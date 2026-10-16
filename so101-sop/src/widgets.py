"""Markup generators for animated figures and 3D viewers used by build.py."""
import html

ANIMS = {
    "print": {"vb": "0 0 680 340", "title": "列印前準備與切片設定", "steps": [
        "清潔平台，薄塗一層膠", "印量規，用馬達試塞", "照官方設定印整盤零件", "拆掉所有支撐材料"]},
    "chain": {"vb": "0 0 680 330", "title": "電源、USB 與馬達串接", "steps": [
        "驅動板接上電源與 USB-C", "6 顆馬達與關節的 ID 對應", "用 3-pin 線把馬達一顆接一顆串起來", "訊號從驅動板一路傳到夾爪"]},
    "motorid": {"vb": "0 0 680 310", "title": "設定 6 顆馬達的 ID", "steps": [
        "驅動板接上電源與 USB-C，在電腦執行設定指令", "照畫面提示一次只接一顆馬達，按 Enter 寫入 ID", "6 顆馬達都完成"]},
    "forcewire": {"vb": "0 0 720 330", "title": "荷重元、HX711、Arduino Nano 接線", "steps": [
        "認識三個零件", "荷重元的 4 條線接到 HX711", "HX711 接到 Arduino Nano，Nano 用 USB 接電腦", "Nano 把讀數傳到電腦"]},
    "jig": {"vb": "0 0 720 340", "title": "治具組裝", "steps": [
        "荷重元有線的那一端，用 2 顆 M3×10 鎖在舌片上", "沒有線的那一端，裝上推頭", "細線穿過固定柱，不讓線受力", "夾爪夾住治具座，再用束帶綁住兩根爪"]},
    "calibrate": {"vb": "0 0 680 330", "title": "校準流程", "steps": [
        "上臂朝上、前臂朝前，擺到中間位置，按 Enter", "除了手腕旋轉，每個關節慢慢轉到兩端", "全部轉完，按 Enter 存檔"]},
    "teleop": {"vb": "0 0 680 330", "title": "雙臂遙控", "steps": [
        "兩隻手臂都用 USB 接上同一台電腦", "用手帶動主控臂，執行臂同步跟著動"]},
    "weights": {"vb": "0 0 680 340", "title": "砝碼校正", "steps": [
        "不放東西，先歸零", "依序放 1、10、50、100、200 g 砝碼，記下讀數", "讀數要連成一條直線"]},
    "push": {"vb": "0 0 680 330", "title": "用力量控制推蘑菇頭", "steps": [
        "手臂帶著治具慢慢接近蘑菇頭", "接觸後一點一點推，讀數上升", "到達目標力量立刻停止"]},
}

