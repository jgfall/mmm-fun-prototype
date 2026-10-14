"""Build the prototype from pen.dev HTML exports.

Usage: python3 build.py <export-dir>     (writes mmm-fun-level-up.html next to this file)

The export dir holds one html-css export per frame, named as in SCREENS / MODALS / SEARCH / EXPANDED below.
"""
from bs4 import BeautifulSoup
import re, os, sys, base64, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "exports")
ROOT = os.path.dirname(HERE)

# Screens: export file -> mode (d = desktop 1440, m = mobile 390)
SCREENS = {"p01": "d", "p03": "d", "p05": "d", "p07": "d", "p08": "d", "p09": "d", "p10": "d",
           "mp01": "m", "mp03": "m", "mp05": "m", "mp07": "m", "mp08": "m", "mp09": "m", "mp10": "m"}
# Modals: key, export file, layer-name pattern of the sheet/card, layer-name pattern of its scrim
MODALS = [("m_load", "p02", r"Add USDC Sheet", r"Scrim"),
          ("m_receipt", "p04", r"Receipt", r"Scrim"),
          ("m_l2", "p06", r"Promotion Card", r"Scrim"),
          ("m_l3", "p07u", r"LEVEL 03 .*promotion card", r"Promotion backdrop"),
          ("m_l4", "p08u", r"LEVEL 04 .*promotion card", r"Promotion backdrop"),
          ("m_l5", "p09u", r"LEVEL 05 .*promotion card", r"Promotion backdrop"),
          ("mm_load", "mp02", r"Add USDC Sheet", r"Scrim"),
          ("mm_receipt", "mp04", r"Sheet", r"Scrim"),
          ("mm_l2", "mp06", r"Promotion Sheet.*", r"Scrim"),
          ("mm_l3", "mp07u", r"Promotion Sheet.*", r"Scrim"),
          ("mm_l4", "mp08u", r"Promotion Sheet.*", r"Scrim"),
          ("mm_l5", "mp09u", r"Promotion Sheet.*", r"Scrim")]
# Search dropdowns: screen -> export of the "Search “tun”" state that holds its "Search results"
SEARCH = {"p01": "s05", "p03": "s05", "p05": "s05", "p07": "s07", "p08": "s08", "p09": "s09", "p10": "p10s",
          "mp01": "s05", "mp03": "s05", "mp05": "s05", "mp07": "s07", "mp08": "s08", "mp09": "s09", "mp10": "p10s"}
# Order details are collapsed in the design, so their rows are not exported. These exports have them switched on.
EXPANDED = {k: k + "x" for k in ["p01", "p03", "p05", "p08", "p09", "mp01", "mp03", "mp05", "mp08", "mp09"]}
# Embedded because they are not on Google Fonts
LOCAL_FONTS = [("PP Editorial New", "100 250", "design/fonts/pangram/EditorialNew-Ultralight.otf", "opentype"),
               ("PP Editorial New", "251 500", "design/fonts/PPEditorialNew-Light.ttf", "truetype")]

uri = {}
for f in os.listdir(os.path.join(HERE, "assets")):
    uri[os.path.splitext(f)[0]] = "data:image/webp;base64," + base64.b64encode(open(os.path.join(HERE, "assets", f), "rb").read()).decode()


def key(p):
    """Asset key for an exported url. Images generated in Pencil (images/…) share file names with token cutouts, so they get their own prefix."""
    if "unsplash.com" in p:
        return "supplysky"
    k = re.sub(r"[^a-z0-9]", "", os.path.splitext(os.path.basename(p))[0].lower())
    return "img" + k if re.match(r"^(\./)?images/", p) else k


def fix_urls(h):
    return re.sub(r"url\('([^']+)'\)", lambda m: "var(--im-" + key(m.group(1)) + ")", h)


fams = set()


def load(f):
    s = BeautifulSoup(open(os.path.join(SRC, f + ".html")).read(), "lxml")
    for l in s.find_all("link", href=re.compile("fonts.googleapis.com/css2")):
        for v in urllib.parse.parse_qs(urllib.parse.urlparse(l["href"]).query)["family"]:
            fams.add(v)
    return s


