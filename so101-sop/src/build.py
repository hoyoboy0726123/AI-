"""Assemble the SOP page: template + content sections + scripts -> dist/index.html."""
import pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import widgets

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
tpl = (ROOT / "index.html").read_text(encoding="utf-8")
parts = sorted(SRC.glob("content_*.html"))
content = "\n".join(p.read_text(encoding="utf-8") for p in parts)
scripts = "\n".join((SRC / n).read_text(encoding="utf-8") for n in ["app.js", "scenes2.js", "scenes3.js"] if (SRC / n).exists())
if "</script" in scripts.lower():
    sys.exit("script text contains a closing script tag")
content = re.sub(r"<!--ANIM:(\w+)-->", lambda m: widgets.anim(m.group(1)), content)
content = re.sub(r"<!--VIEWER:(\w+)(?::([^>]+))?-->", lambda m: widgets.viewer(m.group(1), m.group(2)), content)
content = re.sub(r"<!--CODE:([^>]+)-->", lambda m: widgets.code(m.group(1), ROOT), content)
content = re.sub(r"<!--PARTS:([^>]+)-->", lambda m: widgets.parts(m.group(1)), content)
left = re.findall(r"<!--(?:ANIM|VIEWER|FILL|PARTS|CODE)[^>]*-->", content)
if left: print("unresolved placeholders:", left)
out = tpl.replace("<!--CONTENT-->", content).replace("/*SCRIPT*/", scripts)
dist = ROOT / "dist"
dist.mkdir(exist_ok=True)
(dist / "index.html").write_text(out, encoding="utf-8")
ids = re.findall(r'\bid="([^"]+)"', out)
dups = sorted({i for i in ids if ids.count(i) > 1})
print("wrote", dist / "index.html", len(out.encode("utf-8")), "bytes;", len(parts), "content parts")
print("duplicate ids:", dups or "none")
