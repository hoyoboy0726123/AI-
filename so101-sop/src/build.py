"""Assemble the SOP page: template + content sections + scripts -> dist/index.html."""
import base64, json, pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import widgets
import zips

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

# Binary STL is not a served type, so the page loads base64 copies from assets/stl64/.
STL64 = ROOT / "assets/stl64"
STL64.mkdir(exist_ok=True)
for stl in [*(ROOT / "assets/stl").glob("*.stl"), *(ROOT / "assets/stl/gauges").glob("*"), *(ROOT / "assets/force").glob("*.stl"),
            *(ROOT / "assets/asm").glob("*.stl"), *(ROOT / "assets/dpad").glob("*.stl")]:
    out = STL64 / (stl.name + ".txt")
    if not out.exists() or out.stat().st_mtime < stl.stat().st_mtime:
        out.write_text(base64.b64encode(stl.read_bytes()).decode("ascii"), encoding="ascii")
tpl = (ROOT / "index.html").read_text(encoding="utf-8")
parts = sorted(SRC.glob("content_*.html"))
content = "\n".join(p.read_text(encoding="utf-8") for p in parts)
asm_json = (ROOT / "assets/asm/assembly.json").read_text(encoding="utf-8")
scripts = (zips.js(ROOT) + "window.__SO101_ASM = " + asm_json + ";\n"
           + "\n".join((SRC / n).read_text(encoding="utf-8") for n in ["app.js", "scenes2.js", "scenes3.js", "asm.js"] if (SRC / n).exists()))
if "</script" in scripts.lower():
    sys.exit("script text contains a closing script tag")
content = re.sub(r"<!--ANIM:(\w+)-->", lambda m: widgets.anim(m.group(1)), content)
content = re.sub(r"<!--VIEWER:(\w+)(?::([^>]+))?-->", lambda m: widgets.viewer(m.group(1), m.group(2)), content)
content = re.sub(r"<!--CODE:([^>]+)-->", lambda m: widgets.code(m.group(1), ROOT), content)
content = re.sub(r"<!--PARTS:([^>]+)-->", lambda m: widgets.parts(m.group(1)), content)
content = re.sub(r"<!--ASM:(\w+)-->", lambda m: widgets.asm(m.group(1), json.loads(asm_json)), content)
content = re.sub(r"<!--ASMSTEP:(\w+):(\w+)-->", lambda m: widgets.asm_step(m.group(1), m.group(2), json.loads(asm_json)), content)
left = re.findall(r"<!--(?:ANIM|VIEWER|FILL|PARTS|CODE|ASM|ASMSTEP)[^>]*-->", content)
if left: print("unresolved placeholders:", left)
out = tpl.replace("<!--CONTENT-->", content).replace("/*SCRIPT*/", scripts)
dist = ROOT / "dist"
dist.mkdir(exist_ok=True)
(dist / "index.html").write_text(out, encoding="utf-8")
ids = re.findall(r'\bid="([^"]+)"', out)
dups = sorted({i for i in ids if ids.count(i) > 1})
print("wrote", dist / "index.html", len(out.encode("utf-8")), "bytes;", len(parts), "content parts")
print("duplicate ids:", dups or "none")
