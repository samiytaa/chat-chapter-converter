import { createServer } from "node:http";
import { readFileSync, existsSync, statSync } from "node:fs";
import { extname, join, normalize, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = fileURLToPath(new URL(".", import.meta.url));
const distDir = resolve(scriptDir, "..", "dist");
const host = "127.0.0.1";
const startPort = 8765;

const mimeTypes = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".txt": "text/plain; charset=utf-8",
};

function findPort(port) {
  return new Promise((resolvePort, reject) => {
    const tester = createServer();
    tester.once("error", () => {
      resolvePort(findPort(port + 1));
    });
    tester.once("listening", () => {
      tester.close(() => resolvePort(port));
    });
    tester.listen(port, host);
  }).catch(reject);
}

function getFilePath(urlPath) {
  const safePath = normalize(urlPath.split("?")[0]).replace(/^(\.\.[/\\])+/, "");
  const targetPath = safePath === "/" ? join(distDir, "index.html") : join(distDir, safePath);
  if (existsSync(targetPath) && statSync(targetPath).isFile()) {
    return targetPath;
  }
  return join(distDir, "index.html");
}

const port = await findPort(startPort);

const server = createServer((request, response) => {
  const filePath = getFilePath(request.url || "/");
  const extension = extname(filePath).toLowerCase();
  const contentType = mimeTypes[extension] || "application/octet-stream";

  try {
    const content = readFileSync(filePath);
    response.writeHead(200, { "Content-Type": contentType });
    response.end(content);
  } catch {
    response.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
    response.end("Not Found");
  }
});

server.listen(port, host, () => {
  console.log(`Preview server: http://${host}:${port}`);
});
