#!/usr/bin/env node
// Lists the English UI strings in frontend/src that the zh-TW dictionary does not cover yet.
// Run after merging an upstream LeLab update:   node scripts/i18n-check.mjs
//   --dump     print every UI string found (JSON), translated or not
//   --strict   exit 1 when strings are missing (for CI)
// Part of the zh-TW add-on; see I18N.zh-TW.md in the repository root of lelab-zh.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.resolve(HERE, "../src");
const DICT_FILE = path.join(SRC, "i18n/zh-TW.json");
const args = new Set(process.argv.slice(2));

// Attributes whose string values are shown to the user.
const UI_ATTRS = new Set(["placeholder", "title", "aria-label", "alt", "label", "description", "tooltip", "message"]);
// Object keys whose string values end up on screen (toasts, dialogs, menus).
const UI_KEYS = new Set(["title", "description", "label", "placeholder", "message", "body", "heading", "text", "hint", "cta", "tooltip", "action"]);
// Attributes that are never user-facing text.
const SKIP_ATTRS = new Set(["className", "class", "id", "key", "href", "src", "type", "role", "variant", "size", "name", "value",
  "htmlFor", "data-tour", "data-testid", "rel", "target", "side", "align", "orientation", "mode", "autoComplete", "inputMode"]);
const SKIP_CALLS = new Set(["cn", "clsx", "fetch", "fetchWithHeaders", "require", "console.log", "console.warn", "console.error",
  "console.info", "console.debug", "localStorage.getItem", "localStorage.setItem", "sessionStorage.getItem", "sessionStorage.setItem",
  "addEventListener", "removeEventListener", "querySelector", "querySelectorAll", "getItem", "setItem", "removeItem", "logger"]);

export const normalize = (s) => s.replace(/\s+/g, " ").trim();

