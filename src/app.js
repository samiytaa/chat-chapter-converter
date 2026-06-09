const VOLUME_FILENAME_PATTERN = /第\s*([0-9一二三四五六七八九十百千]+)\s*卷/;
const VOLUME_HEADING_PATTERN = /^#\s*(第\s*[0-9一二三四五六七八九十百千]+\s*卷)\s*$/;
const CHAPTER_PATTERN = /^第\s*[0-9一二三四五六七八九十百千]+\s*章.*$/gm;
const CHINESE_NUMERAL_MAP = {
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
};

const form = document.querySelector("#converterForm");
const txtFilesInput = document.querySelector("#txtFiles");
const templateFileInput = document.querySelector("#templateFile");
const templateTextInput = document.querySelector("#templateText");
const statusElement = document.querySelector("#status");
const buildSampleButton = document.querySelector("#buildSampleButton");

function setStatus(message, isError = false) {
  statusElement.textContent = message;
  statusElement.classList.toggle("error", isError);
}

function parseChineseNumeral(text) {
  const value = text.trim();
  if (!value) {
    throw new Error("空的中文数字");
  }
  if (value === "十") {
    return 10;
  }

  const unitMap = { "十": 10, "百": 100, "千": 1000 };
  let total = 0;
  let current = 0;

  for (const char of value) {
    if (Object.hasOwn(CHINESE_NUMERAL_MAP, char)) {
      current = CHINESE_NUMERAL_MAP[char];
      continue;
    }
    if (Object.hasOwn(unitMap, char)) {
      if (current === 0) {
        current = 1;
      }
      total += current * unitMap[char];
      current = 0;
      continue;
    }
    throw new Error(`不支持的中文数字: ${text}`);
  }

  return total + current;
}

function parseVolumeNumber(volumeText) {
  const value = volumeText.trim();
  if (/^\d+$/.test(value)) {
    return Number(value);
  }
  return parseChineseNumeral(value);
}

function getVolumeInfo(filename) {
  const match = filename.match(VOLUME_FILENAME_PATTERN);
  if (!match) {
    return { volumeNumber: null, volumeTitle: null };
  }
  return {
    volumeNumber: parseVolumeNumber(match[1]),
    volumeTitle: `第${match[1]}卷`,
  };
}

async function readTextFile(file, label) {
  try {
    return await file.text();
  } catch {
    throw new Error(`${label} 读取失败。`);
  }
}

async function mergeTxtUploads(files) {
  const indexedFiles = files.map((file, index) => {
    const { volumeNumber, volumeTitle } = getVolumeInfo(file.name || "");
    return { file, index, volumeNumber, volumeTitle };
  });

  indexedFiles.sort((left, right) => {
    if (left.volumeNumber === null && right.volumeNumber !== null) {
      return 1;
    }
    if (left.volumeNumber !== null && right.volumeNumber === null) {
      return -1;
    }
    if (left.volumeNumber !== null && right.volumeNumber !== null && left.volumeNumber !== right.volumeNumber) {
      return left.volumeNumber - right.volumeNumber;
    }
    return left.index - right.index;
  });

  const mergedParts = [];
  for (const item of indexedFiles) {
    const text = (await readTextFile(item.file, item.file.name)).trim();
    if (!text) {
      continue;
    }
    if (item.volumeNumber !== null && item.volumeTitle !== null) {
      mergedParts.push(`# ${item.volumeTitle}\n\n${text}`);
    } else {
      mergedParts.push(text);
    }
  }

  if (mergedParts.length === 0) {
    throw new Error("上传的 txt 文件内容为空。");
  }

  return mergedParts.join("\n\n");
}

function splitChapters(text) {
  const matches = [...text.matchAll(CHAPTER_PATTERN)];
  if (matches.length === 0) {
    throw new Error("未识别到章节标题，请检查 txt 是否使用“第1章 / 第一章”这类格式。");
  }

  const chapters = matches.map((match, index) => {
    const title = match[0].trim();
    const start = match.index + match[0].length;
    const end = index + 1 < matches.length ? matches[index + 1].index : text.length;
    const body = text.slice(start, end).trim();
    return [title, body];
  });

  const prefix = text.slice(0, matches[0].index);
  const leadingHeadings = prefix
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => VOLUME_HEADING_PATTERN.test(line))
    .map((line) => `# ${line.replace(/^#\s*/, "")}`);

  if (leadingHeadings.length > 0) {
    const [firstTitle, firstBody] = chapters[0];
    chapters[0] = [firstTitle, `${leadingHeadings.join("\n")}\n\n${firstBody}`.trim()];
  }

  for (let index = 0; index < chapters.length - 1; index += 1) {
    const [title, body] = chapters[index];
    const lines = body.split(/\r?\n/);
    const movedHeadings = [];

    while (lines.length > 0 && VOLUME_HEADING_PATTERN.test(lines[lines.length - 1].trim())) {
      movedHeadings.unshift(lines.pop().trim());
      while (lines.length > 0 && !lines[lines.length - 1].trim()) {
        lines.pop();
      }
    }

    if (movedHeadings.length > 0) {
      chapters[index] = [title, lines.join("\n").trim()];
      const [nextTitle, nextBody] = chapters[index + 1];
      chapters[index + 1] = [nextTitle, `${movedHeadings.join("\n")}\n\n${nextBody}`.trim()];
    }
  }

  return chapters;
}

