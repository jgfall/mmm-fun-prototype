#!/usr/bin/env python3
"""Copy a Pencil (.pen) design file into this repo and bundle everything it needs.

Pencil stores image fills and custom fonts as paths relative to the .pen file.
The working copy usually lives in ~/.pencil/documents/<id>/ and points at
assets on the Desktop (e.g. ../../../Desktop/MMM-assets/...). Those paths break
on any other machine. This script:

  1. reads the source .pen (JSON),
  2. copies every local file it references into design/ and rewrites each
     reference to a path relative to design/<name>.pen,
  3. downloads remote images (e.g. Unsplash) into design/assets/remote/ and
     points the file at the local copies,
  4. drops the machine-specific "fileToken",
  5. writes design/<name>.pen,
  6. collects every font family the file uses and bundles the font files:
       - Google Fonts are downloaded as TTF into design/fonts/google/<Family>/
       - local (licensed) families listed in LOCAL_FONTS are copied from the
         system font folders into design/fonts/<foundry>/
       - system fonts that can't be redistributed are reported, not copied.

Usage:
  python3 scripts/sync_design.py                      # default source path
  python3 scripts/sync_design.py "/path/to/file.pen"  # any other source
  python3 scripts/sync_design.py --no-fonts           # skip the font step
"""
import collections
import glob
import hashlib
import json
import os
import re
import shutil
import sys
import urllib.parse
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESIGN = os.path.join(REPO, "design")
OUT_NAME = "mmmfun-screens.pen"
DEFAULT_SRC = os.path.expanduser(
    "~/.pencil/documents/48bf41af-d10f-4d3e-864e-9716b7085b7c/mmmfun screens.pen"
)
DESKTOP = os.path.expanduser("~/Desktop")
PATH_KEYS = ("url", "scriptUri")
FONT_EXT = (".ttf", ".otf", ".woff", ".woff2")
SKIP = ("data:", "pencil:")
FONT_DIRS = [os.path.expanduser("~/Library/Fonts"), "/Library/Fonts"]

# Licensed families that live on the designer's machine rather than Google Fonts.
# Family name -> (destination folder under design/fonts, file glob patterns).
LOCAL_FONTS = {
    "PP Editorial New": ("pangram", ["PPEditorialNew-*", "EditorialNew-*"]),
    "PP Editorial Old": ("pangram", ["PPEditorialOld-*"]),
}
# Always bundle these even if the file doesn't use them yet.
EXTRA_FAMILIES = ["PP Editorial Old"]
# System fonts we can't redistribute or download.
SYSTEM_FONTS = {"Helvetica Neue", "Helvetica", "SF Pro", "SF Pro Display", "Arial"}


def dest_for(abs_path, src_dir):
    """Return the destination (relative to design/) for a local file."""
    name = os.path.basename(abs_path)
    if abs_path.lower().endswith(FONT_EXT):
        return "fonts/" + name
    if abs_path.startswith(DESIGN + os.sep):
        return os.path.relpath(abs_path, DESIGN)
    if abs_path.startswith(src_dir + os.sep):
        return os.path.relpath(abs_path, src_dir)
    if abs_path.startswith(DESKTOP + os.sep):
        return "assets/" + os.path.relpath(abs_path, DESKTOP)
    return "assets/external/" + name


def download(url, target):
    os.makedirs(os.path.dirname(target), exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "mmm-fun-sync/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r, open(target, "wb") as f:
        f.write(r.read())


def remote_dest(url):
    """Stable local name for a remote image."""
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query)
    ext = (query.get("fm") or [""])[0] or os.path.splitext(parsed.path)[1].lstrip(".") or "jpg"
    stem = re.sub(r"[^a-zA-Z0-9-]", "", os.path.basename(parsed.path))[:40] or "image"
    digest = hashlib.sha1(url.encode()).hexdigest()[:8]
    return f"assets/remote/{parsed.netloc.split('.')[0]}-{stem}-{digest}.{ext}"


def font_usage(doc):
    """Map font family -> set of (weight, italic) used anywhere in the file."""
    variables = doc.get("variables", {})

    def resolve(value):
        if isinstance(value, str) and value.startswith("$"):
            var = variables.get(value[1:])
            if not var:
                return set()
            raw = var["value"]
            vals = [x["value"] for x in raw] if isinstance(raw, list) else [raw]
            out = set()
            for v in vals:
                out |= resolve(v)
            return out
        return {value} if isinstance(value, str) else set()

    used = collections.defaultdict(set)

    def walk(node):
        if isinstance(node, dict):
            if "fontFamily" in node:
                w = str(node.get("fontWeight", "400"))
                w = {"normal": "400", "bold": "700"}.get(w, w)
                if not w.isdigit():
                    w = "400"
                italic = node.get("fontStyle") == "italic"
                for fam in resolve(node["fontFamily"]):
                    used[fam].add((int(w), italic))
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for x in node:
                walk(x)

    walk(doc.get("children", []))
    return used


