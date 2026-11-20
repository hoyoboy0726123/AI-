// zh-TW add-on for LeLab: translates the rendered page instead of the source code.
//
// LeLab's components keep their English strings. This module watches the DOM and swaps
// any text node or UI attribute whose whole text is a dictionary key for its translation,
// and swaps it back when the user picks English. Because no component is edited, upstream
// LeLab updates merge without conflicts; a string added upstream simply shows in English
// until it is added to zh-TW.json (scripts/i18n-check.mjs lists those strings).

export type Lang = "en" | "zh-TW";

export interface Dictionary {
  strings: Record<string, string>;
  patterns?: [string, string][];
  ignore?: string[];
}

const ATTRS = ["placeholder", "title", "aria-label", "alt"] as const;
// Text inside these is user data, code, or not rendered; never translate it.
const SKIP_TAGS = new Set(["SCRIPT", "STYLE", "NOSCRIPT", "TEXTAREA", "CODE", "PRE", "KBD", "CANVAS"]);
const OPT_OUT = "[data-no-i18n],[translate='no'],[contenteditable='true']";

export const normalize = (s: string): string => s.replace(/\s+/g, " ").trim();

export class Translator {
  private strings: Map<string, string>;
  private patterns: [RegExp, string][];

  constructor(dict: Dictionary) {
    this.strings = new Map(Object.entries(dict.strings));
    this.patterns = (dict.patterns ?? []).map(([re, rep]) => [new RegExp(re), rep]);
  }

  /** Chinese for an English UI string, or null when it is not in the dictionary. Keeps outer spaces. */
  translate(text: string): string | null {
    const key = normalize(text);
    if (!key || !/[A-Za-z]/.test(key)) return null;
    let out = this.strings.get(key);
    if (out === undefined) {
      for (const [re, rep] of this.patterns) {
        if (re.test(key)) {
          out = key.replace(re, (...m) => rep.replace(/\$(\d)/g, (_, i) => this.translate(m[+i] ?? "") ?? m[+i] ?? ""));
          break;
        }
      }
    }
    if (out === undefined) return null;
    // Keep the spaces that separate this text from its neighbours, except next to full-width punctuation.
    const fullWidth = /[\u3000-\u303f\uff00-\uffef]/;
    const lead = /^\s/.test(text) && out && !fullWidth.test(out[0]) ? " " : "";
    const trail = /\s$/.test(text) && out && !fullWidth.test(out[out.length - 1]) ? " " : "";
    return lead + out + trail;
  }
}

interface TextRecord { original: string; shown: string }

/** Keeps the live DOM in the chosen language as React re-renders it. */
export class DomTranslator {
  private lang: Lang = "en";
  private texts = new WeakMap<Text, TextRecord>();
  private attrs = new WeakMap<Element, Map<string, TextRecord>>();
  private observer: MutationObserver | null = null;

  constructor(private translator: Translator, private root: Node = document.body) {}

  get language(): Lang { return this.lang; }

  start(lang: Lang): void {
    this.lang = lang;
    this.walk(this.root);
    this.observer = new MutationObserver((records) => this.onMutations(records));
    this.observer.observe(this.root, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: [...ATTRS] });
  }

  stop(): void { this.observer?.disconnect(); this.observer = null; }

  setLanguage(lang: Lang): void {
    if (lang === this.lang) return;
    this.lang = lang;
    this.walk(this.root);
  }

  private skip(el: Element | null): boolean {
    for (let e = el; e; e = e.parentElement) {
      if (SKIP_TAGS.has(e.tagName.toUpperCase())) return true;
      if (e.matches?.(OPT_OUT)) return true;
    }
    return false;
  }

  private walk(node: Node): void {
    if (node.nodeType === Node.TEXT_NODE) { this.applyText(node as Text); return; }
    if (node.nodeType !== Node.ELEMENT_NODE && node.nodeType !== Node.DOCUMENT_FRAGMENT_NODE) return;
    if (node.nodeType === Node.ELEMENT_NODE) {
      const el = node as Element;
      if (this.skip(el)) return;
      for (const a of ATTRS) if (el.hasAttribute(a)) this.applyAttr(el, a);
    }
    for (let c = node.firstChild; c; c = c.nextSibling) this.walk(c);
  }

  private onMutations(records: MutationRecord[]): void {
    for (const r of records) {
      if (r.type === "characterData") this.applyText(r.target as Text);
      else if (r.type === "attributes" && r.attributeName) this.applyAttr(r.target as Element, r.attributeName);
      else r.addedNodes.forEach((n) => this.walk(n));
    }
  }

  private applyText(node: Text): void {
    const value = node.nodeValue ?? "";
    let rec = this.texts.get(node);
    if (rec && value === rec.shown) {
      if (this.lang === "en" && rec.shown !== rec.original) this.write(node, rec, rec.original);
      else if (this.lang !== "en" && rec.shown === rec.original) this.translateInto(node, rec);
      return;
    }
    if (!rec) {
      if (!/[A-Za-z]/.test(value) || this.skip(node.parentElement)) return;
      rec = { original: value, shown: value };
      this.texts.set(node, rec);
    } else {
      rec.original = value; rec.shown = value;   // React wrote new English text
    }
    if (this.lang !== "en") this.translateInto(node, rec);
  }

  private translateInto(node: Text, rec: TextRecord): void {
    const zh = this.translator.translate(rec.original);
    if (zh !== null && zh !== rec.shown) this.write(node, rec, zh);
  }

  private write(node: Text, rec: TextRecord, value: string): void {
    rec.shown = value;
    node.nodeValue = value;
  }

  private applyAttr(el: Element, name: string): void {
    const value = el.getAttribute(name);
    if (value === null) return;
    let map = this.attrs.get(el);
    let rec = map?.get(name);
    if (rec && value === rec.shown) {
      const want = this.lang === "en" ? rec.original : this.translator.translate(rec.original) ?? rec.original;
      if (want !== value) { rec.shown = want; el.setAttribute(name, want); }
      return;
    }
    if (!/[A-Za-z]/.test(value)) return;
    if (!map) { map = new Map(); this.attrs.set(el, map); }
    rec = { original: value, shown: value };
    map.set(name, rec);
    if (this.lang !== "en") {
      const zh = this.translator.translate(value);
      if (zh !== null) { rec.shown = zh; el.setAttribute(name, zh); }
    }
  }
}
