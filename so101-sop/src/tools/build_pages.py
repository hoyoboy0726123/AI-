"""Build a standalone static site for GitHub Pages: so101-sop/site/

usage: python3 src/tools/build_pages.py

Runs src/build.py, wraps dist/index.html in a full HTML document and copies
every file the page loads (images, base64 STLs, kit sources) next to it.
"""
import pathlib, re, shutil, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import zips  # noqa: E402

SITE = ROOT / "site"
DESC = "SO-101 開源機械手臂零基礎施工手冊：單臂、力感測、雙臂，含 STL 下載、3D 組裝圖與動畫步驟。"
RESET = ("<style>body{margin:0}img{max-width:100%}[hidden]{display:none!important}"
         ":root{color-scheme:light}</style>")


def site_files(html):
    """published path -> source path, for everything the page and its zip bundles fetch."""
    files = {}
    for p in sorted((ROOT / "assets/stl64").glob("*.txt")):
        files[str(p.relative_to(ROOT))] = p
    for m in sorted(set(re.findall(r'(?:src|href)="(assets/[^"]+)"', html))):
        files[m] = ROOT / m
    for k in zips.publish_files(ROOT):
        src = ROOT / k
        files[k] = src if src.exists() else ROOT / k[: -len(".txt")]  # kit sources are served as .txt
    for k, src in files.items():
        assert src.exists(), k
    return files


def main():
    subprocess.run([sys.executable, str(ROOT / "src/build.py")], check=True)
    html = (ROOT / "dist/index.html").read_text(encoding="utf-8")
    cut = html.index('<div class="wrap">')
    page = ('<!doctype html>\n<html lang="zh-Hant">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
            f'<meta name="description" content="{DESC}">\n{RESET}\n'
            + html[:cut] + "\n</head>\n<body>\n" + html[cut:] + "\n</body>\n</html>\n")
    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir()
    (SITE / "index.html").write_text(page, encoding="utf-8")
    files = site_files(html)
    for doc in sorted((ROOT / "docs").glob("*.docx")):  # documents linked from the page
        files["docs/" + doc.name] = doc
    for dst, src in files.items():
        out = SITE / dst
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, out)
    size = sum(p.stat().st_size for p in SITE.rglob("*") if p.is_file())
    print(f"site: {len(files) + 1} files, {size / 1e6:.1f} MB -> {SITE}")


if __name__ == "__main__":
    main()
