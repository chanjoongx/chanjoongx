#!/usr/bin/env python3
"""The profile README's picture: my GitHub contribution graph as a lawn, and the dog from chanjoongx.com on it.

Each week is a tuft of grass as tall as the week's contributions, on a square-root scale against the busiest week of
the last year, the newest on the right; a week with none is bare ground. The wide picture holds the last 52 weeks,
the narrow one the last 28. The dog stays at today, past the newest week, facing back over the year, and keeps the
hour in Seoul. By day it does what the site's dog does as its page opens: it wags its hello, and ten seconds in it
dozes off (its eyes shut, it lies down, and a "z" comes up), each act over within a second. At night it is asleep
from the start, and nothing moves. A reader who asks for reduced motion gets the still picture: the dog standing at
today, or asleep at night.

Two layouts, each in a light and a dark picture: wide, beside the README's column at 846 px, and narrow, for phones
and tablets. The workflow (.github/workflows/hero.yml) fetches the calendar (calendar.graphql) and runs this every
hour, and puts what it draws on the output branch, which README.md reads.

Standard library only: the text comes drawn, as glyph outlines, from kit.json (kit.py makes it from the fonts).

    python hero/render.py CALENDAR PART OUT
        CALENDAR  the answer to calendar.graphql, or a calendar.json this wrote
        PART      morning, afternoon, evening or night; auto for the part it is in Seoul now, which also wants the
                  calendar to end today (as the workflow runs it)
        OUT       gets the four pictures, blank.svg, calendar.json and README.md; the part drawn is printed
"""
from __future__ import annotations

import datetime
import functools
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent

NAME = "Chanjoong (CJ) Kim"
HELLO = "Hi, I'm CJ."
LEDE = "I build AI dev tools and apps, idea to shipped, on a short clock."
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
PARTS = {  # the part of the day in Seoul, by the hour there; the dog sleeps at night
    "morning": range(6, 12),
    "afternoon": range(12, 18),
    "evening": range(18, 23),
    "night": (23, 0, 1, 2, 3, 4, 5),
}
SEOUL = datetime.timezone(datetime.timedelta(hours=9))  # Korea keeps no summer time
YEAR = 52  # weeks; the busiest of them sets the grass's scale, in both layouts

# light: the site's ink on white, and its muted slate for the second tone (5.4:1); the grass in GitHub's greens for
# the contribution graph, darkest at the foot, its tips still 3.2:1 on white, as the tips are where a week's height
# is read. Dark: the same steps lifted for GitHub's dark grounds (#0d1117, and #212830 dimmed): ink 15.4:1 and 12.1:1,
# muted 7.9:1 and 6.2:1, the tips 9.8:1 and 7.7:1. The ground line is a hairline under it all, and the dog keeps its
# white body and ink face in both, its outline turned light in the dark (src/og/icons.ts on the site). The light
# picture lies on a white of its own, GitHub's light page, so that it still reads where it is shown on a dark one (an
# app that takes the light picture whatever its theme); the dark one stays clear, as GitHub's dark grounds differ.
THEMES = {
    "light": dict(page="#ffffff", ink="#16181d", muted="#5a6d76", ground="#d1d9e0", dog_line="#16181d",
                  grass=("#116329", "#1a7f37", "#2da44e")),
    "dark": dict(page=None, ink="#e6e8eb", muted="#9ba9b2", ground="#3d444d", dog_line="#a8adb5",
                 grass=("#196c2e", "#2ea043", "#56d364")),
}


@dataclass(frozen=True)
class Layout:
    name: str
    width: int
    px: int  # the dog's pixel, and the grass's
    week: int  # pixels a week of grass is wide
    weeks: int  # weeks drawn, to today
    hmax: int  # pixels the busiest week of the year stands
    # the type, which kit.py draws from here into kit.json; the rest of the picture hangs from the lede's last baseline
    name_size: float
    lede_size: float
    lede_lh: float
    lede_width: float
    lede_gap: float  # the name's baseline to the top of the lede's capitals
    gap: float  # the lede's last baseline to the top of the tallest grass
    mono: float  # the labels under the ground
    label_gap: float  # the ground to their baseline