def named(s, pat):
    return s.find(attrs={"data-pencil-name": re.compile("^(" + pat + ")$")})


def unplace(el):
    """Strip the absolute placement a node had inside its frame so it can be laid out by the shell."""
    st = re.sub(r"(^|;)\s*(left|top|position|z-index):[^;]*", "", el["style"])
    el["style"] = st.strip("; ") + "; position: relative"
    return re.search(r"(?:^|;)\s*width:\s*([\d.]+)px", st).group(1)


screens = []
for k, mode in SCREENS.items():
    s = load(k)
    root = s.body.find(attrs={"data-pencil-id": True}, recursive=False)
    if k in EXPANDED:
        x = load(EXPANDED[k])
        for old, new in zip(root.find_all(attrs={"data-pencil-name": "Order Summary"}),
                            x.find_all(attrs={"data-pencil-name": "Order Summary"})):
            new["data-collapsible"] = "1"
            old.replace_with(new)
    for os_ in root.find_all(attrs={"data-pencil-name": "Order Summary"}):
        os_["data-collapsible"] = "1"
    drop = named(load(SEARCH[k]), "Search results")
    if drop:
        drop["class"] = "ms-drop"
        drop["style"] = re.sub(r"(^|;)\s*(left|top|z-index):[^;]*", "", drop["style"]).strip("; ")
        root.append(drop)
    root["class"] = "screen"
    root["data-screen"] = k
    root["data-mode"] = mode
    screens.append(str(root))

# mmm.supply lander: wrap the 5840-wide strip in a 1440 viewport
s = load("supply")
root = s.body.find(attrs={"data-pencil-id": True}, recursive=False)
root["style"] = root["style"] + "; flex-shrink: 0"
screens.append('<div class="screen" data-screen="supply" data-mode="d" style="width:1440px;overflow:hidden;position:relative;background:#2A8EEA">' + str(root) + "</div>")

modals = []
for k, f, pat, scrim_pat in MODALS:
    s = load(f)
    el = named(s, pat)
    sc = named(s, scrim_pat)
    m = re.search(r"background-color:\s*([^;]+)", sc.get("style", "")) if sc else None
    scrim = m.group(1).strip() if m else "#0000009E"
    w = unplace(el)
    modals.append(f'<div class="modal" data-modal="{k}" data-scrim="{scrim}" style="width:{w}px">{el}</div>')

best = {}
for f in fams:
    n = f.split(":")[0]
    if len(f) > len(best.get(n, "")):
        best[n] = f
fl = "https://fonts.googleapis.com/css2?" + "&".join("family=" + urllib.parse.quote(f, safe=":;@.,") for f in sorted(best.values())) + "&display=swap"
local = "".join("@font-face{font-family:'%s';font-weight:%s;font-display:swap;src:url(data:font/%s;base64,%s) format('%s')}"
                % (n, w, "otf" if t == "opentype" else "ttf", base64.b64encode(open(os.path.join(ROOT, p), "rb").read()).decode(), t)
                for n, w, p, t in LOCAL_FONTS)
out = open(os.path.join(HERE, "shell.html")).read()
out = out.replace("__FONTS__", f'<link rel="stylesheet" href="{fl}">\n<style>{local}</style>')
out = out.replace("__SCREENS__", "\n".join(screens)).replace("__MODALS__", "\n".join(modals))
out = fix_urls(out)
used = set(re.findall(r"var\(--im-([a-z0-9]+)\)", out))
css = ":root{" + "".join(f"--im-{key(k)}:url('{v}');" for k, v in uri.items() if key(k) in used) + "}"
out = out.replace("</style>", css + "</style>", 1)
open(os.path.join(HERE, "mmm-fun-level-up.html"), "w").write(out)
print(len(out) // 1024, "KB", sorted(best))
print("unresolved urls:", sorted(u for u in used if u not in {key(k) for k in uri}))
