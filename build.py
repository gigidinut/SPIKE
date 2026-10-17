"""Build a team's SPIKE program from the modules they have bought.

    python build.py movement colour --team "Rocket Rovers"
    python build.py all --out spike_all_in_one.py

The SPIKE App runs a single file, so this joins the chosen modules into one.
Every team gets Setup. Modules that a chosen module needs are added
automatically, and a module the team did not buy is replaced by a short
"not installed" placeholder wherever other modules rely on it.

The result goes to builds/<team>.py unless --out says otherwise.
"""
import argparse
import datetime
import os
import re
import sys

VERSION = "1.0"     # change this whenever the modules change, so teams can say which they have

HERE = os.path.dirname(os.path.abspath(__file__))
MODULE_DIR = os.path.join(HERE, "modules")

# The modules teams can buy, and what each one needs. "grid" is shared by
# the two autonomy modules and is never sold on its own.
NEEDS = {
    "movement": [],
    "distance": ["movement"],
    "colour": ["movement"],
    "grid": ["movement", "distance"],
    "wall_follower": ["grid"],
    "explorer": ["grid"],
}
FOR_SALE = ["movement", "distance", "colour", "wall_follower", "explorer"]
ORDER = ["movement", "distance", "colour", "grid", "wall_follower", "explorer"]
PLACEHOLDERS = {"distance": "stub_distance", "colour": "stub_colour"}

IMPORTS = """import motor
import distance_sensor
import color_sensor
import color
import runloop
import math
import time
from hub import port, motion_sensor, button"""


def read_module(name):
    """Split a module file into its #@title, #@about, #@constants, #@settings
    and #@code parts. Constants go before the settings, so settings can use them."""
    parts = {"title": "", "about": [], "constants": [], "settings": [], "code": []}
    part = None
    with open(os.path.join(MODULE_DIR, name + ".py"), encoding="utf-8") as f:
        for line in f.read().splitlines():
            marker = re.match(r"#@(\w+)\s*(.*)$", line)
            if marker:
                part = marker.group(1)
                if part == "title":
                    parts["title"] = marker.group(2)
                continue
            if part in ("about", "constants", "settings", "code"):
                parts[part].append(line)
    for key in ("about", "constants", "settings", "code"):
        lines = parts[key]
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
    return parts


def banner(title):
    return ["# " + "=" * 70, "# " + title, "# " + "=" * 70]


def with_needs(chosen):
    """The chosen modules plus everything they need."""
    result = set()
    todo = list(chosen)
    while todo:
        name = todo.pop()
        if name not in result:
            result.add(name)
            todo.extend(NEEDS[name])
    return result


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


def build(chosen, team):
    included = with_needs(chosen)
    sections = ["setup"]
    for name in ORDER:
        if name in included:
            sections.append(name)
        elif name in PLACEHOLDERS:
            sections.append(PLACEHOLDERS[name])
    modules = {name: read_module(name) for name in sections}

    bought = [modules[n]["title"] for n in sections if n in FOR_SALE]
    missing = [read_module(n)["title"] for n in FOR_SALE if n not in included]

    out = banner("ROVER SOFTWARE" + (" - " + team if team else ""))
    out += [
        "# Version " + VERSION + ", built " + datetime.date.today().isoformat() + " with: Setup, " + ", ".join(bought),
        "# Not included: " + (", ".join(missing) if missing else "nothing - everything is installed"),
        "#",
        "# 1. Copy this whole file into a new Python project in the SPIKE App.",
        "# 2. Change the SETTINGS below to match your rover.",
        "# 3. Run setup_check (see YOUR PROGRAM at the bottom) and fix anything it reports.",
        "# 4. Choose your program at the bottom and run it.",
        "# The User Manual explains every setting and function.",
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
    parser.add_argument("modules", nargs="+",
                        help="modules to include: " + ", ".join(FOR_SALE) + ", or all")
    parser.add_argument("--team", default="", help="team name, for the file header")
    parser.add_argument("--out", help="output file (default builds/<team>.py)")
    args = parser.parse_args()

    chosen = FOR_SALE if args.modules == ["all"] else args.modules
    unknown = [m for m in chosen if m not in FOR_SALE]
    if unknown:
        sys.exit("Unknown module(s): " + ", ".join(unknown)
                 + ". Choose from: " + ", ".join(FOR_SALE) + ", or all.")

    out = args.out
    if not out:
        slug = re.sub(r"[^a-z0-9]+", "_", (args.team or "rover").lower()).strip("_")
        out = os.path.join(HERE, "builds", slug + ".py")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    text = build(chosen, args.team)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("Wrote " + out + " (" + str(text.count("\n")) + " lines)")


if __name__ == "__main__":
    main()