VIEWERS = {
    "parts": {"base": "assets/stl64/", "hint": "拖曳旋轉　滾輪或雙指縮放", "groups": [
        ("共用零件", [
            ("Base_SO101.stl", "底座", "執行臂、主控臂都要"),
            ("Base_motor_holder_SO101.stl", "馬達 1 固定座", "執行臂、主控臂都要"),
            ("Motor_holder_SO101_Base.stl", "馬達 2 固定座", "執行臂、主控臂都要"),
            ("Rotation_Pitch_SO101.stl", "肩部零件", "執行臂、主控臂都要"),
            ("Upper_arm_SO101.stl", "上臂", "執行臂、主控臂都要"),
            ("Under_arm_SO101.stl", "前臂", "執行臂、主控臂都要"),
            ("Motor_holder_SO101_Wrist.stl", "馬達 4 固定座", "執行臂、主控臂都要"),
            ("Wrist_Roll_Pitch_SO101.stl", "手腕座", "執行臂、主控臂都要"),
            ("WaveShare_Mounting_Plate_SO101.stl", "驅動板固定板 Waveshare", "依驅動板品牌二選一"),
            ("Seeedstudio_Mounting_Plate_SO101.stl", "驅動板固定板 Seeed", "依驅動板品牌二選一"),
        ]),
        ("執行臂專用", [
            ("Wrist_Roll_Follower_SO101.stl", "夾爪本體", "只有執行臂"),
            ("Moving_Jaw_SO101.stl", "活動爪", "只有執行臂"),
        ]),
        ("主控臂專用", [
            ("Wrist_Roll_SO101.stl", "主控臂手腕座", "只有主控臂"),
            ("Handle_SO101.stl", "握把", "只有主控臂"),
            ("Trigger_SO101.stl", "扳機", "只有主控臂"),
        ]),
    ]},
    "plates": {"base": "assets/stl64/", "hint": "官方 Bambu A1 mini 列印盤排版，減面後", "groups": [
        ("列印盤", [("BambuLabA1mini_Follower_SO101_lite.stl", "執行臂整盤", "階段 A 列印"),
                    ("BambuLabA1mini_Leader_SO101_lite.stl", "主控臂整盤", "階段 C 列印")]),
    ]},
    "jig": {"base": "assets/stl64/", "hint": "本手冊設計的治具，已轉成列印方向", "groups": [
        ("力感測治具", [("probe_block.stl", "治具座", "夾在夾爪裡，PLA 或 PETG"),
                        ("probe_tip.stl", "推頭", "鎖在荷重元沒有線的那一端")]),
    ]},
    "dpad": {"base": "assets/stl64/", "hint": "拖曳旋轉　滾輪或雙指縮放", "groups": [
        ("D-pad 指尖", [("Wrist_Roll_Follower_SO101_DPad.stl", "夾爪本體 + 套筒", "取代官方夾爪本體"),
                        ("Moving_Jaw_SO101_DPad.stl", "活動爪 + 套筒", "取代官方活動爪")]),
    ]},
    "overview": {"base": "assets/stl64/", "hint": "拖曳旋轉　滾輪或雙指縮放", "groups": [
        ("完整手臂", [("SO101_Assembly_lite.stl", "SO-101 組裝完成", "官方組裝模型，減面後")]),
    ]},
}


def anim(name):
    a = ANIMS[name]
    steps = "".join(f"<li>{html.escape(s)}</li>" for s in a["steps"])
    return (
        f'<figure class="anim" data-scene="{name}">'
        f'<div class="stage"><svg viewBox="{a["vb"]}" role="img" aria-label="{html.escape(a["title"])}"></svg></div>'
        f'<div class="ctrl"><button class="btn primary" type="button" data-act="play">從頭播放</button>'
        f'<button class="btn" type="button" data-act="prev">上一步</button>'
        f'<button class="btn" type="button" data-act="next">下一步</button><span class="sp"></span></div>'
        f'<ol class="steps">{steps}</ol>'
        f'<figcaption style="padding:0 14px 12px">{html.escape(a["title"])}：點步驟可以單獨播放那一段。</figcaption>'
        f"</figure>"
    )


def viewer(name, pressed=None):
    v = VIEWERS[name]
    groups = []
    first = True
    for label, items in v["groups"]:
        btns = []
        for f, lab, use in items:
            on = (pressed == f) if pressed else first
            first = False
            btns.append(
                f'<button type="button" data-file="{html.escape(f)}" data-label="{html.escape(lab)}　{html.escape(f)}" '
                f'data-use="{html.escape(use)}" aria-pressed="{"true" if on else "false"}">{html.escape(lab)}</button>'
            )
        groups.append(f'<div class="grp"><span>{html.escape(label)}</span>{"".join(btns)}</div>')
    return (
        f'<figure class="viewer" data-viewer="{name}" data-base="{v["base"]}">'
        f'<div class="vp"><div class="status">3D 模型會在捲到這裡時載入</div><div class="hint">{html.escape(v["hint"])}</div></div>'
        f'<div class="meta"><span>零件：<b data-meta="name">-</b></span><span>外框尺寸：<b data-meta="size">-</b></span><span><b data-meta="use"></b></span></div>'
        f'<div class="parts">{"".join(groups)}</div>'
        f"</figure>"
    )


NAMES = {f: (lab, use) for v in ("parts", "jig") for _g, items in VIEWERS[v]["groups"] for f, lab, use in items}


