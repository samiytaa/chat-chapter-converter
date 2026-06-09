import { copyFileSync, mkdirSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = fileURLToPath(new URL(".", import.meta.url));
const rootDir = resolve(scriptDir, "..");
const srcDir = resolve(rootDir, "src");
const distDir = resolve(rootDir, "dist");

function copyDirectory(sourceDir, targetDir) {
  mkdirSync(targetDir, { recursive: true });

  for (const entry of readdirSync(sourceDir)) {
    const sourcePath = join(sourceDir, entry);
    const targetPath = join(targetDir, entry);
    const stats = statSync(sourcePath);

    if (stats.isDirectory()) {
      copyDirectory(sourcePath, targetPath);
      continue;
    }

    copyFileSync(sourcePath, targetPath);
  }
}

rmSync(distDir, { recursive: true, force: true });
mkdirSync(distDir, { recursive: true });
copyDirectory(srcDir, distDir);
writeFileSync(resolve(distDir, ".nojekyll"), "");

console.log("Build completed:", distDir);