LAYOUTS = (
    Layout("wide", 846, 3, 5, 52, 22, 26, 30, 36, 846 * .78, 28, 34, 13, 22),
    Layout("narrow", 320, 3, 3, 28, 16, 22, 22, 28, 320, 22, 28, 12, 20),
)

# the timeline, in seconds from the picture opening: the site's dog's, its hello and its doze (src/scripts/dog.ts)
HELLO_AT = .45  # the hello starts
WAG = .15  # each half of a wag
NAP = 10  # the doze starts: the site's dog dozes off when the reader has done nothing for ten seconds
DOZE = .26  # each pose of the doze: its eyes shut, lying down, the "z" up a row
MOTION = 5  # WCAG 2.2.2: motion that starts by itself is over within five seconds
ACT = 1  # and each act within a second, as the site's dog keeps every act


# ---- the dog: chanjoongx.com's (src/scripts/dog.ts), k its outline, w its white body; it faces left --------------
DOG_W, DOG_H = 19, 16
DOG_INK = "#16181d"  # its eyes and nose, in any light
DOG_WHITE = "#ffffff"
REST = [
    "k.kkkkkkk.k",
    "kkwwwwwwwkk",
    "kwwwwwwwwwkk",
    "kwwwwwwwwwwwk....k",
    "kwkwwwwkwwwwwkk.kk",
    "kwwwwwwwwwwwwwwkk",
    "kwwwkkwwwwwwwwwwk",
    "kwwwwwwwwwwwwwwwwk",
    "kwwwwwwwwwwwwwwwwk",
    "kwwwwwwwwwwwwwwwwk",
    "kwwwwwwwwwwwwwwwwk",
    "kwwwwwwwwwwwwwwwwk",
    ".kwwwwwwwwwwwwwwk",
    ".kwwkwkkkkkkwkwwk",
    ".kwwkwk....kwkwwk",
    "..kk.k......k.kk",
]
LIE = [
    "k.kkkkkkk.k",
    "kkwwwwwwwkkk",
    "kwwwwwwwwwwwkk",
    "kwwwwwwwwwwwwwkk",
    "kwwwwwwwwwwwwwwwk",
    "kwkkwwkkwwwwwwwwk",
    "kwwwkkwwwwwwwwwwk.k",
    ".kwwwwwwwwwwwwwwkk",
    "..kkkkkkkkkkkkkkk",
]
ZZ = ["kkkk", "..k.", ".k..", "kkkk"]
Z_AT = (12, 3)
WAG_OFF, WAG_ON = (17, 4), (18, 2)  # a wag: the tail's tip leaves one cell for the other
REST_FACE = {(2, 4), (7, 4), (4, 6), (5, 6)}  # eyes and nose: ink in any light (src/og/icons.ts)
LIE_FACE = {(2, 12), (3, 12), (6, 12), (7, 12), (4, 13), (5, 13)}  # shut eyes and nose, lying down
SHUT = ((3, 4), (6, 4))  # standing, the cells that shut its eyes


def padded(rows: list[str]) -> list[str]:
    """A pose in the dog's full box, standing on its floor."""
    return [r.ljust(DOG_W, ".") for r in [""] * (DOG_H - len(rows)) + rows]


def sprite(rows: list[str], face: set, px: int, fills: dict, skip: frozenset = frozenset(), attrs: str = "") -> str:
    """A pose as a group of three paths at the origin: its white body, its outline and its face. `skip` leaves cells
    out (the tail's tip, which wags)."""
    rows = padded(rows)

    def kind(c: int, r: int) -> str | None:
        if rows[r][c] == "." or (c, r) in skip:
            return None
        return "w" if rows[r][c] == "w" else ("f" if (c, r) in face else "o")

    runs: dict[str, list[str]] = {}
    for r in range(DOG_H):
        c = 0
        while c < DOG_W:
            kd, e = kind(c, r), c + 1
            while e < DOG_W and kind(e, r) == kd:
                e += 1
            if kd:
                runs.setdefault(kd, []).append(f"M{c * px} {r * px}h{(e - c) * px}v{px}h-{(e - c) * px}z")
            c = e
    paths = "".join(f'<path fill="{fills[kd]}" d="{"".join(runs[kd])}"/>' for kd in "wof" if kd in runs)
    return f"<g{attrs}>{paths}</g>"


