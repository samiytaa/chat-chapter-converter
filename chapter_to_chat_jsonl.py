import json
import re
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


CHAPTER_PATTERN = re.compile(r"^第\s*[0-9一二三四五六七八九十百千]+\s*章.*$", re.MULTILINE)
VOLUME_FILENAME_PATTERN = re.compile(r"第\s*([0-9一二三四五六七八九十百千]+)\s*卷")
VOLUME_HEADING_PATTERN = re.compile(r"^#\s*(第\s*[0-9一二三四五六七八九十百千]+\s*卷)\s*$", re.MULTILINE)
CHINESE_NUMERAL_MAP = {
    "零": 0,
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}


def parse_chinese_numeral(text: str) -> int:
    text = text.strip()
    if not text:
        raise ValueError("空的中文数字")
    if text == "十":
        return 10

    total = 0
    current = 0
    unit_map = {"十": 10, "百": 100, "千": 1000}

    for char in text:
        if char in CHINESE_NUMERAL_MAP:
            current = CHINESE_NUMERAL_MAP[char]
        elif char in unit_map:
            if current == 0:
                current = 1
            total += current * unit_map[char]
            current = 0
        else:
            raise ValueError(f"不支持的中文数字: {text}")
    return total + current


def parse_volume_number(volume_text: str) -> int:
    volume_text = volume_text.strip()
    if volume_text.isdigit():
        return int(volume_text)
    return parse_chinese_numeral(volume_text)


def get_volume_info(filename: str) -> tuple[Optional[int], Optional[str]]:
    match = VOLUME_FILENAME_PATTERN.search(filename)
    if not match:
        return None, None

    volume_text = f"第{match.group(1)}卷"
    return parse_volume_number(match.group(1)), volume_text


def merge_txt_uploads(uploads: list) -> str:
    merged_parts = []
    indexed_uploads = []

    for original_index, upload in enumerate(uploads):
        volume_number, volume_title = get_volume_info(upload.filename or "")
        indexed_uploads.append((volume_number, volume_title, original_index, upload))

    indexed_uploads.sort(
        key=lambda item: (
            item[0] is None,
            item[0] if item[0] is not None else item[2],
            item[2],
        )
    )

    for volume_number, volume_title, _, upload in indexed_uploads:
        text = upload.read().decode("utf-8").strip()
        if not text:
            continue

        if volume_number is not None and volume_title is not None:
            merged_parts.append(f"# {volume_title}\n\n{text}")
        else:
            merged_parts.append(text)

    if not merged_parts:
        raise ValueError("上传的 txt 文件内容为空。")

    return "\n\n".join(merged_parts)


def split_chapters(text: str) -> list[tuple[str, str]]:
    matches = list(CHAPTER_PATTERN.finditer(text))
    if not matches:
        raise ValueError("未识别到章节标题，请检查 txt 是否使用“第1章 / 第一章”这类格式。")

    chapters = []
    for index, match in enumerate(matches):
        title = match.group().strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        chapters.append((title, body))

    leading_headings = [f"# {heading.strip()}" for heading in VOLUME_HEADING_PATTERN.findall(text[:matches[0].start()])]
    if leading_headings:
        first_title, first_body = chapters[0]
        chapters[0] = (first_title, f"{chr(10).join(leading_headings)}\n\n{first_body}".strip())

    for index in range(len(chapters) - 1):
        title, body = chapters[index]
        lines = body.splitlines()
        moved_headings = []

        while lines and VOLUME_HEADING_PATTERN.match(lines[-1].strip()):
            moved_headings.insert(0, lines.pop().strip())
            while lines and not lines[-1].strip():
                lines.pop()

        if moved_headings:
            chapters[index] = (title, "\n".join(lines).strip())
            next_title, next_body = chapters[index + 1]
            chapters[index + 1] = (
                next_title,
                f"{chr(10).join(moved_headings)}\n\n{next_body}".strip(),
            )

    return chapters


def find_template_jsonl(workdir: Path) -> Path:
    candidates = sorted(
        path for path in workdir.glob("*.jsonl") if path.name != "output.jsonl"
    )
    if not candidates:
        raise FileNotFoundError("当前目录没有可复用的 jsonl 模板文件。")
    return candidates[0]


def parse_template_lines(lines: list[str]) -> tuple[dict, dict]:
    if len(lines) < 2:
        raise ValueError("模板 jsonl 至少需要包含 1 行 chat_metadata 和 1 条 AI 消息。")

    metadata = json.loads(lines[0])
    ai_message = None

    for line in lines[1:]:
        item = json.loads(line)
        if item.get("is_user") is False:
            ai_message = item
            break

    if ai_message is None:
        raise ValueError("模板 jsonl 中没有找到 AI 消息。")

    return metadata, ai_message


def load_template(template_path: Path) -> tuple[dict, dict]:
    lines = template_path.read_text(encoding="utf-8").splitlines()
    return parse_template_lines(lines)


def load_template_from_text(template_text: str) -> tuple[dict, dict]:
    return parse_template_lines(template_text.splitlines())


def iso_with_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def build_ai_message(template: dict, mes: str, send_date: str) -> dict:
    message = deepcopy(template)
    message["mes"] = mes
    message["send_date"] = send_date
    message["is_user"] = False
    message["is_system"] = False
    message["swipes"] = [mes]
    message["swipe_id"] = 0

    swipe_info = message.get("swipe_info")
    if isinstance(swipe_info, list) and swipe_info:
        info = deepcopy(swipe_info[0])
        info["send_date"] = send_date
        if not isinstance(info.get("extra"), dict):
            info["extra"] = {}
        message["swipe_info"] = [info]
    else:
        message["swipe_info"] = [{"send_date": send_date, "extra": {}}]

    return message


def convert_text_to_jsonl(text: str, metadata: dict, ai_template: dict) -> str:
    chapters = split_chapters(text)
    start_time = datetime.now(timezone.utc)
    lines = [json.dumps(metadata, ensure_ascii=False)]

    for index, (title, body) in enumerate(chapters):
        mes = f"## {title}\n\n{body}".strip()
        send_date = iso_with_z(start_time + timedelta(seconds=index * 5))
        message = build_ai_message(ai_template, mes, send_date)
        lines.append(json.dumps(message, ensure_ascii=False))

    return "\n".join(lines) + "\n"


def main() -> None:
    workdir = Path(__file__).resolve().parent
    text_path = workdir / "正文.txt"
    output_path = workdir / "正文_转换结果.jsonl"

    if not text_path.exists():
        raise FileNotFoundError("未找到 正文.txt")

    template_path = find_template_jsonl(workdir)
    metadata, ai_template = load_template(template_path)
    text = text_path.read_text(encoding="utf-8")
    result = convert_text_to_jsonl(text, metadata, ai_template)

    output_path.write_text(result, encoding="utf-8")

    print(f"已生成: {output_path}")
    print(f"模板文件: {template_path.name}")
    print(f"章节数: {len(split_chapters(text))}")


if __name__ == "__main__":
    main()
