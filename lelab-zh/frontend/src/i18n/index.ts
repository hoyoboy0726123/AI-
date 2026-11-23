// zh-TW add-on entry point. main.tsx imports this file once; nothing else in LeLab refers to it.
// It starts the DOM translator and adds a floating 中文 / EN button. See I18N.zh-TW.md.
import dict from "./zh-TW.json";
import { DomTranslator, Translator, type Lang, type Dictionary } from "./translator";

const STORAGE_KEY = "lelab.lang";

function initialLanguage(): Lang {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "en" || saved === "zh-TW") return saved;
  } catch {
    // Storage can be unavailable (private mode); fall through to the browser language.
  }
  // Traditional Chinese browsers start in Chinese; everyone else starts in English and can switch.
  return /^zh-(TW|HK|MO|Hant)\b/i.test(navigator.language || "") ? "zh-TW" : "en";
}

function saveLanguage(lang: Lang): void {
  try { localStorage.setItem(STORAGE_KEY, lang); } catch { /* non-fatal */ }
}

function makeToggle(dom: DomTranslator): HTMLButtonElement {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.id = "lelab-lang-toggle";
  btn.setAttribute("data-no-i18n", "");
  btn.setAttribute("translate", "no");
  const paint = () => {
    const zh = dom.language === "zh-TW";
    btn.textContent = zh ? "EN" : "中文";
    btn.title = zh ? "Switch to English" : "切換成中文";
    btn.setAttribute("aria-label", btn.title);
    document.documentElement.lang = zh ? "zh-Hant" : "en";
  };
  Object.assign(btn.style, {
    position: "fixed", right: "16px", bottom: "80px", zIndex: "2147483000",  // above LeLab's ? help button
    minWidth: "56px", height: "40px", padding: "0 14px", borderRadius: "999px",
    border: "1px solid #4b5563", background: "#111827", color: "#f9fafb",
    font: "600 14px/1 system-ui, -apple-system, 'Segoe UI', 'Noto Sans TC', 'Microsoft JhengHei', sans-serif",
    letterSpacing: "0.02em", cursor: "pointer", boxShadow: "0 4px 14px rgba(0,0,0,.35)",
  } satisfies Partial<CSSStyleDeclaration>);
  btn.addEventListener("click", () => {
    const next: Lang = dom.language === "zh-TW" ? "en" : "zh-TW";
    dom.setLanguage(next);
    saveLanguage(next);
    paint();
  });
  paint();
  return btn;
}

export function startI18n(): DomTranslator {
  const dom = new DomTranslator(new Translator(dict as Dictionary), document.body);
  dom.start(initialLanguage());
  document.body.appendChild(makeToggle(dom));
  return dom;
}

if (typeof document !== "undefined" && !(window as unknown as { __lelabI18n?: unknown }).__lelabI18n) {
  const run = () => { (window as unknown as { __lelabI18n?: DomTranslator }).__lelabI18n = startI18n(); };
  if (document.body) run();
  else document.addEventListener("DOMContentLoaded", run, { once: true });
}
