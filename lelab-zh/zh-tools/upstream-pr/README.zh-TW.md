# 把中文介面貢獻給官方 LeLab

這個資料夾放的是要送給官方 [huggingface/leLab](https://github.com/huggingface/leLab) 的 Pull Request（PR）。
送出要用你自己的 GitHub 帳號，大約 10 分鐘。

| 檔案 | 用途 |
|---|---|
| `lelab-zh-TW.patch` | 程式修改，已確認可以直接套用在官方最新版（commit 1894ab5） |
| `commit-message.txt` | commit 訊息 |
| `PR_DESCRIPTION.md` | PR 的標題和內文（英文），直接複製貼上 |
| `screenshot-*.png` | 貼在 PR 裡的截圖 |

## 步驟

1. **Fork。** 登入 GitHub，打開 https://github.com/huggingface/leLab ，按右上角的 **Fork**，建立 `你的帳號/leLab`。

2. **套用修改。** 在終端機切到放 `AI-` 資料夾的那一層（也就是手冊 L-01 執行 `git clone` 的地方），執行下面的指令，把 `你的帳號` 換成你的 GitHub 帳號：

   ```bash
   git clone https://github.com/你的帳號/leLab.git
   cd leLab
   git checkout -b feat/zh-tw-ui-toggle
   git apply ../AI-/lelab-zh/zh-tools/upstream-pr/lelab-zh-TW.patch
   git add -A
   git commit -F ../AI-/lelab-zh/zh-tools/upstream-pr/commit-message.txt
   git push -u origin feat/zh-tw-ui-toggle
   ```

3. **開 PR。** 打開 `https://github.com/你的帳號/leLab`，畫面上方會出現 **Compare & pull request**，按下去。
   - 確認方向是 `huggingface/leLab` 的 `main` ← `你的帳號/leLab` 的 `feat/zh-tw-ui-toggle`。
   - 標題和內文複製 `PR_DESCRIPTION.md`（第一行是標題）。
   - 把三張 `screenshot-*.png` 拖進內文的 Screenshots 段落。
   - 按 **Create pull request**。

4. **之後。** 官方回覆時，GitHub 會寄信通知你。把留言轉給我，我幫你看要怎麼改、怎麼回。

## 送出前可以自己先看一眼

PR 會用你的名義公開。建議先用中文版 LeLab 把幾個主要畫面看過一遍（手冊 L-01 有安裝方式），覺得哪個翻譯不順就先告訴我改。

## 如果官方收下了

官方版本身就會有中文切換，我們的 `lelab-zh` 就可以改回直接安裝官方版，不用再自己維護。
