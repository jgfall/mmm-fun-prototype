#!/usr/bin/env python3
"""Copy a Pencil (.pen) design file into this repo and make it portable.

Pencil stores image fills and custom fonts as paths relative to the .pen file.
The working copy usually lives in ~/.pencil/documents/<id>/ and points at
assets on the Desktop (e.g. ../../../Desktop/MMM-assets/...). Those paths break
on any other machine. This script:

  1. reads the source .pen (JSON),
  2. copies every local file it references into design/,
  3. rewrites each reference to a path relative to design/<name>.pen,
  4. drops the machine-specific "fileToken",
  5. writes design/<name>.pen.

Font files (.ttf/.otf/.woff/.woff2) are copied into design/fonts/, which is
gitignored, because the fonts we use are commercially licensed and the repo
is public.

Usage:
  python3 scripts/sync_design.py                      # default source path
  python3 scripts/sync_design.py "/path/to/file.pen"  # any other source
"""
import json
import os
import shutil
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESIGN = os.path.join(REPO, "design")
OUT_NAME = "mmmfun-screens.pen"
DEFAULT_SRC = os.path.expanduser(
    "~/.pencil/documents/48bf41af-d10f-4d3e-864e-9716b7085b7c/mmmfun screens.pen"
)
DESKTOP = os.path.expanduser("~/Desktop")
PATH_KEYS = ("url", "scriptUri")
FONT_EXT = (".ttf", ".otf", ".woff", ".woff2")
REMOTE = ("http://", "https://", "data:", "pencil:")


def dest_for(abs_path, src_dir):
    """Return the repo-relative destination (relative to design/) for a file."""
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


def main():
    src = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SRC)
    if not os.path.isfile(src):
        sys.exit(f"Source not found: {src}")
    src_dir = os.path.dirname(src)
    doc = json.load(open(src, encoding="utf-8"))

    copied, missing, seen = 0, [], {}

    def fix(value):
        nonlocal copied
        if not isinstance(value, str) or value.startswith(REMOTE):
            return value
        if value in seen:
            return seen[value]
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
    print(f"{len(seen)} referenced files, {copied} copied")
    if missing:
        print("Missing (left as-is in the file, fix before committing):")
        for m in missing:
            print("  ", m)


if __name__ == "__main__":
    main()
