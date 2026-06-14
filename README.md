# Chat Chapter Converter

一个纯前端的小工具，用来把章节 TXT 转成聊天记录 JSONL。

## 功能

- 支持批量选择 TXT 文件
- 支持导入或直接粘贴 JSONL 模板
- 在浏览器内完成转换并下载结果
- 无需后端服务

## 本地使用

安装依赖并构建：

```bash
npm run build
```

启动本地预览：

```bash
npm run serve
```

## 部署

项目通过 GitHub Pages 自动部署，工作流文件位于 `.github/workflows/deploy.yml`。
