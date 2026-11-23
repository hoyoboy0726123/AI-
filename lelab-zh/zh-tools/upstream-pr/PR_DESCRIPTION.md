Title: feat(i18n): add Traditional Chinese interface with a 中文/EN toggle

## What

Adds a Traditional Chinese (zh-TW) interface to LeLab with a one-click **中文 / EN** button. The button floats above the `?` help button on every page, and the choice is saved in `localStorage`. Browsers set to Traditional Chinese (`zh-TW`, `zh-HK`, `zh-MO`, `zh-Hant`) start in Chinese; everyone else still starts in English, so nothing changes for existing users.

I searched the issues and the 137 existing PRs and found no earlier i18n or Chinese work.

## How

No component is edited. `frontend/src/i18n/translator.ts` watches the rendered page with a `MutationObserver` and swaps any text node or `placeholder` / `title` / `aria-label` / `alt` whose whole text is a key in `zh-TW.json`. When React re-renders a node with new English text, it translates it again. Switching back restores the original text.

I chose this over wrapping every string in `t()` for three reasons:

- **Small diff.** The PR touches one line of `main.tsx`, one `package.json` script and the README. Everything else is new files, so it cannot conflict with the open PRs.
- **New UI text is safe.** A string without a translation stays in English, so it never breaks.
- **Easy to keep up to date.** `npm run i18n:check` uses the TypeScript parser to list UI strings in `src/` that are not in the dictionary yet.

Coverage right now: 798 UI strings extracted. 747 are translated, plus 60 patterns for text built from variables (e.g. `Create "so101"`, `Episode 3 of 10`, `started 25m ago`). The remaining strings are deliberately left in English: product and model names, CSS values, code. Common backend status messages are translated too. Joint names, file names and model names stay in English on purpose.

If you would rather have a `react-i18next` / `t()` approach, I am happy to rework it. The dictionary would carry over as-is.

## Files

- `frontend/src/i18n/translator.ts`: string lookup plus the DOM translator.
- `frontend/src/i18n/index.ts`: starts it and adds the toggle button. Imported once from `main.tsx`.
- `frontend/src/i18n/zh-TW.json`: the dictionary (`strings`, `patterns`, `ignore`).
- `frontend/src/i18n/i18n.test.tsx`: 9 tests covering dictionary sanity, lookup, and React re-renders switching both ways.
- `frontend/scripts/i18n-check.mjs`: coverage check, run as `npm run i18n:check`.
- `frontend/src/i18n/README.md`: how it works, how to add strings, terminology table.

No new dependencies. The checker uses the `typescript` package that is already a devDependency.

## Testing

- `npm ci && npm test && npm run build` pass: 18 test files and 67 tests, 9 of them new.
- `pre-commit run` passes on all changed files.
- `npx eslint src/i18n scripts` passes.
- I checked every main screen in Chinese: landing, robot setup, calibration (idle and recording ranges), teleoperation with the 3D view, the recording dialog, and training. I also toggled back and forth, including after a reload.

## Screenshots

<!-- drag the three screenshots from this folder here: landing, calibration, teleoperation -->

The translations were drafted with Claude Code. A review from another Traditional Chinese speaker is very welcome.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
