"""Retake the simulator screenshots used in the manuals (docs/img/).

    python docs/tools/takeshots.py

Needs Microsoft Edge, Pillow (pip install pillow) and internet (the
simulator downloads Python). It serves a copy of the simulator with
shots.js added, which sets up each scene (a finished run, a selected wheel,
a settings mismatch, each tab). For each scene, one headless Edge pass reads
where the panels are and a second takes the screenshot; then the parts are
cropped. Afterwards it splits the two tall panels and numbers the overview,
as the manuals expect. Then run "node make_manuals.js" in docs/.
"""
import functools, http.server, json, os, re, shutil, socketserver, subprocess, tempfile, threading
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(REPO, "docs", "img")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
W, H, SCALE = 1400, 1800, 1.5

work = tempfile.mkdtemp(prefix="rover_shots_")
os.makedirs(os.path.join(work, "sim"))
html = open(os.path.join(REPO, "sim", "rover_sim.html"), encoding="utf-8").read()
inject = open(os.path.join(HERE, "shots.js"), encoding="utf-8").read()
open(os.path.join(work, "sim", "rover_sim.html"), "w", encoding="utf-8").write(html.replace("</body>", "<script>" + inject + "</script>\n</body>"))
shutil.copy(os.path.join(REPO, "spike_all_in_one.py"), work)

class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


handler = functools.partial(Quiet, directory=work)
server = socketserver.TCPServer(("127.0.0.1", 0), handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
BASE = "http://127.0.0.1:%d/sim/rover_sim.html#" % server.server_address[1]

# scene: (URL hash, {image name: (part, or "a..b" from a down to b, or "a+b" both; padding)})
SCENES = {
    "overview": ("autorun&shot=overview", {"sim_overview": ("page", 0), "sim_topbar": ("bar", 6), "sim_toolbar": ("toolbar", 6)}),
    "logsel": ("autorun&shot=logsel", {"sim_logsel": ("stage+panel", 6)}),
    "params": ("shot=params&tab=params", {"sim_params": ("panel", 6)}),
    "rover": ("shot=rover&tab=rover", {"sim_rover": ("panel", 6)}),
    "roverprops": ("shot=roverprops&tab=rover", {"sim_rover_props": ("rtools..props", 8)}),
    "mismatch": ("shot=mismatch&tab=rover&rover=skid4", {"sim_mismatch_hud": ("hud", 6), "sim_mismatch_check": ("check", 8)}),
    "course": ("shot=course&tab=course", {"sim_course": ("panel", 6), "sim_course_tools": ("toolbar", 6)}),
    "code": ("shot=code&tab=code", {"sim_code": ("panel", 6)}),
}


def edge(args, url):
    prof = os.path.join(work, "profile")
    shutil.rmtree(prof, ignore_errors=True)
    return subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--user-data-dir=" + prof, "--hide-scrollbars",
                           "--window-size=%d,%d" % (W, H), "--force-device-scale-factor=%s" % SCALE,
                           "--blink-settings=preferredColorScheme=1", "--virtual-time-budget=3000000"] + args + [url],
                          capture_output=True, text=True, encoding="utf-8", errors="replace").stdout


full = {}
for name, (hsh, crops) in SCENES.items():
    found = list(re.finditer(r'<pre id="rects">(\{.*?)</pre>', edge(["--dump-dom"], BASE + hsh), re.S))
    if not found:
        print(name, "- the scene did not finish; skipped")
        continue
    rects = json.loads(found[-1].group(1).replace("&quot;", '"'))
    png = os.path.join(work, name + ".png")
    edge(["--screenshot=" + png], BASE + hsh)
    img = full[name] = Image.open(png)
    for fname, (what, pad) in crops.items():
        if what == "page":
            box = (0, 0, img.width, int(1000 * SCALE))
        else:
            if ".." in what:
                a, b = (rects[n] for n in what.split(".."))
                parts = [a, b]
                x0, y0, x1, y1 = min(a[0], b[0]), a[1], max(a[0] + a[2], b[0] + b[2]), b[1] + b[3]
            else:
                parts = [rects[n] for n in what.split("+")]
                x0, y0 = min(p[0] for p in parts), min(p[1] for p in parts)
                x1, y1 = max(p[0] + p[2] for p in parts), max(p[1] + p[3] for p in parts)
            box = tuple(int(v * SCALE) for v in (x0 - pad, y0 - pad, x1 + pad, y1 + pad))
            box = (max(0, box[0]), max(0, box[1]), min(img.width, box[2]), min(img.height, box[3]))
        img.crop(box).save(os.path.join(OUT, fname + ".png"))
        print(name, "->", fname)
server.shutdown()

# The status bar: its chips run wider than the box the page reports.
if "overview" in full:
    full["overview"].crop((31, 210, 940, 266)).save(os.path.join(OUT, "sim_hud.png"))
# Split the two tall panels; keep only the top of the settings list.
for name, first, second, cut, keep in [("sim_params", "sim_params_file", "sim_params_model", 1500, 860),
                                       ("sim_rover", "sim_rover_top", "sim_rover_bottom", 1075, None)]:
    src = os.path.join(OUT, name + ".png")
    if os.path.exists(src):
        im = Image.open(src)
        im.crop((0, 0, im.width, keep or cut)).save(os.path.join(OUT, first + ".png"))
        im.crop((0, cut, im.width, im.height)).save(os.path.join(OUT, second + ".png"))
        os.remove(src)
# Number the parts of the overview, to match the table in the simulator manual.
over = os.path.join(OUT, "sim_overview.png")
if os.path.exists(over):
    im = Image.open(over).convert("RGB")
    d = ImageDraw.Draw(im)
    font = ImageFont.truetype("arialbd.ttf", 30)
    for n, x, y in [(1, 869, 50), (2, 907, 109), (3, 618, 157), (4, 470, 560), (5, 1147, 84), (6, 963, 115), (7, 1373, 533)]:
        cx, cy, r = x * SCALE, y * SCALE, 24
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(200, 40, 40), outline=(255, 255, 255), width=3)
        d.text((cx, cy), str(n), fill=(255, 255, 255), font=font, anchor="mm")
    im.save(os.path.join(OUT, "sim_overview_marked.png"))
print("Check the images in docs/img, then run node make_manuals.js in docs/.")
