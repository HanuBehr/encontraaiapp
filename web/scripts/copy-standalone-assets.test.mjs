import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import test from "node:test";

const scriptPath = join(dirname(fileURLToPath(import.meta.url)), "copy-standalone-assets.mjs");

test("copies static and public assets into standalone output", () => {
  const workspace = mkdtempSync(join(tmpdir(), "encontraai-standalone-assets-"));
  try {
    createFile(join(workspace, ".next", "standalone", ".keep"));
    createFile(join(workspace, ".next", "static", "chunks", "app.js"));
    createFile(join(workspace, "public", "favicon.ico"));

    const result = spawnSync(process.execPath, [scriptPath], {
      cwd: workspace,
      encoding: "utf8",
    });

    assert.equal(result.status, 0, result.stderr);
    assert.equal(existsSync(join(workspace, ".next", "standalone", ".next", "static", "chunks", "app.js")), true);
    assert.equal(existsSync(join(workspace, ".next", "standalone", "public", "favicon.ico")), true);
  } finally {
    rmSync(workspace, { force: true, recursive: true });
  }
});

function createFile(path) {
  rmSync(path, { force: true });
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, "test");
}
