# SO-101 施工手冊

零基礎也能照著做的 SO-101 開源機械手臂手冊，分三個階段：

1. 階段 A：單臂，也就是執行臂
2. 階段 B：力感測，TAL221 500 g 荷重元 + HX711 + Arduino Nano
3. 階段 C：雙臂，做主控臂來遙控執行臂

## 資料夾內容

| 路徑 | 內容 |
|---|---|
| `src/content_*.html` | 手冊各章節內文 |
| `src/app.js`、`src/scenes2.js`、`src/scenes3.js` | GSAP 動畫、3D 檢視器、zip 下載 |
| `src/widgets.py`、`src/zips.py`、`src/build.py` | 組裝網頁用的程式 |
| `index.html` | 網頁樣板與樣式 |
| `assets/stl/` | 官方 SO-ARM100 STL 原檔，Apache-2.0 |
| `assets/img/` | 官方照片與零件算繪圖 |
| `assets/force/` | 力感測：Arduino 韌體、`force_probe.py`、治具 STL 與 OpenSCAD 原始檔 |
| `assets/scripts/first_move.py` | 第一次用 Python 控制手臂 |

## 產生網頁

```bash
python3 src/build.py
```

輸出在 `dist/index.html`。`assets/stl64/` 是 STL 的 base64 版本，網頁用它載入 3D 模型，`build.py` 會自動產生。

## 驗證狀態

- 官方 STL 下載網址都實際下載過；LeRobot 指令與 Python 類別對照 LeRobot 0.6.2 原始碼。
- Arduino 韌體用 arduino-cli 對 `arduino:avr:nano` 編譯成功；`force_probe.py` 在模擬環境測過。
- 韌體、程式和治具都還沒有在實體硬體上測試。治具的孔位請先用游標卡尺量過荷重元再印。

## 組裝步驟圖

`assets/asm/` 和 `assets/img/asm/` 是從官方 URDF 模型產生的，重新產生的方法：

```bash
pip install numpy fast-simplification
python3 src/tools/gen_assembly.py <SO-ARM100>/Simulation/SO101
W=720 H=540 node src/tools/asm_render.js src/tools/asm_render_jobs.json
```

第二個指令需要 Node 的 playwright，以及 three.js 0.147.0 的檔案，用 `LIB` 環境變數指定 three 所在的資料夾。
