# CLAUDE.md

給在這個 repo 工作的 Claude Code 看的守則。**這個 repo 是公開的**：這份檔案和 repo 裡的任何東西都不能放機密或個人資料。

## 溝通方式

- 一律用繁體中文回覆，語氣親切、多鼓勵。
- 只在這個 repo 的資料夾裡工作，不要動到電腦上的其他資料夾。
- 需要人動手的步驟（接線、插拔、轉關節、示範動作），一次只講一步，等對方回報再講下一步。
- 看不出硬體狀況時，請對方拍照或截圖。

## 資料夾

| 資料夾 | 內容 |
|---|---|
| `so101-sop/` | SO-101 機械手臂中文施工手冊的原始碼，發布在 GitHub Pages 的 `so101/` |
| `lelab-zh/` | 官方 LeLab 原始碼（git subtree），加上我們的中文／EN 切換外掛 |
| `app/`、`main.py`、`tests/`、`docs/` | 另一個專案（Office 自動化工具），和手臂無關，沒被要求就不要改 |

`lelab-zh/CLAUDE.md` 是 LeLab 官方給開發者的說明。我們自己的外掛怎麼維護，看 `lelab-zh/I18N.zh-TW.md`。

## 設備

| 項目 | 內容 |
|---|---|
| 執行臂（Follower） | 6 顆 STS3215 **12V**（C018 或 C047），用 **12V** 電源 |
| 主控臂（Leader） | STS3215 **7.4V**：ID 1、3 是 C044，ID 2 是 C001，ID 4–6 是 C046；一律用 **5V** 電源 |
| 驅動板 | 兩塊，各接一隻手臂。Waveshare 款的跳線帽要放在 B |
| 校準檔名稱 | 執行臂 `my_awesome_follower_arm`，主控臂 `my_awesome_leader_arm` |
| 校準檔位置 | `~/.cache/huggingface/lerobot/calibration/robots/so_follower/`、`.../teleoperators/so_leader/` |
| LeLab 手臂名稱 | `so101`；攝影機名稱 `front`（桌面）、`wrist`（手腕），640×480、30 fps |
| 力感測 | TAL221 荷重元 → HX711 → Arduino Nano，程式 `so101-sop/assets/force/force_probe.py` |
| 訓練電腦 | 筆電，RTX 5090 筆電版（24 GB） |

連接埠（例如 `COM3`、`COM4`）每台電腦不一樣，USB 重插也可能變。用之前先執行 `lerobot-find-port` 確認，不要直接沿用舊的。

## 安全規則（一定要遵守）

Claude 下指令後看不到手臂的即時動作，也沒辦法在幾毫秒內停手。所以停止條件必須寫在程式裡，人也必須在現場。

**可以直接執行（手臂不會動）：**
- `nvidia-smi`、`lerobot-find-port`、`lerobot-find-cameras opencv`
- 啟動 `lelab`
- `force_probe.py` 的 `monitor`、`tare`、`cal`、`raw`
- 建置手冊、跑測試

**執行前一定要先問，得到同意才執行：**
- `lerobot-setup-motors`：會把 ID 寫進馬達，一次只能接一顆。
- `lerobot-calibrate`：會寫入校準。
- 會讓手臂動的指令：`lerobot-teleoperate`、`lerobot-record`、`lerobot-replay`、推論（讓 AI 操作）、`force_probe.py push`。
- 任何連上手臂並送出動作的 Python 程式。
- 呼叫 LeLab 開始遙控、重播、推論的 API。

問的時候要講清楚三件事：手臂會怎麼動、範圍多大、要有人站在旁邊並把手放在執行臂的電源旁。

**每次讓手臂動之前：**
- 確認執行臂接 12V、主控臂接 5V。
- 確認同一個連接埠沒有被其他程式用著（例如 LeLab 正在遙控）。
- 新寫的動作程式依序試：先關扭力空跑 → 低速、短行程 → 才跑正常速度。
- 讓 AI 操作（推論）時，第一次把最長時間設 20 秒以下。

