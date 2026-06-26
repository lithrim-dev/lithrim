// @vitest-environment node
/* theme_tokens.test.js — UI-THEME-TOKENS-1: the shell's inline styles reference CSS custom
   properties (var(--x)); a token used WITHOUT a fallback that is never defined resolves to nothing
   — a transparent background / inherited color. The screenshot-1 session-menu bleed-through was
   exactly this: var(--panel) undefined. These tests pin the three then-missing tokens AND guard the
   whole class (any used-without-fallback custom prop must be defined in a stylesheet). */
import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

const srcDir = fileURLToPath(new URL(".", import.meta.url));
const stylesCss = readFileSync(join(srcDir, "styles.css"), "utf8");

// the custom props declared inside a specific selector block (first match; blocks here are flat).
function blockDefs(selectorRegex) {
  const m = stylesCss.match(selectorRegex);
  const defs = new Set();
  if (m) for (const mm of m[1].matchAll(/(--[A-Za-z0-9_-]+)\s*:/g)) defs.add(mm[1]);
  return defs;
}
const rootDefs = blockDefs(/:root\s*\{([\s\S]*?)\}/);
const darkDefs = blockDefs(/\[data-theme="dark"\]\s*\{([\s\S]*?)\}/);

function walk(dir) {
  const out = [];
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) out.push(...walk(p));
    else out.push(p);
  }
  return out;
}
const codeFiles = walk(srcDir).filter((f) => /\.(jsx?|css)$/.test(f) && !f.endsWith(".test.js"));

// every custom prop DEFINED anywhere (css blocks + inline `"--x":` style definitions).
const definedAll = new Set();
for (const f of codeFiles)
  for (const mm of readFileSync(f, "utf8").matchAll(/(--[A-Za-z0-9_-]+)\s*:/g)) definedAll.add(mm[1]);

// runtime-injected vars (set by a library on the element at render, never in our CSS).
const RUNTIME_ALLOW = new Set(["--radix-select-trigger-width"]);

describe("UI-THEME-TOKENS-1 — theme tokens are defined (no transparent/inherited fallbacks)", () => {
  it("the three formerly-missing tokens are defined in BOTH the light :root and the dark block", () => {
    for (const t of ["--panel", "--text", "--fg"]) {
      expect(rootDefs, `light :root must define ${t}`).toContain(t);
      expect(darkDefs, `dark [data-theme="dark"] must define ${t}`).toContain(t);
    }
  });

  it("every var(--x) used WITHOUT a fallback resolves to a defined token (no silent bleed-through)", () => {
    const undefinedUsed = new Set();
    for (const f of codeFiles) {
      const src = readFileSync(f, "utf8");
      for (const mm of src.matchAll(/var\(\s*(--[A-Za-z0-9_-]+)\s*([,)])/g)) {
        const [, name, next] = mm;
        if (next === ",") continue; // has an explicit fallback — safe
        if (RUNTIME_ALLOW.has(name)) continue;
        if (!definedAll.has(name)) undefinedUsed.add(name);
      }
    }
    expect([...undefinedUsed].sort()).toEqual([]);
  });
});
