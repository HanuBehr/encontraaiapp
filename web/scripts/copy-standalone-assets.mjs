import { cpSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { join } from "node:path";

const root = process.cwd();
const standaloneDir = join(root, ".next", "standalone");

if (!existsSync(standaloneDir)) {
  process.exit(0);
}

copyIfExists(join(root, ".next", "static"), join(standaloneDir, ".next", "static"));
copyIfExists(join(root, "public"), join(standaloneDir, "public"));

function copyIfExists(source, destination) {
  if (!existsSync(source)) {
    return;
  }
  rmSync(destination, { force: true, recursive: true });
  mkdirSync(destination, { recursive: true });
  cpSync(source, destination, { recursive: true });
}