def cell(c: int, r: int, px: int) -> str:
    return f"M{c * px} {r * px}h{px}v{px}h-{px}z"


# ---- the calendar ---------------------------------------------------------------------------------------------
def load_calendar(raw: dict, today: datetime.date | None = None) -> list[list[tuple[str, int]]]:
    """The weeks, oldest first, each its days as (date, contributions), from the GraphQL answer or a calendar.json
    this wrote. Checked, so that a bad answer stops the run (the output branch keeps the last pictures) rather than
    drawing a wrong lawn: the days one after another in weeks from Sunday, whole counts that add up to the calendar's
    own total, some contributions in the last year (none at all is likelier an outage than a year away), and, given
    `today`, a last day within a day of it (not an old calendar)."""
    total = None
    try:
        if "weeks" in raw:
            weeks = [[(d, c) for d, c in w] for w in raw["weeks"]]
        else:
            if raw.get("errors"):
                raise ValueError(f"the calendar query failed: {raw['errors']}")
            cal = raw["data"]["user"]["contributionsCollection"]["contributionCalendar"]
            weeks = [[(d["date"], d["contributionCount"]) for d in w["contributionDays"]] for w in cal["weeks"]]
            total = cal.get("totalContributions")
    except (KeyError, TypeError, AttributeError) as e:
        raise ValueError(f"not a contribution calendar ({type(e).__name__}: {e})") from None
    if len(weeks) < YEAR:
        raise ValueError(f"{len(weeks)} weeks, fewer than the {YEAR} the wide picture holds")
    prev = None
    for i, week in enumerate(weeks):
        if not 1 <= len(week) <= 7:
            raise ValueError(f"week {i} has {len(week)} days")
        for j, (d, c) in enumerate(week):
            day = datetime.date.fromisoformat(d) if isinstance(d, str) else None
            if day is None or day.isoformat() != d:
                raise ValueError(f"week {i}: {d!r} is not a date as YYYY-MM-DD")
            if prev is not None and day != prev + datetime.timedelta(days=1):
                raise ValueError(f"{d} does not follow {prev}")
            if i > 0 and j == 0 and day.weekday() != 6:
                raise ValueError(f"week {i} starts on {d}, not a Sunday")
            if type(c) is not int or c < 0:
                raise ValueError(f"{d}: {c!r} contributions")
            prev = day
    if total is not None and total != sum(totals(weeks)):
        raise ValueError(f"the days add up to {sum(totals(weeks))}, but the calendar says {total!r}")
    if not any(totals(weeks[-YEAR:])):
        raise ValueError(f"no contributions at all in the last {YEAR} weeks")
    if today is not None and abs((prev - today).days) > 1:
        raise ValueError(f"the calendar ends on {prev}, not about today ({today})")
    return weeks


def totals(weeks: list[list[tuple[str, int]]]) -> list[int]:
    return [sum(c for _, c in w) for w in weeks]


