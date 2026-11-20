// @vitest-environment jsdom
// Tests for the zh-TW add-on: dictionary sanity, string translation, and the DOM layer
// staying correct while React re-renders.
import React, { act, useState } from "react";
import { createRoot, Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, test } from "vitest";
import dict from "./zh-TW.json";
import { DomTranslator, Translator, normalize, type Dictionary } from "./translator";

const tick = () => new Promise((r) => setTimeout(r, 0));
const translator = new Translator(dict as Dictionary);

describe("dictionary", () => {
  test("keys are normalized and values are strings", () => {
    for (const [k, v] of Object.entries(dict.strings)) {
      expect(k).toBe(normalize(k));
      expect(typeof v).toBe("string");
    }
  });
  test("patterns compile and use only captured groups", () => {
    for (const [re, rep] of dict.patterns as [string, string][]) {
      const groups = new RegExp(re + "|").exec("")!.length - 1;
      for (const m of rep.matchAll(/\$(\d)/g)) expect(+m[1]).toBeLessThanOrEqual(groups);
    }
  });
});

describe("Translator", () => {
  test("translates whole strings and keeps outer spaces", () => {
    expect(translator.translate("Start Calibration")).toBe("開始校準");
    expect(translator.translate("  Start   Calibration ")).toBe(" 開始校準 ");
  });
  test("leaves unknown text, numbers and user data alone", () => {
    expect(translator.translate("so101_dpad_up")).toBeNull();
    expect(translator.translate("2540")).toBeNull();
    expect(translator.translate("Start Calibration now")).toBeNull();
  });
  test("patterns fill in values and translate known values", () => {
    expect(translator.translate('Create "so101"')).toBe("建立「so101」");
    expect(translator.translate("Calibration started for teleop")).toBe("已開始校準：主控臂");
    expect(translator.translate("Episode 3 of 10")).toBe("第 3 段，共 10 段");
  });
});

describe("DomTranslator with React", () => {
  let host: HTMLDivElement;
  let root: Root;
  let dom: DomTranslator;
  let setLabel: (s: string) => void = () => {};

  function Probe() {
    const [label, set] = useState("Start Calibration");
    setLabel = set;
    return (
      <div>
        <button type="button" title="Delete robot">{label}</button>
        <input placeholder="Search jobs" defaultValue="Ready" />
        <span data-no-i18n="">Ready</span>
        <p>Recording with <strong>so101</strong></p>
      </div>
    );
  }

  beforeEach(async () => {
    Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
    host = document.createElement("div");
    document.body.appendChild(host);
    dom = new DomTranslator(translator, host);
    dom.start("zh-TW");
    root = createRoot(host);
    await act(async () => root.render(<Probe />));
    await tick();
  });
  afterEach(() => { act(() => root.unmount()); dom.stop(); host.remove(); });

  test("renders Chinese text and attributes", () => {
    expect(host.querySelector("button")!.textContent).toBe("開始校準");
    expect(host.querySelector("button")!.getAttribute("title")).toBe("刪除手臂");
    expect(host.querySelector("input")!.getAttribute("placeholder")).toBe("搜尋工作");
    expect(host.querySelector("p")!.textContent).toBe("使用手臂：so101");
  });

  test("does not touch input values or opted-out elements", () => {
    expect(host.querySelector("input")!.value).toBe("Ready");
    expect(host.querySelector("span")!.textContent).toBe("Ready");
  });

  test("follows React updates and switches both ways", async () => {
    await act(async () => setLabel("Cancel Calibration"));
    await tick();
    expect(host.querySelector("button")!.textContent).toBe("取消校準");

    dom.setLanguage("en");
    await tick();
    expect(host.querySelector("button")!.textContent).toBe("Cancel Calibration");
    expect(host.querySelector("button")!.getAttribute("title")).toBe("Delete robot");
    expect(host.querySelector("input")!.getAttribute("placeholder")).toBe("Search jobs");

    await act(async () => setLabel("Save Calibration"));
    await tick();
    expect(host.querySelector("button")!.textContent).toBe("Save Calibration");

    dom.setLanguage("zh-TW");
    await tick();
    expect(host.querySelector("button")!.textContent).toBe("儲存校準");
    expect(host.querySelector("p")!.textContent).toBe("使用手臂：so101");
  });

  test("text React adds later is translated too", async () => {
    const extra = document.createElement("div");
    extra.textContent = "Teleoperation Started";
    host.appendChild(extra);
    await tick();
    expect(extra.textContent).toBe("已開始遙控");
  });
});
