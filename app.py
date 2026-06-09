from io import BytesIO
from pathlib import Path
import socket
from urllib.parse import quote

from flask import Flask, render_template_string, request, send_file

from chapter_to_chat_jsonl import (
    convert_text_to_jsonl,
    find_template_jsonl,
    load_template,
    load_template_from_text,
    merge_txt_uploads,
)


app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_PORT = 8765
PAGE_TEMPLATE = """
<!doctype html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>TXT 转 JSONL</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #f0ebe4;
            font-family: "Microsoft YaHei", "PingFang SC", "Segoe UI", sans-serif;
            color: #2a2118;
        }
        .card {
            width: min(420px, 92vw);
            background: #fff;
            border-radius: 20px;
            padding: 32px 28px;
            box-shadow: 0 8px 40px rgba(0,0,0,0.10);
        }
        h1 {
            font-size: 20px;
            font-weight: 700;
            margin-bottom: 24px;
            text-align: center;
            color: #1f4f42;
        }
        form { display: grid; gap: 16px; }
        .field label {
            display: block;
            font-size: 13px;
            color: #6a6055;
            margin-bottom: 6px;
        }
        input[type="file"] {
            width: 100%;
            padding: 14px;
            border: 1.5px dashed #a8c5bc;
            border-radius: 12px;
            background: #f7faf9;
            font-size: 14px;
            color: #2a2118;
            cursor: pointer;
            transition: border-color 0.2s;
        }
        input[type="file"]:hover { border-color: #2e6a59; }
        button {
            width: 100%;
            padding: 14px;
            border: none;
            border-radius: 12px;
            background: #2e6a59;
            color: #fff;
            font-size: 16px;
            font-weight: 700;
            cursor: pointer;
            transition: background 0.2s;
        }
        button:hover { background: #1f4f42; }
        .error {
            padding: 10px 14px;
            border-radius: 10px;
            background: #fff3ef;
            color: #a33a32;
            border: 1px solid #efc4c0;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="card">
        <h1>TXT 转聊天记录 JSONL</h1>
        <form method="post" enctype="multipart/form-data">
            <div class="field">
                <label for="txt_file">文本文件（.txt，可多选）</label>
                <input id="txt_file" type="file" name="txt_file" accept=".txt,text/plain" multiple required>
            </div>
            <div class="field">
                <label for="template_jsonl">JSONL 模板（可选）</label>
                <input id="template_jsonl" type="file" name="template_jsonl" accept=".jsonl,application/json">
            </div>
            {% if error %}
            <div class="error">{{ error }}</div>
            {% endif %}
            <button type="submit">转换并下载</button>
        </form>
    </div>
</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return render_template_string(PAGE_TEMPLATE, error=None)

    uploads = [file for file in request.files.getlist("txt_file") if file and file.filename]
    if not uploads:
        return render_template_string(PAGE_TEMPLATE, error="请先选择至少一个 txt 文件。")
    template_upload = request.files.get("template_jsonl")

    try:
        text = merge_txt_uploads(uploads)
    except UnicodeDecodeError:
        return render_template_string(PAGE_TEMPLATE, error="上传的 txt 文件里有非 UTF-8 编码内容，请先统一保存为 UTF-8。")

    try:
        if template_upload is not None and template_upload.filename:
            try:
                template_text = template_upload.read().decode("utf-8")
            except UnicodeDecodeError:
                return render_template_string(PAGE_TEMPLATE, error="上传的 jsonl 模板不是 UTF-8，请先转成 UTF-8。")
            metadata, ai_template = load_template_from_text(template_text)
        else:
            template_path = find_template_jsonl(BASE_DIR)
            metadata, ai_template = load_template(template_path)
        result = convert_text_to_jsonl(text, metadata, ai_template)
    except Exception as exc:
        return render_template_string(PAGE_TEMPLATE, error=str(exc))

    if len(uploads) == 1:
        stem = Path(uploads[0].filename).stem or "转换结果"
    else:
        stem = "合并正文"
    download_name = f"{stem}_转换结果.jsonl"
    encoded_name = quote(download_name)
    buffer = BytesIO(result.encode("utf-8"))

    response = send_file(
        buffer,
        as_attachment=True,
        download_name=download_name,
        mimetype="application/json",
    )
    response.headers["Content-Disposition"] = (
        f"attachment; filename*=UTF-8''{encoded_name}"
    )
    return response


def find_available_port(start_port: int = DEFAULT_PORT) -> int:
    for port in range(start_port, start_port + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError("没有找到可用端口，请稍后重试或关闭其他本地服务。")


if __name__ == "__main__":
    port = find_available_port()
    print(f"请在浏览器打开: http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=True, use_reloader=False)
