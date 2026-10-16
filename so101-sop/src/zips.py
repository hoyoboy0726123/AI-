"""Zip bundles the page builds in the browser, plus the files they need published."""
import json, pathlib

OFFICIAL_README = """SO-101 official STL files (unmodified copies)

Source: https://github.com/TheRobotStudio/SO-ARM100
Commit: a758567c3978dfeefe282ede0500085a48fe8f78 (2026-10-06)
Paths: STL/SO101/Individual/*.stl and STL/Gauges/*.STL
License: Apache License 2.0, see LICENSE in this folder.
Full print plates (Ender / Prusa / Bambu A1 mini) are in STL/SO101/Follower and STL/SO101/Leader of the source repository.

Individual/ has 15 files. WaveShare_Mounting_Plate_SO101 and Seeedstudio_Mounting_Plate_SO101
are the same part for two driver-board brands: print only the one for your board, so 14 parts per print list.
Individual 資料夾有 15 個檔案。兩個驅動板固定板只印你的驅動板品牌那一個，所以實際要印 14 種。

Gauges/ has 4 files: print Gauge_0 and Gauge_tight_1 if you test with an STS3215 servo,
or the two Lego_Size_Test files if you test with a 4x2 Lego brick. Not both pairs.
Gauges 資料夾有 4 個檔案：用馬達試塞就印 Gauge_0 和 Gauge_tight_1；用樂高積木試塞才印兩個 Lego_Size_Test。
"""


DPAD_README = """SO-101 D-pad fingertips (optional add-on for the follower arm)

Wrist_Roll_Follower_SO101_DPad.stl  replaces the official Wrist_Roll_Follower_SO101 (gripper body); adds a socket under the fixed jaw.
Moving_Jaw_SO101_DPad.stl           replaces the official Moving_Jaw_SO101 (moving jaw); adds a socket under the jaw tip.

Both files are modified copies of the official parts from TheRobotStudio/SO-ARM100 (Apache License 2.0, see LICENSE).
Only the sockets were added. Everything else, including the coordinate frame, is unchanged.
Print: PLA+, same orientation as the official files, supports everywhere. Clean the supports out of the sockets; do not sand the socket end faces.
Pads: 0.5 mm adhesive silicone sheet, Shore A 40-60, about 8 x 3 mm, one on each socket end face, same thickness on both.

這兩個檔案是官方夾爪本體和活動爪，各加上一個套筒，其他部位和座標都沒有改。
只有執行臂要換。這是選配零件，不在階段 A 的 23 件裡。
列印：PLA+，擺放方向和官方原檔相同，支撐全開。套筒裡的支撐要清乾淨，端面不要磨。
墊片：0.5 mm 背膠矽膠片，Shore A 40–60，剪成約 8 × 3 mm，兩個套筒端面各貼一片，厚度要一樣。
"""


def specs(root):
    root = pathlib.Path(root)
    parts = sorted(p for p in (root / "assets/stl").glob("*.stl") if not p.name.endswith("_lite.stl"))
    gauges = sorted((root / "assets/stl/gauges").glob("*"))
    official = {
        "name": "SO-101-official-STL.zip", "folder": "SO-101-official-STL",
        "files": [["assets/stl64/" + p.name + ".txt", "Individual/" + p.name] for p in parts]
               + [["assets/stl64/" + p.name + ".txt", "Gauges/" + p.name] for p in gauges]
               + [["assets/LICENSE-SO-ARM100.txt", "LICENSE"]],
        "text": [["README.txt", OFFICIAL_README]],
    }
    dpad = {
        "name": "SO-101-DPad-tips.zip", "folder": "SO-101-DPad-tips",
        "files": [["assets/stl64/" + p.name + ".txt", p.name] for p in sorted((root / "assets/dpad").glob("*.stl"))]
               + [["assets/LICENSE-SO-ARM100.txt", "LICENSE"]],
        "text": [["README.txt", DPAD_README]],
    }
    out = {"official": official, "dpad": dpad}
    kit = root / "assets/kit.json"
    if kit.exists():
        out["kit"] = json.loads(kit.read_text(encoding="utf-8"))
    return out


def js(root):
    return "window.__SO101_ZIPS = " + json.dumps(specs(root), ensure_ascii=False) + ";\n"


def publish_files(root):
    files = {}
    for spec in specs(root).values():
        for src, _dst in spec["files"]:
            files[src] = src
    return files