def parts(spec):
    """<!--PARTS:file1.stl,file2.stl|note--> -> grid of rendered part images."""
    files, _, note = spec.partition("|")
    cells = []
    for f in [x.strip() for x in files.split(",") if x.strip()]:
        lab, _use = NAMES.get(f, (f, ""))
        png = f.rsplit(".", 1)[0] + ".png"
        cells.append(
            f'<figure class="pimg"><img src="assets/img/parts/{html.escape(png)}" alt="{html.escape(lab)} 的 3D 算繪圖" '
            f'width="800" height="600" loading="lazy"><figcaption><b>{html.escape(lab)}</b><code>{html.escape(f)}</code></figcaption></figure>'
        )
    cap = f'<p class="src" style="margin:0">{html.escape(note)}</p>' if note else ""
    return f'<div class="pgrid">{"".join(cells)}</div>{cap}'


def code(spec, root):
    """<!--CODE:relative/path|caption--> -> copyable code block filled from the file on disk."""
    path, _, cap = spec.partition("|")
    p = root / path.strip()
    if not p.exists():
        return f"<!--FILL:missing {html.escape(path)}-->"
    body = html.escape(p.read_text(encoding="utf-8"))
    return (f'<div class="codeblk"><div class="cap"><span>{html.escape(cap or p.name)}</span>'
            f'<button class="btn" type="button" data-copy>複製</button></div><pre>{body}</pre></div>')


def asm(arm, data):
    """<!--ASM:follower--> -> interactive step-by-step 3D assembly viewer."""
    steps = data["arms"][arm]["steps"]
    btns = "".join(f'<button type="button" data-step="{i}" aria-pressed="false">{i + 1} {html.escape(s["title"])}</button>'
                   for i, s in enumerate(steps))
    return (
        f'<figure class="viewer asmv" data-asm="{arm}">'
        f'<div class="vp"><div class="status">3D 組裝模型會在捲到這裡時載入</div><div class="hint">拖曳旋轉　滾輪或雙指縮放</div></div>'
        f'<div class="asm-cap"><b data-asm-step>組裝順序</b><span data-asm-sub>點下方的步驟，看零件一個一個裝上去。</span></div>'
        f'<div class="ctrl"><button class="btn primary" type="button" data-act="play">播放這一步</button>'
        f'<button class="btn" type="button" data-act="prev">上一步</button><button class="btn" type="button" data-act="next">下一步</button>'
        f'<button class="btn" type="button" data-act="all">看完成的手臂</button></div>'
        f'<ol class="subs"></ol>'
        f'<div class="parts"><div class="grp"><span>組裝順序</span>{btns}</div></div>'
        f'<figcaption class="src" style="padding:0 12px 12px">零件位置取自官方 SO-ARM100 的 URDF 模型，橘色是這一步新裝的零件，深色方塊是馬達。'
        f'動畫只表示零件最後裝在哪裡，實際插入的方向請對照官方影片。</figcaption>'
        f"</figure>"
    )


def asm_step(arm, step_id, data):
    """<!--ASMSTEP:follower:j1--> -> one picture per official sub-step, new parts highlighted."""
    st = next(s for s in data["arms"][arm]["steps"] if s["id"] == step_id)
    cells = []
    for i, sub in enumerate(st["subs"]):
        text = html.escape(sub["text"])
        if sub["parts"]:
            names = "、".join(data["labels"][p] for p in sub["parts"])
            cells.append(
                f'<figure class="asmimg"><img src="assets/img/asm/{arm}_{step_id}_{i}.webp" width="720" height="540" loading="lazy" '
                f'alt="{html.escape(st["title"])} 第 {i + 1} 步：{html.escape(names)} 的位置，橘色標示"><figcaption><b>{i + 1}</b>{text}</figcaption></figure>')
        else:
            cells.append(f'<figure class="asmimg noimg"><div class="ph">{text}</div><figcaption><b>{i + 1}</b>{text}</figcaption></figure>')
    return (f'<div class="asmgrid">{"".join(cells)}</div>'
            f'<p class="src" style="margin:0">圖由官方 URDF 模型算繪，橘色是新裝的零件。手臂擺的是校準時的中間姿勢，組裝時你手上的零件角度可能不同。</p>')