function parseTemplateLines(lines) {
  if (lines.length < 2) {
    throw new Error("模板 jsonl 至少需要包含 1 行 chat_metadata 和 1 条 AI 消息。");
  }

  const metadata = JSON.parse(lines[0]);
  let aiMessage = null;

  for (const line of lines.slice(1)) {
    if (!line.trim()) {
      continue;
    }
    const item = JSON.parse(line);
    if (item.is_user === false) {
      aiMessage = item;
      break;
    }
  }

  if (!aiMessage) {
    throw new Error("模板 jsonl 中没有找到 AI 消息。");
  }

  return { metadata, aiMessage };
}

function loadTemplateFromText(templateText) {
  return parseTemplateLines(templateText.split(/\r?\n/));
}

function isoWithZ(date) {
  return date.toISOString().replace(/\.\d{3}Z$/, (value) => value);
}

function deepClone(value) {
  return JSON.parse(JSON.stringify(value));
}

function buildAiMessage(template, mes, sendDate) {
  const message = deepClone(template);
  message.mes = mes;
  message.send_date = sendDate;
  message.is_user = false;
  message.is_system = false;
  message.swipes = [mes];
  message.swipe_id = 0;

  const swipeInfo = Array.isArray(message.swipe_info) ? message.swipe_info : [];
  if (swipeInfo.length > 0) {
    const info = deepClone(swipeInfo[0]);
    info.send_date = sendDate;
    if (typeof info.extra !== "object" || info.extra === null || Array.isArray(info.extra)) {
      info.extra = {};
    }
    message.swipe_info = [info];
  } else {
    message.swipe_info = [{ send_date: sendDate, extra: {} }];
  }

  return message;
}

function convertTextToJsonl(text, metadata, aiTemplate) {
  const chapters = splitChapters(text);
  const startTime = Date.now();
  const lines = [JSON.stringify(metadata)];

  chapters.forEach(([title, body], index) => {
    const mes = `## ${title}\n\n${body}`.trim();
    const sendDate = isoWithZ(new Date(startTime + index * 5000));
    const message = buildAiMessage(aiTemplate, mes, sendDate);
    lines.push(JSON.stringify(message));
  });

  return `${lines.join("\n")}\n`;
}

function triggerDownload(content, filename) {
  const blob = new Blob([content], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function getDownloadName(files) {
  if (files.length === 1) {
    const fileName = files[0].name || "转换结果";
    const dotIndex = fileName.lastIndexOf(".");
    const stem = dotIndex > 0 ? fileName.slice(0, dotIndex) : fileName;
    return `${stem || "转换结果"}_转换结果.jsonl`;
  }
  return "合并正文_转换结果.jsonl";
}

templateFileInput.addEventListener("change", async (event) => {
  const [file] = event.currentTarget.files || [];
  if (!file) {
    return;
  }
  const templateText = await readTextFile(file, "模板文件");
  templateTextInput.value = templateText;
  localStorage.setItem("lastTemplateText", templateText);
  setStatus("模板文件已载入。");
});

buildSampleButton.addEventListener("click", () => {
  const lastTemplateText = localStorage.getItem("lastTemplateText");
  if (!lastTemplateText) {
    setStatus("没有可恢复的模板内容。", true);
    return;
  }
  templateTextInput.value = lastTemplateText;
  setStatus("已填入上次模板。");
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setStatus("正在转换...");

  const files = [...txtFilesInput.files];
  if (files.length === 0) {
    setStatus("请先选择至少一个 txt 文件。", true);
    return;
  }

  const templateText = templateTextInput.value.trim();
  if (!templateText) {
    setStatus("请上传或粘贴 JSONL 模板内容。", true);
    return;
  }

  try {
    const mergedText = await mergeTxtUploads(files);
    const { metadata, aiMessage } = loadTemplateFromText(templateText);
    const result = convertTextToJsonl(mergedText, metadata, aiMessage);
    localStorage.setItem("lastTemplateText", templateText);
    triggerDownload(result, getDownloadName(files));
    setStatus(`转换完成，共处理 ${files.length} 个文本文件。`);
  } catch (error) {
    setStatus(error instanceof Error ? error.message : "转换失败。", true);
  }
});
