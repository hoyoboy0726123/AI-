"""Zip bundles the page builds in the browser, plus the files they need published."""
import json, pathlib

OFFICIAL_README = """SO-101 official STL files (unmodified copies)

Source: https://github.com/TheRobotStudio/SO-ARM100
Commit: a758567c3978dfeefe282ede0500085a48fe8f78 (2026-10-06)
Paths: STL/SO101/Individual/*.stl and STL/Gauges/*.STL
License: Apache License 2.0, see LICENSE in this folder.
Full print plates (Ender / Prusa / Bambu A1 mini) are in STL/SO101/Follower and STL/SO101/Leader of the source repository.
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
    out = {"official": official}
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