# ---- the grass ------------------------------------------------------------------------------------------------
def prng(seed: int):
    """mulberry32, as the site's."""
    s = seed & 0xFFFFFFFF

    def rand() -> float:
        nonlocal s
        s = (s + 0x6D2B79F5) & 0xFFFFFFFF
        t = s
        t = ((t ^ (t >> 15)) * (t | 1)) & 0xFFFFFFFF
        t = (t ^ ((t + (((t ^ (t >> 7)) * (t | 61)) & 0xFFFFFFFF)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296

    return rand


def heights(weekly: list[int], top: int, hmax: int) -> list[int]:
    """Each week's tuft in pixels: none for a week without contributions, else at least 2 and the busiest week's
    hmax, on a square root, so the quiet weeks still read beside the busy ones."""
    top = max(top, 1)
    return [0 if v == 0 else min(hmax, max(2, round(hmax * math.sqrt(v / top)))) for v in weekly]


def tuft(h: int, week: int, rand) -> list[tuple[int, int, int]]:
    """Pixels (x from the week's left, y up from the ground, shade) of one week's tuft: a turf the week's width at the
    foot, and blades rising from it, the middle one as tall as the week, the others shorter and leaning out, so the
    tops part as grass does. Shade 0 is the turf, 1 a blade, 2 its tip."""
    px: list[tuple[int, int, int]] = []
    if h <= 0:
        return px
    base = max(1, round(h * .22))
    for j in range(week):
        for y in range(base):
            px.append((j, y, 0))
    mid = week // 2
    spots = [mid] + [s for s in range(week) if s != mid]
    fracs = [1.0, .74, .86, .5, .58][:week]
    order = [0] + sorted(range(1, len(fracs)), key=lambda _: rand())
    for spot, i in zip(spots, order):
        hb = h if i == 0 else min(h, max(base + 1, round(h * fracs[i])))
        lean = 0 if spot == mid else (-1 if spot < mid else 1)
        if spot == mid and h > 6:
            lean = 1 if rand() < .5 else -1
        reach = 1 + h // 9  # a taller blade leans further
        for y in range(base, hb):
            f = (y - base + 1) / max(1, hb - base)
            dx = lean * int(f * reach + (.35 if spot == mid else .5)) if f > .45 else 0
            shade = 2 if y >= hb - max(1, (hb - base) // 4) else 1
            px.append((spot + dx, y, shade))
    return px


def lawn(lay: Layout, weeks: list[list[tuple[str, int]]]) -> dict[tuple[int, int], int]:
    """The grass as cells, (x, y up from the ground) in pixels to their shade; where tufts meet the higher shade
    shows (a blade over the turf, a tip over both). Each tuft draws from its own week's seed, so it keeps its shape as
    the year moves on; the first week's blades that lean out of the picture are cut."""
    top = max(totals(weeks[-YEAR:]))
    shown = weeks[-lay.weeks:]
    cells: dict[tuple[int, int], int] = {}
    for i, h in enumerate(heights(totals(shown), top, lay.hmax)):
        for x, y, shade in tuft(h, lay.week, prng(int(shown[i][0][0].replace("-", "")))):
            x += i * lay.week
            if x >= 0 and shade >= cells.get((x, y), -1):
                cells[x, y] = shade
    return cells


def rows_path(cells: list[tuple[int, int]], px: int, ground: int) -> str:
    """Cells as one path, a rectangle for each run of them along a row."""
    out = []
    for x, y in sorted(cells, key=lambda c: (c[1], c[0])):
        if out and out[-1][1] == y and out[-1][0] + out[-1][2] == x:
            out[-1][2] += 1
        else:
            out.append([x, y, 1])
    return "".join(f"M{x * px} {ground - (y + 1) * px}h{n * px}v{px}h-{n * px}z" for x, y, n in out)


# ---- the picture --------------------------------------------------------------------------------------------------
@functools.lru_cache(maxsize=None)
def kit() -> dict:
    return json.loads((HERE / "kit.json").read_text(encoding="utf-8"))


def type_spec() -> dict:
    """What kit.json's text is drawn from, here: the words and each layout's type. kit.py keeps a copy in kit.json,
    and a test holds the two together, so that new words never show in old glyphs."""
    return {"words": [NAME, HELLO, LEDE],
            "layouts": {lay.name: [lay.name_size, lay.lede_size, lay.lede_lh, round(lay.lede_width, 3), lay.lede_gap,
                                   lay.mono] for lay in LAYOUTS}}


def num(v: float, places: int = 3) -> str:
    s = f"{v:.{places}f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def anim(name: str, total: float, stops: list[tuple[float, str]]) -> str:
    """One element's whole timeline, once: each stop's style held (step-end) until the next, the last kept after."""
    frames: dict[str, str] = {}
    for t, style in stops + [(total, stops[-1][1])]:
        frames[num(100 * t / total, 3) + "%"] = style
    return (f"#{name}{{animation:{name} {num(total)}s step-end both}}"
            f"@keyframes {name}{{{''.join(f'{p}{{{s}}}' for p, s in frames.items())}}}")


def home(lay: Layout) -> int:
    """The dog's left edge: it stands at today, the picture's right end."""
    return lay.width - DOG_W * lay.px


def timeline(part: str) -> dict[str, list[float]]:
    """The dog's acts, each as the moments it changes, in seconds from the picture opening: by day its hello (the
    tail's tip up, down, up, down: two wags) and its doze (its eyes shut, it lies down, the "z" comes up a row); none
    at night, when it is asleep from the start."""
    if part == "night":
        return {}
    return {"hello": [HELLO_AT + j * WAG for j in range(4)], "doze": [NAP + j * DOZE for j in range(3)]}


def svg(lay: Layout, theme: str, part: str, weeks: list[list[tuple[str, int]]]) -> str:
    th = THEMES[theme]
    k = kit()["layouts"][lay.name]
    P, W = lay.px, lay.width
    used: dict[str, None] = {}
    body: list[str] = []
    css: list[str] = []

    def glyphs(uses) -> str:
        out = []
        for gid, x, y, tone in uses:
            used[gid] = None
            out.append(f'<use href="#{gid}" x="{num(x, 2)}" y="{num(y, 2)}" fill="{th[tone]}"/>')
        return "".join(out)

    def label(text: str, x: float, y: float, tone: str) -> str:
        mono = k["mono"]
        return glyphs((mono["glyphs"][ch], x + i * mono["adv"], y, tone) for i, ch in enumerate(text)
                      if mono["glyphs"][ch])

    # ---- the name, then the lede in its two tones
    body.append(glyphs(k["text"]))

    # ---- the ground and the grass, a path a shade
    ground = math.ceil((k["last"] + lay.gap + lay.hmax * P) / P) * P
    cells = lawn(lay, weeks)
    body.append(f'<rect x="0" y="{ground}" width="{W}" height="1" fill="{th["ground"]}"/>')
    body.append('<g shape-rendering="crispEdges">')
    for shade in (0, 1, 2):
        mine = [xy for xy, s in cells.items() if s == shade]
        if mine:
            body.append(f'<path fill="{th["grass"][shade]}" d="{rows_path(mine, P, ground)}"/>')
    body.append("</g>")

    # ---- the dog at today, facing back over the year
    fills = {"o": th["dog_line"], "f": DOG_INK, "w": DOG_WHITE}
    zd = "".join(cell(Z_AT[0] + c, Z_AT[1] + r, P) for r, row in enumerate(ZZ) for c, ch in enumerate(row) if ch == "k")
    dog = [f'<g transform="translate({home(lay)} {ground - DOG_H * P})" shape-rendering="crispEdges">']
    if part == "night":
        # asleep under its "z" from the start, and nothing moves
        dog.append(f'<g id="nap">{sprite(LIE, LIE_FACE, P, fills)}<path id="zz" fill="{th["dog_line"]}" d="{zd}"/></g>')
    else:
        # standing, its tail's tip at rest; the tip and the shut eyes are cells of their own, shown when they are on
        a, b = WAG_OFF, WAG_ON
        dog.append(f'<g class="m" id="st">{sprite(REST, REST_FACE, P, fills, skip=frozenset({a}))}'
                   f'<path class="m" id="ta" fill="{th["dog_line"]}" d="{cell(*a, P)}"/>'
                   f'<path class="m" id="tb" fill="{th["dog_line"]}" opacity="0" d="{cell(*b, P)}"/>'
                   f'<path class="m" id="sh" fill="{DOG_INK}" opacity="0" d="{"".join(cell(*s, P) for s in SHUT)}"/></g>'
                   f'<g class="m" id="nap" opacity="0">{sprite(LIE, LIE_FACE, P, fills)}'
                   f'<path class="m" id="zz" fill="{th["dog_line"]}" d="{zd}"/></g>')
        t = timeline(part)
        hello, doze = t["hello"], t["doze"]
        T = doze[-1]
        css.append(anim("ta", T, [(0, "opacity:1")] + [(s, f"opacity:{j % 2}") for j, s in enumerate(hello)]))
        css.append(anim("tb", T, [(0, "opacity:0")] + [(s, f"opacity:{1 - j % 2}") for j, s in enumerate(hello)]))
        css.append(anim("sh", T, [(0, "opacity:0"), (doze[0], "opacity:1")]))
        css.append(anim("st", T, [(0, "opacity:1"), (doze[1], "opacity:0")]))
        css.append(anim("nap", T, [(0, "opacity:0"), (doze[1], "opacity:1")]))
        css.append(anim("zz", T, [(0, f"transform:translate(0,{P}px)"), (doze[2], "transform:none")]))
    dog.append("</g>")
    body.extend(dog)

    # ---- under the ground: when the lawn starts, and Seoul's part of the day under the dog
    sb = ground + lay.label_gap
    first = datetime.date.fromisoformat(weeks[-lay.weeks][0][0])
    since = f"{MONTHS[first.month - 1]} {first.year}"
    right = W - len(f"Seoul, {part}") * k["mono"]["adv"]
    body.append(label(since, 0, sb, "muted"))
    body.append(label("Seoul,", right, sb, "muted") + label(part, right + 7 * k["mono"]["adv"], sb, "ink"))
    H = math.ceil(sb + 6)

    style = "".join(css) + "@media (prefers-reduced-motion:reduce){.m{animation:none!important}}"
    title = escape(f"{NAME}. {HELLO} {LEDE} My GitHub contributions since {since}, a tuft a week. Seoul, {part}.")
    defs = "".join(f'<path id="{gid}" d="{kit()["glyphs"][gid]}"/>' for gid in used)
    page = f'<rect width="{W}" height="{H}" fill="{th["page"]}"/>' if th["page"] else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
            f"<title>{title}</title><style>{style}</style><defs>{defs}</defs>{page}{''.join(body)}</svg>\n")


BLANK = '<svg xmlns="http://www.w3.org/2000/svg" width="0" height="0"/>\n'  # where the other layout is in use


def part_at(hour: int) -> str:
    return next(p for p, hours in PARTS.items() if hour in hours)


def draw(raw: dict, part: str, out: Path, today: datetime.date | None = None) -> str:
    """Everything the output branch holds, written only once all of it is drawn; returns a line about it."""
    weeks = load_calendar(raw, today)
    files = {f"{lay.name}-{theme}.svg": svg(lay, theme, part, weeks) for lay in LAYOUTS for theme in THEMES}
    files["blank.svg"] = BLANK
    files["calendar.json"] = json.dumps({"weeks": weeks}, separators=(",", ":")) + "\n"
    files["README.md"] = ("Drawn by .github/workflows/hero.yml every hour (hero/render.py on main) from calendar.json, "
                          "the contribution calendar as GitHub gives it: the README's picture, for the part of the day "
                          f"it is in Seoul ({part}). Nothing here is edited by hand.\n")
    out.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        with open(out / name, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    year = totals(weeks[-YEAR:])
    return (f"{part}: {len(weeks)} weeks, {weeks[0][0][0]} to {weeks[-1][-1][0]}, "
            f"{sum(totals(weeks))} contributions; the busiest of the last {YEAR} weeks {max(year)}")


def main(argv: list[str], now: datetime.datetime | None = None) -> int:
    """The command; `now` (aware) stands in for the clock, for the tests."""
    if len(argv) != 4 or argv[2] not in (*PARTS, "auto"):
        print(__doc__.strip().split("\n\n")[-1], file=sys.stderr)
        return 2
    now = (now or datetime.datetime.now(datetime.timezone.utc)).astimezone(datetime.timezone.utc)
    auto = argv[2] == "auto"
    part = part_at(now.astimezone(SEOUL).hour) if auto else argv[2]
    try:
        raw = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        line = draw(raw, part, Path(argv[3]), today=now.date() if auto else None)
    except (OSError, ValueError) as e:  # a bad or missing calendar: draw nothing
        print(f"render: {e}", file=sys.stderr)
        return 1
    print(line, file=sys.stderr)
    print(part)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