def google_css(family, styles):
    pairs = sorted({(1 if it else 0, w) for w, it in styles})
    axes = ";".join(f"{i},{w}" for i, w in pairs)
    url = ("https://fonts.googleapis.com/css2?family="
           + urllib.parse.quote_plus(family) + ":ital,wght@" + axes)
    req = urllib.request.Request(url, headers={"User-Agent": "mmm-fun-sync/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode()


def fetch_google(family, styles):
    """Download the TTFs for a Google Fonts family. Returns files written."""
    try:
        css = google_css(family, styles)
    except Exception:
        # A requested weight doesn't exist: fall back to one request per style.
        css = ""
        for s in styles:
            try:
                css += google_css(family, {s})
            except Exception:
                pass
    if not css:
        return None
    folder = os.path.join(DESIGN, "fonts", "google", family.replace(" ", ""))
    written = []
    for block in re.findall(r"@font-face\s*{([^}]*)}", css):
        style = re.search(r"font-style:\s*(\w+)", block).group(1)
        weight = re.search(r"font-weight:\s*(\d+)", block).group(1)
        src = re.search(r"url\(([^)]+)\)", block).group(1)
        name = f"{family.replace(' ', '')}-{weight}{'Italic' if style == 'italic' else ''}.ttf"
        target = os.path.join(folder, name)
        if not os.path.isfile(target):
            download(src, target)
        written.append(os.path.relpath(target, REPO))
    return sorted(set(written))


def copy_local_family(family):
    folder, patterns = LOCAL_FONTS[family]
    written = []
    for d in FONT_DIRS:
        for pat in patterns:
            for path in glob.glob(os.path.join(d, pat)):
                if path.lower().endswith(FONT_EXT):
                    target = os.path.join(DESIGN, "fonts", folder, os.path.basename(path))
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    shutil.copy2(path, target)
                    written.append(os.path.relpath(target, REPO))
    return sorted(set(written))


def bundle_fonts(doc):
    used = font_usage(doc)
    for fam in EXTRA_FAMILIES:
        used.setdefault(fam, set())
    print("\nFonts:")
    for fam in sorted(used):
        styles = used[fam] or {(400, False)}
        if fam in LOCAL_FONTS:
            files = copy_local_family(fam)
            note = f"{len(files)} local files" if files else "NOT FOUND in system font folders"
        elif fam in SYSTEM_FONTS:
            note = "system font, not redistributable (skipped)"
        else:
            files = fetch_google(fam, styles)
            note = f"{len(files)} Google Fonts files" if files else "NOT FOUND on Google Fonts"
        print(f"  {fam:24} {note}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    src = os.path.abspath(args[0] if args else DEFAULT_SRC)
    if not os.path.isfile(src):
        sys.exit(f"Source not found: {src}")
    src_dir = os.path.dirname(src)
    doc = json.load(open(src, encoding="utf-8"))

    copied, downloaded, missing, seen = 0, 0, [], {}

    def fix(value):
        nonlocal copied, downloaded
        if not isinstance(value, str) or value.startswith(SKIP):
            return value
        if value in seen:
            return seen[value]
        if value.startswith(("http://", "https://")):
            rel = remote_dest(value)
            target = os.path.join(DESIGN, rel)
            if not os.path.isfile(target):
                try:
                    download(value, target)
                    downloaded += 1
                except Exception as e:
                    missing.append(f"{value}  ({e})")
                    seen[value] = value
                    return value
            seen[value] = rel
            return rel
        abs_path = os.path.normpath(os.path.join(src_dir, value))
        rel = dest_for(abs_path, src_dir)
        target = os.path.join(DESIGN, rel)
        if os.path.isfile(abs_path):
            if os.path.abspath(target) != abs_path:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                shutil.copy2(abs_path, target)
                copied += 1
        elif not os.path.isfile(target):
            missing.append(value)
            seen[value] = value
            return value
        seen[value] = rel
        return rel

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in PATH_KEYS:
                    node[k] = fix(v)
                else:
                    walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(doc)
    doc.pop("fileToken", None)

    os.makedirs(DESIGN, exist_ok=True)
    out = os.path.join(DESIGN, OUT_NAME)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Wrote {os.path.relpath(out, REPO)}")
    print(f"{len(seen)} referenced files: {copied} copied, {downloaded} downloaded")
    if missing:
        print("Missing (left as-is in the file, fix before committing):")
        for m in missing:
            print("  ", m)

    if "--no-fonts" not in sys.argv:
        bundle_fonts(doc)


if __name__ == "__main__":
    main()