// A string looks like UI prose if it has a letter, is not code-ish, and reads like words.
function looksLikeUiText(s) {
  if (!/[A-Za-z]/.test(s)) return false;
  if (/^(https?:|\/|\.\/|@\/|#|data:|ws:)/.test(s)) return false;          // urls and paths
  if (/^[a-z0-9_.:/-]+$/.test(s)) return false;                           // identifiers, keys, css tokens
  if (/^[A-Z0-9_]+$/.test(s) && s.length > 1 && !/^[A-Z][a-z]/.test(s)) return /^[A-Z]{2,5}$/.test(s) ? false : false;
  if (/\b(bg|text|border|flex|grid|px|py|mx|my|mt|mb|ml|mr|pt|pb|gap|w|h|rounded|hover|focus|items|justify)-/.test(s)) return false;
  if (/[{};=<>]|=>/.test(s)) return false;                                 // code fragments
  if (/^[A-Z][a-zA-Z]+$/.test(s)) return true;                            // single capitalized word: "Ready"
  if (/\s/.test(s)) return true;                                          // phrases
  return /[.!?…:]$/.test(s);
}

function callName(node) {
  const e = node.expression;
  if (ts.isIdentifier(e)) return e.text;
  if (ts.isPropertyAccessExpression(e)) {
    const left = ts.isIdentifier(e.expression) ? e.expression.text : ts.isPropertyAccessExpression(e.expression) ? e.expression.name.text : "";
    return left ? `${left}.${e.name.text}` : e.name.text;
  }
  return "";
}

function insideSkippedContext(node) {
  for (let p = node.parent; p; p = p.parent) {
    if (ts.isJsxAttribute(p)) return SKIP_ATTRS.has(p.name.getText());
    if (ts.isCallExpression(p)) {
      const n = callName(p);
      if (SKIP_CALLS.has(n) || SKIP_CALLS.has(n.split(".").pop())) return true;
    }
    if (ts.isImportDeclaration(p) || ts.isExportDeclaration(p)) return true;
    if (ts.isPropertyAssignment(p) && p.initializer !== node && !ts.isObjectLiteralExpression(p.initializer)) return false;
    if (ts.isElementAccessExpression(p)) return true;
    if (ts.isCaseClause(p)) return p.expression === node || p.expression.pos <= node.pos && node.end <= p.expression.end;
    if (ts.isBinaryExpression(p) && [ts.SyntaxKind.EqualsEqualsEqualsToken, ts.SyntaxKind.ExclamationEqualsEqualsToken,
      ts.SyntaxKind.EqualsEqualsToken, ts.SyntaxKind.ExclamationEqualsToken].includes(p.operatorToken.kind)) return true;
    if (ts.isTypeNode(p) || ts.isLiteralTypeNode(p)) return true;
    if (ts.isFunctionLike(p) || ts.isSourceFile(p)) return false;
  }
  return false;
}

export function extract(srcDir = SRC) {
  const found = new Map();   // text -> Set(file)
  const templates = new Map(); // pattern text -> Set(file)
  const add = (map, text, file) => { if (!map.has(text)) map.set(text, new Set()); map.get(text).add(file); };
  const files = [];
  (function walk(d) {
    for (const e of fs.readdirSync(d, { withFileTypes: true })) {
      const p = path.join(d, e.name);
      if (e.isDirectory()) { if (e.name !== "i18n") walk(p); continue; }
      if (/\.(tsx?|jsx?)$/.test(e.name) && !/\.test\.|\.spec\.|\.d\.ts$/.test(e.name)) files.push(p);
    }
  })(srcDir);
  for (const file of files) {
    const rel = path.relative(srcDir, file);
    const sf = ts.createSourceFile(file, fs.readFileSync(file, "utf8"), ts.ScriptTarget.Latest, true,
      file.endsWith("x") ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
    const visit = (node) => {
      if (ts.isJsxText(node)) {
        const t = normalize(node.getText());
        if (t && /[A-Za-z]/.test(t)) add(found, t, rel);
      } else if (ts.isJsxAttribute(node) && node.initializer && ts.isStringLiteral(node.initializer)) {
        const t = normalize(node.initializer.text);
        if (UI_ATTRS.has(node.name.getText()) && /[A-Za-z]/.test(t)) add(found, t, rel);
      } else if ((ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) && !ts.isJsxAttribute(node.parent)) {
        const t = normalize(node.text);
        const key = ts.isPropertyAssignment(node.parent) && node.parent.initializer === node ? node.parent.name.getText() : "";
        if (!insideSkippedContext(node) && (UI_KEYS.has(key) ? /[A-Za-z]/.test(t) : looksLikeUiText(t))) add(found, t, rel);
      } else if (ts.isTemplateExpression(node) && !insideSkippedContext(node)) {
        let t = node.head.text; node.templateSpans.forEach((s, i) => { t += `{${i}}` + s.literal.text; });
        t = normalize(t);
        if (looksLikeUiText(t.replace(/\{\d+\}/g, "x"))) add(templates, t, rel);
      }
      ts.forEachChild(node, visit);
    };
    visit(sf);
  }
  return { found, templates };
}

function main() {
  const dict = JSON.parse(fs.readFileSync(DICT_FILE, "utf8"));
  const strings = dict.strings || {};
  const ignore = new Set(dict.ignore || []);
  const patterns = (dict.patterns || []).map(([re, rep]) => [new RegExp(re), rep]);
  const covered = (t) => t in strings || ignore.has(t) || patterns.some(([re]) => re.test(t));
  const { found, templates } = extract();
  if (args.has("--dump")) {
    console.log(JSON.stringify({ strings: [...found.keys()].sort(), templates: [...templates.keys()].sort() }, null, 1));
    return;
  }
  const missing = [...found.keys()].filter((t) => !covered(t)).sort();
  // Try the template with every placeholder as "1", then with the first as "1" and the rest empty ("episode{1}").
  const variants = (t) => [t.replace(/\{\d+\}/g, "1"), t.replace(/\{0\}/g, "1").replace(/\{\d+\}/g, "")];
  const missingTpl = [...templates.keys()].filter((t) => !ignore.has(t) && !variants(t).some((v) => patterns.some(([re]) => re.test(v)))).sort();
  const stale = Object.keys(strings).filter((k) => !found.has(k)).sort();
  console.log(`zh-TW dictionary: ${Object.keys(strings).length} strings, ${patterns.length} patterns, ${ignore.size} ignored`);
  console.log(`UI strings in source: ${found.size}; not translated yet: ${missing.length}`);
  for (const t of missing) console.log(`  MISSING  ${JSON.stringify(t)}   (${[...found.get(t)].join(", ")})`);
  if (missingTpl.length) {
    console.log(`Text built from variables (add a pattern if it shows on screen): ${missingTpl.length}`);
    for (const t of missingTpl) console.log(`  TEMPLATE ${JSON.stringify(t)}   (${[...templates.get(t)].join(", ")})`);
  }
  if (args.has("--stale") && stale.length) {
    console.log(`Dictionary entries no longer in source (safe to keep; backend messages live here too): ${stale.length}`);
    for (const t of stale) console.log(`  UNUSED   ${JSON.stringify(t)}`);
  }
  if (args.has("--strict") && missing.length) process.exit(1);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main();
