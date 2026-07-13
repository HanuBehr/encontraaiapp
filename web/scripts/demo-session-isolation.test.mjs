import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

test("demo locale and lead storage are session-scoped and versioned", () => {
  const localeSession = readFileSync(new URL("../lib/i18n/locale-session.ts", import.meta.url), "utf8");
  const demoStorage = readFileSync(new URL("../lib/demo/storage.ts", import.meta.url), "utf8");

  assert.match(localeSession, /sessionStorage\.getItem\(SESSION_LOCALE_KEY\)/);
  assert.match(localeSession, /sessionStorage\.setItem\(SESSION_LOCALE_KEY, locale\)/);
  assert.doesNotMatch(localeSession, /localStorage/);

  assert.match(demoStorage, /const STORAGE_PREFIX = "encontraai\.demo\.v3"/);
  assert.match(demoStorage, /sessionStorage\.getItem\(key\)/);
  assert.match(demoStorage, /sessionStorage\.setItem\(key, JSON\.stringify\(value\)\)/);
  assert.match(demoStorage, /getActiveLocale\(\)/);
  assert.doesNotMatch(demoStorage, /encontraai\.demo\.v2/);
  assert.doesNotMatch(demoStorage, /localStorage/);
});
