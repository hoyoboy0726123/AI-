# Interface translations

LeLab can show its interface in Traditional Chinese (`zh-TW`). A floating **中文 / EN** button sits above the `?` help button on every page. The choice is saved in `localStorage` (`lelab.lang`). Browsers set to Traditional Chinese (`zh-TW`, `zh-HK`, `zh-MO`, `zh-Hant`) start in Chinese; everyone else starts in English.

## How it works

Components keep their English strings; nothing in them changes. `translator.ts` watches the rendered page with a `MutationObserver` and replaces any text node, `placeholder`, `title`, `aria-label` or `alt` whose whole text is a key in `zh-TW.json`. When React re-renders a node with new English text, the observer translates it again. Switching back to English restores the original text.

Not translated: input values, `<code>`, `<pre>`, `<kbd>`, `<textarea>`, and anything inside an element with `data-no-i18n`. Joint names, file names, robot and dataset names, and model names (ACT, SmolVLA, ...) stay in English on purpose.

A string with no translation simply stays in English, so new UI text never breaks anything.

## Files

| File                           | Purpose                                                                                                                                                                                                                             |
| ------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `zh-TW.json`                   | `strings`: exact English → Chinese. `patterns`: regex → replacement for text built from variables, such as `Create "so101"`; captured values are translated too when they are keys. `ignore`: strings deliberately left in English. |
| `translator.ts`                | String lookup and the DOM translator.                                                                                                                                                                                               |
| `index.ts`                     | Starts the translator and adds the toggle button. Imported once from `main.tsx`.                                                                                                                                                    |
| `i18n.test.tsx`                | Tests for the dictionary, string lookup, and React re-renders.                                                                                                                                                                      |
| `../../scripts/i18n-check.mjs` | Extracts UI strings from `src/` with the TypeScript parser and lists those missing from `zh-TW.json`.                                                                                                                               |

## After changing UI text

```bash
npm run i18n:check            # lists strings not in zh-TW.json yet
npm run i18n:check -- --stale # also lists dictionary entries no longer in the source
npx vitest run src/i18n
```

Add each missing string to `strings` in `zh-TW.json`. If a string is built from variables, add a regex to `patterns` instead. If it should stay in English, add it to `ignore`.

## Terms used in zh-TW

| English               | 中文     |
| --------------------- | -------- |
| Leader / Teleoperator | 主控臂   |
| Follower / Robot      | 執行臂   |
| Teleoperation         | 遙控     |
| Calibration           | 校準     |
| Dataset               | 資料集   |
| Episode               | 片段     |
| Reset (time)          | 歸位     |
| Policy                | 策略模型 |
| Inference             | 推論     |
| Checkpoint            | 檢查點   |
| Job                   | 工作     |
| Port                  | 連接埠   |
