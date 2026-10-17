"""Build a team's SPIKE program from the software package they have bought.

    python build.py basic --team "Rocket Rovers"
    python build.py wall_follower --team "Rocket Rovers"
    python build.py explorer --team "Rocket Rovers"
    python build.py all --out spike_all_in_one.py      (everything, for testing)

The SPIKE App runs a single file, so this joins the package's modules into
one. Every package has the basic functions (movement, the distance and
colour sensors) and the setup_check tests; the two autonomy packages add
the wall follower or the maze explorer.

The result goes to builds/<team>.py unless --out says otherwise. If that
file already exists, its YOUR PROGRAM section is kept, so a team that
upgrades does not lose its own code.
"""
import argparse
import datetime
import os
import re

VERSION = "1.1"     # change this whenever the modules change, so teams can say which they have

HERE = os.path.dirname(os.path.abspath(__file__))
MODULE_DIR = os.path.join(HERE, "modules")

# The packages teams can buy: a name for the file header, and the modules in
# it, in the order they go into the file. Setup always comes first. "grid"
# is shared by the two autonomy packages.
BASIC = ["setup", "movement", "distance", "colour"]
PACKAGES = {
    "basic": ("Basic functions", BASIC),
    "wall_follower": ("Wall follower", BASIC + ["grid", "wall_follower"]),
    "explorer": ("Maze explorer", BASIC + ["grid", "explorer"]),
    "all": ("Everything (for testing)", BASIC + ["grid", "wall_follower", "explorer"]),
}

IMPORTS = """import motor
import distance_sensor
import color_sensor
import color
import runloop
import math
import time
from hub import port, motion_sensor, button"""


def read_module(name):
    """Split a module file into its #@title, #@about, #@constants, #@settings,
    #@tuning and #@code parts. Constants go before the settings, so settings
    can use them. Settings are the ones every team must look at; tuning
    settings go in a separate FINE TUNING block further down."""
    parts = {"title": "", "about": [], "constants": [], "settings": [], "tuning": [], "code": []}
    part = None
    with open(os.path.join(MODULE_DIR, name + ".py"), encoding="utf-8") as f:
        for line in f.read().splitlines():
            marker = re.match(r"#@(\w+)\s*(.*)$", line)
            if marker:
                part = marker.group(1)
                if part == "title":
                    parts["title"] = marker.group(2)
                continue
            if part in ("about", "constants", "settings", "tuning", "code"):
                parts[part].append(line)
    for key in ("about", "constants", "settings", "tuning", "code"):
        lines = parts[key]
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
    return parts


def banner(title):
    return ["# " + "=" * 70, "# " + title, "# " + "=" * 70]


def program_section(included):
    lines = banner("YOUR PROGRAM")
    lines += [
        "",
        "async def my_program():",
        "    # Write your own route here. This example drives a 30 cm square.",
        "    for side in range(4):",
        "        await drive_forward(30)",
        "        await turn_left(90)",
    ]
    if "distance" in included:
        lines += [
            "    # Another example: drive until a wall is 10 cm away, then turn to face WEST.",
            "    # await drive_to_wall(10)",
            "    # await turn_to(WEST)",
        ]
    if "explorer" in included and "colour" in included:
        lines += [
            "    # Another example: find colours in order with the Maze explorer. The lines",
            "    # after each explore(find=...) are your actions for that colour, and may drive.",
            "    # await explore(find=color.GREEN, near=(-30, 110))   # about 30 cm left, 110 cm ahead",
            "    # await drive_forward(8)                             # e.g. get the payload over it",
            "    # ...your payload code here...",
            "    # await explore(find=color.RED, towards=30)          # mostly north, a bit west",
        ]
    choices = ["my_program", "setup_check"]
    if "wall_follower" in included:
        choices.append("follow_wall")
    if "explorer" in included:
        choices.append("explore")
    default = choices[-1] if len(choices) > 2 else "my_program"
    lines += [
        "",
        "",
        "# Choose what runs: exactly ONE of these lines must have no # in front.",
        "# Run setup_check first on a new rover.",
    ]
    for name in choices:
        prefix = "" if name == default else "# "
        lines.append(prefix + "runloop.run(run_program(" + name + "))")
    return lines


def build(package, team):
    title, sections = PACKAGES[package]
    included = set(sections)
    modules = {name: read_module(name) for name in sections}

    out = banner("ROVER SOFTWARE - " + title.upper() + (" - " + team if team else ""))
    out += [
        "# Package: " + title + ". Version " + VERSION + ", built " + datetime.date.today().isoformat() + ".",
        "#",
        "# YOU ONLY CHANGE TWO PARTS OF THIS FILE:",
        "#   SETTINGS      just below: describe your rover and your course",
        "#   YOUR PROGRAM  at the very bottom: choose or write what the rover does",
        "# Everything in between is the rover software. Read it if you are curious,",
        "# but do not change it. The User Manual explains every setting and function.",
        "#",
        "# 1. Copy this whole file into a new Python project in the SPIKE App.",
        "# 2. Change the SETTINGS to match your rover.",
        "# 3. Run setup_check (see YOUR PROGRAM at the bottom) and fix anything it reports.",
        "# 4. Choose your program at the bottom and run it.",
        "# " + "=" * 70,
        "",
        IMPORTS,
        "",
        'SOFTWARE_VERSION = "' + VERSION + '"     # which version of the software this is',
        "",
    ]
    for name in sections:
        if modules[name]["constants"]:
            out += modules[name]["constants"] + [""]
    out += [""]

    out += banner("SETTINGS - change these to match your rover and your course")
    for name in sections:
        if modules[name]["settings"]:
            out += ["", "# ---- " + modules[name]["title"] + " ----"]
            out += modules[name]["settings"]
    out += ["", ""]

    out += banner("FINE TUNING - leave these alone unless the User Manual tells you to change them")
    for name in sections:
        if modules[name]["tuning"]:
            out += ["", "# ---- " + modules[name]["title"] + " ----"]
            out += modules[name]["tuning"]
    out += ["", ""]

    for name in sections:
        out += banner(modules[name]["title"].upper())
        out += modules[name]["about"]
        out += [""]
        out += modules[name]["code"]
        out += ["", ""]

    out += program_section(included)
    return "\n".join(out) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Build a team's rover program.")
    parser.add_argument("package", choices=list(PACKAGES),
                        help="the package the team bought (all = everything, for testing)")
    parser.add_argument("--team", default="", help="team name, for the file header")
    parser.add_argument("--out", help="output file (default builds/<team>.py)")
    args = parser.parse_args()

    out = args.out
    if not out:
        slug = re.sub(r"[^a-z0-9]+", "_", (args.team or "rover").lower()).strip("_")
        out = os.path.join(HERE, "builds", slug + ".py")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    text = build(args.package, args.team)
    # Rebuilding must not wipe the team's own code: keep the YOUR PROGRAM
    # section of the file being replaced, if it has one.
    marker = "\n".join(banner("YOUR PROGRAM"))
    if os.path.exists(out):
        with open(out, encoding="utf-8") as f:
            old = f.read().replace("\r\n", "\n")
        if marker in old:
            text = text[:text.index(marker)] + old[old.index(marker):]
            print("Kept the YOUR PROGRAM section from the old " + out)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("Wrote " + out + " (" + str(text.count("\n")) + " lines)")


if __name__ == "__main__":
    main()