**按壓和力量控制：**
- 一定要有目標力量和上限（`--target`、`--limit`）。
- 感測器沒有讀數、讀到負值、或行程超過上限時，程式要自己停。`force_probe.py` 已經做好這些，新程式要照同樣的做法。

**沒有明確要求就不要做：**
- 改馬達 EEPROM 參數（扭力上限、ID 等）。手冊流程裡的 setup-motors 和校準除外。
- 更新馬達韌體。
- 叫人對調電源。

## 常用指令

LeRobot 指令在 conda 環境裡跑：Windows 開 Miniforge Prompt，先執行 `conda activate lerobot`。這個環境的 LeRobot 版本和 LeLab 內建的（0.7.0）可能不同，參數名稱也可能不同，第一次用某個指令先看 `--help`。

```bash
lerobot-find-port
lerobot-calibrate --robot.type=so101_follower --robot.port=COM3 --robot.id=my_awesome_follower_arm
lerobot-teleoperate --robot.type=so101_follower --robot.port=COM3 --robot.id=my_awesome_follower_arm \
    --teleop.type=so101_leader --teleop.port=COM4 --teleop.id=my_awesome_leader_arm
lerobot-find-cameras opencv          # 會把每支攝影機的照片存在 outputs/captured_images，可以打開來看畫面
python so101-sop/assets/force/force_probe.py monitor --port COM5
```

LeLab（中文版）：

```bash
lelab                 # 啟動，瀏覽器打開 http://127.0.0.1:8000
lelab --stop          # 出現 port 8000 is already in use 時
uv tool install --force --reinstall-package lelab --torch-backend auto --with-executables-from huggingface_hub ./lelab-zh   # 更新
```

- RTX 50 系列要 CUDA 12.8 以上的 PyTorch。`lelab` 啟動時出現 `NVIDIA GPU detected but PyTorch can't use CUDA`，就照手冊 T-04 重裝。
- 訓練步數 ≈ 總影格數（片段數 × 每段秒數 × 30）÷ 批次大小 × 5 到 10。

## 手冊（so101-sop）

- 內容在 `so101-sop/src/content_*.html`，每一步是一個 `<article class="step">`，編號像 `A-10`、`T-03`。
- 建置：在 `so101-sop` 執行 `python3 src/build.py`（輸出 `dist/index.html`）和 `python3 src/tools/build_pages.py`（輸出 `site/`）。
- 發布：把 `site/` 整個複製到 `gh-pages` 分支的 `so101/` 再推上去。推之前確認只改到 `so101/`。
- 寫作方式：跟著現有章節的風格，按鈕名稱照畫面寫，數字和指令都要查證過官方來源，查不到就說查不到。
- 公司提供的 D-pad 原始 CAD 檔和從裡面量出的尺寸是**機密**：不能放進這個 repo，也不能上傳到任何外部服務。公開手冊只放兩個 D-pad 指尖 STL 和列印、換裝說明。

## 中文版 LeLab（lelab-zh）

- 官方程式碼不要改。翻譯在 `frontend/src/i18n/zh-TW.json`，外掛只新增檔案，再加上 `frontend/src/main.tsx` 第一行的 import。
- 拉官方更新：`python lelab-zh/zh-tools/update_from_upstream.py`，然後照它列出的字串補翻譯。
- 檢查：在 `lelab-zh/frontend` 執行 `npm ci`、`node scripts/i18n-check.mjs`、`npx vitest run src/i18n`、`npx vite build`。
- 要送給官方的 PR 放在 `lelab-zh/zh-tools/upstream-pr/`。
- 用詞：主控臂、執行臂、遙控、校準、資料集、片段、歸位、策略模型、推論、檢查點、工作、連接埠。關節名稱、檔名、模型名稱保留英文。

## Git

- 在 `claude/project-review-sos0lj` 分支上工作。推到 `main`、強制推送、改寫歷史之前，都要先問。
- 不要把 `node_modules/`、`dist/`、`site/`、訓練輸出、資料集或大型檔案加進 git。
