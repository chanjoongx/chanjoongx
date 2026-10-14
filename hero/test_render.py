"""render.py's tests, standard library only; the workflow runs them before it draws.

    python -m unittest discover -s hero -p "test_*.py"
"""
from __future__ import annotations

import contextlib
import datetime
import io
import json
import math
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import render as R

SVG_NS = "{http://www.w3.org/2000/svg}"
DASHES = re.compile("[" + chr(0x2013) + chr(0x2014) + "]|&[mn]dash;|&#821[12];|&#x201[34];|" + re.escape(chr(92)) + "u201[34]",
                    re.I)


def calendar(weekly: list[int], start: datetime.date = datetime.date(2025, 10, 12), last_days: int = 4):
    """Weeks from the Sunday `start`, each week's contributions on its Wednesday (or its last day, if sooner), the
    last week `last_days` long, as GitHub's calendar ends on today."""
    weeks, day = [], start
    for i, total in enumerate(weekly):
        n = last_days if i == len(weekly) - 1 else 7
        days = []
        for j in range(n):
            days.append((day.isoformat(), total if j == min(3, n - 1) else 0))
            day += datetime.timedelta(days=1)
        weeks.append(days)
    return weeks


def graphql(weeks) -> dict:
    """The answer to calendar.graphql, as GitHub shapes it."""
    days = [{"contributionCount": c, "date": d} for w in weeks for d, c in w]
    return {"data": {"user": {"contributionsCollection": {
        "contributionCalendar": {"totalContributions": sum(d["contributionCount"] for d in days),
                                 "weeks": [{"contributionDays": [{"contributionCount": c, "date": d} for d, c in w]}
                                           for w in weeks]},
        "restrictedContributionsCount": 0}}}}


def year(seed: int = 7, n: int = 53) -> list[int]:
    """A year of weeks as a busy person's: a few bare weeks, many quiet ones, and some very busy."""
    rand = R.prng(seed)
    out = []
    for _ in range(n):
        r = rand()
        out.append(0 if r < .12 else (1 + int(rand() * 3) if r < .3 else int(5 + 140 * rand() ** 2.2)))
    out[n // 2] = 143
    return out


def draw(raw: dict, part: str) -> dict[str, str]:
    with tempfile.TemporaryDirectory() as d:
        R.draw(raw, part, Path(d))
        return {p.name: p.read_text(encoding="utf-8") for p in sorted(Path(d).iterdir())}


def changes(text: str) -> list[tuple[str, float]]:
    """Every moment a picture changes, read from the CSS it carries, as (rule, seconds after it opens): a keyframed
    timeline at each step where its style changes. Any other kind of animation (eased, delayed, repeated, or without
    its fill) is refused, as these readings would not hold for it."""
    root = ET.fromstring(text)
    style, _, rest = root.find(SVG_NS + "style").text.partition("@media (prefers-reduced-motion:reduce)")
    assert rest == "{.m{animation:none!important}}", rest
    frames: dict[str, list[tuple[float, str]]] = {}
    for name, body in re.findall(r"@keyframes ([\w-]+)\{((?:[^{}]*\{[^{}]*\})*)\}", style):
        for sel, decl in re.findall(r"([^{}]+)\{([^{}]*)\}", body):
            for s in sel.split(","):
                s = s.strip()
                frames.setdefault(name, []).append((0.0 if s == "from" else 1.0 if s == "to" else float(s[:-1]) / 100,
                                                    decl))
    out = []
    rules = re.sub(r"@keyframes [\w-]+\{(?:[^{}]*\{[^{}]*\})*\}", "", style)
    for sel, decl in re.findall(r"([^{}]+)\{([^{}]*)\}", rules):
        m = re.fullmatch(r"#[\w-]+\{animation:([\w-]+) ([\d.]+)s step-end both\}", f"{sel}{{{decl}}}")
        assert m, f"{sel}{{{decl}}}"
        prev = None
        for off, d in sorted(frames[m.group(1)]):
            if prev is not None and d != prev:
                out.append((sel, off * float(m.group(2))))
            prev = d
    return out


def ink(d: str) -> tuple[float, float, float, float]:
    """The bounds of a glyph's outline as kit.json keeps it (the commands fontTools writes: M, L, H, V, Q and Z, a
    pair after a move being a line), its curves at their furthest."""
    assert re.fullmatch(r"[MLHVQZ0-9. -]*", d), d
    toks = re.findall(r"[MLHVQZ]|-?\d+(?:\.\d+)?", d)
    xs, ys, x, y, cmd, i = [], [], 0.0, 0.0, "", 0
    while i < len(toks):
        if toks[i].isalpha():
            cmd, i = toks[i], i + 1
            continue
        n = {"M": 2, "L": 2, "H": 1, "V": 1, "Q": 4}[cmd]
        v = [float(t) for t in toks[i:i + n]]
        i += n
        if cmd == "Q":
            for p0, p1, p2, out in ((x, v[0], v[2], xs), (y, v[1], v[3], ys)):
                if p0 - 2 * p1 + p2 and 0 < (p0 - p1) / (p0 - 2 * p1 + p2) < 1:
                    t = (p0 - p1) / (p0 - 2 * p1 + p2)
                    out.append((1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t * t * p2)
            x, y = v[2], v[3]
        else:
            x, y = (v[0], y) if cmd == "H" else (x, v[0]) if cmd == "V" else (v[0], v[1])
            cmd = "L" if cmd == "M" else cmd
        xs.append(x)
        ys.append(y)
    return min(xs), min(ys), max(xs), max(ys)


class TheHour(unittest.TestCase):
    def test_each_hour_has_its_part(self):
        parts = [R.part_at(h) for h in range(24)]
        self.assertEqual([h for h in range(24) if parts[h] == "night"], [0, 1, 2, 3, 4, 5, 23])
        self.assertEqual([h for h in range(24) if parts[h] == "morning"], list(range(6, 12)))
        self.assertEqual([h for h in range(24) if parts[h] == "afternoon"], list(range(12, 18)))
        self.assertEqual([h for h in range(24) if parts[h] == "evening"], list(range(18, 23)))


class TheCalendar(unittest.TestCase):
    def test_either_answer_draws_the_same_and_so_does_what_it_wrote(self):
        weeks = calendar(year())
        a = draw(graphql(weeks), "evening")
        self.assertEqual(a, draw({"weeks": weeks}, "evening"))
        self.assertEqual(a, draw(json.loads(a["calendar.json"]), "evening"))

    def test_the_same_calendar_draws_the_same_bytes(self):
        raw = graphql(calendar(year()))
        self.assertEqual(draw(raw, "morning"), draw(raw, "morning"))

    def test_a_bad_answer_draws_nothing(self):
        good = calendar(year())

        def with_day(w: int, d: int, value) -> list:
            weeks = [list(x) for x in good]
            weeks[w][d] = value
            return weeks

        gap = [list(x) for x in good]
        del gap[10][3]
        days = [d for w in good for d in w]
        monday = [days[:1]] + [days[i:i + 7] for i in range(1, len(days), 7)]  # every day there, weeks from Monday
        week_date = with_day(0, 0, ("2025-W41-7", 0))  # 2025-10-12 as an ISO week date, which Python 3.11 reads
        wrong_total = graphql(good)
        wrong_total["data"]["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"] += 1
        bad = {
            "errors": dict(graphql(good), errors=[{"type": "RATE_LIMITED", "message": "rate limited"}]),
            "no user": {"data": {"user": None}},
            "a list": [],
            "weeks not a list": {"weeks": 5},
            "too few weeks": {"weeks": good[-51:]},
            "an empty week": {"weeks": good[:10] + [[]] + good[10:]},
            "a gap": {"weeks": gap},
            "a week from a Monday": {"weeks": monday},
            "a negative count": {"weeks": with_day(3, 2, (good[3][2][0], -1))},
            "a fractional count": {"weeks": with_day(3, 2, (good[3][2][0], 1.0))},
            "a true count": {"weeks": with_day(3, 2, (good[3][2][0], True))},
            "a count as text": {"weeks": with_day(3, 2, (good[3][2][0], "4"))},
            "no such date": {"weeks": with_day(0, 0, ("2025-13-12", 0))},
            "a date as a number": {"weeks": with_day(0, 0, (20251012, 0))},
            "a week date": {"weeks": week_date},
            "days that do not add up to the total": wrong_total,
            "a year without a contribution": {"weeks": calendar([0] * 53)},
        }
        self.assertEqual(len(monday[1]), 7)
        self.assertEqual(datetime.date.fromisoformat(monday[1][0][0]).weekday(), 0)
        for why, raw in bad.items():
            with self.subTest(why), tempfile.TemporaryDirectory() as d:
                out = Path(d) / "out"
                with self.assertRaises(ValueError):
                    R.draw(raw, "evening", out)
                self.assertFalse(out.exists(), "nothing is written for a bad answer")

    def test_drawing_for_now_wants_a_calendar_that_ends_today(self):
        raw = graphql(calendar(year()))
        last = datetime.date(2025, 10, 12) + datetime.timedelta(days=52 * 7 + 3)
        with tempfile.TemporaryDirectory() as d:
            for days, ok in ((-1, True), (0, True), (1, True), (2, False), (8, False), (-2, False)):
                with self.subTest(days=days):
                    out = Path(d) / f"out{days}"
                    if ok:
                        R.draw(raw, "evening", out, today=last + datetime.timedelta(days=days))
                    else:
                        with self.assertRaises(ValueError):
                            R.draw(raw, "evening", out, today=last + datetime.timedelta(days=days))
                        self.assertFalse(out.exists())


class TheGrass(unittest.TestCase):
    def test_heights(self):
        self.assertEqual(R.heights([0, 1, 4, 36, 143], 143, 22),
                         [0, 2, round(22 * math.sqrt(4 / 143)), round(22 * math.sqrt(36 / 143)), 22])
        self.assertEqual(R.heights([0, 0, 0], 0, 22), [0, 0, 0])
        hs = R.heights(list(range(0, 144)), 143, 22)
        self.assertEqual(hs, sorted(hs), "a busier week is never shorter")
        self.assertTrue(all(2 <= h <= 22 for h in hs[1:]))

    def test_a_tuft_is_as_tall_as_its_week(self):
        for week in (3, 5):
            for h in range(1, 23):
                for seed in range(40):
                    px = R.tuft(h, week, R.prng(seed))
                    ys = [y for _, y, _ in px]
                    reach = 1 + h // 9
                    self.assertEqual((min(ys), max(ys)), (0, h - 1), (week, h, seed))
                    self.assertTrue(all(-reach <= x < week + reach for x, _, _ in px), (week, h, seed))
                    self.assertTrue(all(s == 0 for x, y, s in px if y == 0), "the foot is turf")
        self.assertEqual(R.tuft(0, 5, R.prng(1)), [])

    def test_the_lawn_keeps_out_of_the_edge_and_the_dog(self):
        weeks = calendar([143] * 53)  # every week as tall as can be, so every blade leans its furthest
        for lay in R.LAYOUTS:
            cells = R.lawn(lay, weeks)
            self.assertGreaterEqual(min(x for x, _ in cells), 0, lay.name)
            self.assertLessEqual((max(x for x, _ in cells) + 1) * lay.px, R.home(lay), lay.name)
            self.assertEqual(R.home(lay) + R.DOG_W * lay.px, lay.width, "the dog stands at the right end, today")
            self.assertEqual(max(y for _, y in cells), lay.hmax - 1, lay.name)
            self.assertEqual(set(cells.values()), {0, 1, 2}, lay.name)
            self.assertEqual({cells.get((x, 0)) for x in range(lay.weeks * lay.week)}, {0}, "every week its turf")

    def test_a_tuft_keeps_its_shape_as_the_year_moves_on(self):
        weekly = year(n=54)
        a = calendar(weekly[:53])
        b = calendar(weekly[1:], start=datetime.date(2025, 10, 19))  # a week later: the oldest gone, a new one
        self.assertEqual({max(weekly[1:53]), max(weekly[2:54])}, {143}, "the scale is the same in both")
        for lay in R.LAYOUTS:
            n, w = lay.weeks, lay.week

            def between(weeks, lo, hi, back):  # the cells over weeks lo to hi, moved `back` weeks to the left
                return sorted((x - back * w, y, s) for (x, y), s in R.lawn(lay, weeks).items() if lo * w <= x < hi * w)

            # each week of a is one week further left in b; the edges are left out, where a blade leans in from a
            # week that is in only one of them
            self.assertEqual(between(a, 2, n - 2, 1), between(b, 1, n - 3, 0), lay.name)
            self.assertNotEqual(between(a, 2, n - 2, 0), between(b, 2, n - 2, 0), "a check that can fail")


class ThePicture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = graphql(calendar(year()))
        cls.files = {part: draw(cls.raw, part) for part in R.PARTS}

    def test_it_is_all_there(self):
        for part, files in self.files.items():
            self.assertEqual(sorted(files), ["README.md", "blank.svg", "calendar.json", "narrow-dark.svg",
                                             "narrow-light.svg", "wide-dark.svg", "wide-light.svg"])
            self.assertIn(f"({part})", files["README.md"])
            self.assertEqual(files["blank.svg"], R.BLANK)

    def test_each_picture_is_well_made(self):
        for part, files in self.files.items():
            for lay in R.LAYOUTS:
                for theme in R.THEMES:
                    with self.subTest(part=part, layout=lay.name, theme=theme):
                        text = files[f"{lay.name}-{theme}.svg"]
                        root = ET.fromstring(text)
                        self.assertEqual(root.get("width"), str(lay.width))
                        self.assertEqual(root.get("viewBox"), f"0 0 {lay.width} {root.get('height')}")
                        defs = {p.get("id") for p in root.iter(SVG_NS + "path") if p.get("id", "").startswith("g")}
                        refs = {u.get("href")[1:] for u in root.iter(SVG_NS + "use")}
                        self.assertEqual(defs, refs, "every glyph drawn is defined, and none is kept for nothing")
                        ids = [e.get("id") for e in root.iter() if e.get("id")]
                        self.assertEqual(len(ids), len(set(ids)))
                        self.assertIn(f"Seoul, {part}.", root.find(SVG_NS + "title").text)
                        self.assertNotIn("NaN", text)
                        self.assertLess(len(text.encode()), 60_000)

    def test_everything_that_moves_stops_for_reduced_motion(self):
        for files in self.files.values():
            for name, text in files.items():
                if not name.endswith(".svg") or name == "blank.svg":
                    continue
                root = ET.fromstring(text)
                style = root.find(SVG_NS + "style").text
                self.assertTrue(style.endswith("@media (prefers-reduced-motion:reduce){.m{animation:none!important}}"))
                animated = set(re.findall(r"#([a-z]+)\{animation:", style))
                self.assertEqual(len(animated), style.count("animation:") - 1, "every animation is an element's own")
                for e in root.iter():
                    if e.get("id") in animated:
                        self.assertIn("m", (e.get("class") or "").split(), (name, e.get("id")))
                self.assertEqual(animated - {e.get("id") for e in root.iter()}, set(), "no rule for a missing element")

    def test_the_labels_can_say_any_month_and_part(self):
        for lay in R.LAYOUTS:
            chars = R.kit()["layouts"][lay.name]["mono"]["glyphs"]
            for text in [f"{m} {y}" for m in R.MONTHS for y in range(2025, 2100)] + [f"Seoul, {p}" for p in R.PARTS]:
                self.assertTrue(set(text) <= set(chars), (lay.name, text))

    def test_the_timing_the_pictures_carry(self):
        """From the CSS each picture carries, every moment it changes: nothing at night; by day the hello, within the
        first second, then nothing until the doze, ten seconds in, over within a second; each at the site dog's
        moments (src/scripts/dog.ts: the hello at 450 ms, a pose every 150; the doze at 10 s, a pose every 260)."""
        for part, files in self.files.items():
            for lay in R.LAYOUTS:
                for theme in R.THEMES:
                    with self.subTest(part=part, layout=lay.name, theme=theme):
                        found = changes(files[f"{lay.name}-{theme}.svg"])
                        if part == "night":
                            self.assertEqual(found, [], "asleep, and nothing moves")
                            continue
                        self.assertEqual({s for s, _ in found}, {"#ta", "#tb", "#sh", "#st", "#nap", "#zz"})
                        ts = sorted({round(t, 3) for _, t in found})  # a keyframe is placed to a thousandth of a per cent
                        early = [t for t in ts if t <= R.MOTION]
                        late = [t for t in ts if t > R.MOTION]
                        self.assertLessEqual(early[-1] - early[0], R.ACT)
                        self.assertLessEqual(late[-1] - late[0], R.ACT)
                        self.assertEqual(ts, [.45, .6, .75, .9, 10, 10.26, 10.52])

    def test_the_still_picture(self):
        """With no animation (reduced motion asked for), what shows is the dog at today: standing by day, its eyes
        open and its tail at rest; asleep under its "z" at night."""
        for part, files in self.files.items():
            for lay in R.LAYOUTS:
                with self.subTest(part=part, layout=lay.name):
                    root = ET.fromstring(files[f"{lay.name}-light.svg"])
                    el = {e.get("id"): e for e in root.iter() if e.get("id")}
                    shown = {i for i in ("st", "nap") if i in el and el[i].get("opacity") != "0"}
                    if part == "night":
                        self.assertEqual(shown, {"nap"})
                        self.assertNotIn("st", el)
                        self.assertIsNone(el["zz"].get("opacity"))
                    else:
                        self.assertEqual(shown, {"st"})
                        self.assertEqual([el[i].get("opacity") for i in ("ta", "tb", "sh")], [None, "0", "0"])
                    dog = next(g for g in root.iter(SVG_NS + "g") if el["nap"] in list(g))
                    self.assertEqual(dog.get("transform").split()[0], f"translate({lay.width - R.DOG_W * lay.px}",
                                     "at today, the right end")
                    moving = [e for e in root.iter() if "m" in (e.get("class") or "").split()]
                    self.assertEqual([e for e in moving if e.get("transform")], [], "nothing that moves is moved")

    def test_the_picture_draws_the_lawn(self):
        """The grass in each picture is the lawn's cells, each in its shade's green, standing on the ground line."""
        weeks = R.load_calendar(self.raw)
        for lay in R.LAYOUTS:
            cells = R.lawn(lay, weeks)
            for theme in R.THEMES:
                with self.subTest(layout=lay.name, theme=theme):
                    root = ET.fromstring(self.files["morning"][f"{lay.name}-{theme}.svg"])
                    ground = int(next(r for r in root.iter(SVG_NS + "rect") if r.get("height") == "1").get("y"))
                    greens = R.THEMES[theme]["grass"]
                    got: dict[tuple[int, int], int] = {}
                    for p in root.iter(SVG_NS + "path"):
                        if p.get("fill") in greens:
                            runs = re.findall(r"M(\d+) (\d+)h(\d+)v(\d+)h-\3z", p.get("d"))
                            self.assertEqual("".join(f"M{x} {y}h{n}v{v}h-{n}z" for x, y, n, v in runs), p.get("d"))
                            for x, y, n, v in runs:
                                self.assertEqual(int(v), lay.px)
                                for i in range(int(n) // lay.px):
                                    got[int(x) // lay.px + i, (ground - int(y)) // lay.px - 1] = greens.index(p.get("fill"))
                    self.assertEqual(got, cells)

    def test_the_dog_keeps_its_ink_face_in_the_dark(self):
        """Its eyes and nose, and its eyes shut, are ink on its white body in any light (src/og/icons.ts)."""
        for part, files in self.files.items():
            for lay in R.LAYOUTS:
                with self.subTest(part=part, layout=lay.name):
                    el = {e.get("id"): e for e in ET.fromstring(files[f"{lay.name}-dark.svg"]).iter() if e.get("id")}
                    for pose in ("st", "nap"):
                        if pose in el:
                            fills = [p.get("fill") for p in el[pose].iter(SVG_NS + "path")]
                            self.assertTrue({R.DOG_INK, R.DOG_WHITE, R.THEMES["dark"]["dog_line"]} <= set(fills), pose)
                    if "sh" in el:
                        self.assertEqual(el["sh"].get("fill"), R.DOG_INK)

    def test_the_text_stays_inside_the_picture(self):
        """Every glyph's ink, where it is placed, inside the picture: the dots on i and j over the name too."""
        glyphs = R.kit()["glyphs"]
        for part, files in self.files.items():
            for lay in R.LAYOUTS:
                with self.subTest(part=part, layout=lay.name):
                    root = ET.fromstring(files[f"{lay.name}-dark.svg"])
                    w, h = float(root.get("width")), float(root.get("height"))
                    for u in root.iter(SVG_NS + "use"):
                        x0, y0, x1, y1 = ink(glyphs[u.get("href")[1:]])
                        x, y = float(u.get("x")), float(u.get("y"))
                        self.assertTrue(0 <= x + x0 and x + x1 <= w and 0 <= y + y0 and y + y1 <= h,
                                        (u.get("href"), x + x0, y + y0, x + x1, y + y1, w, h))
        self.assertEqual(ink("M0 0H2V3Q4 4 2 5Z"), (0, 0, 3, 5), "the bounds reach a curve's furthest point")

    def test_the_light_picture_lies_on_a_page_of_its_own(self):
        """Under everything in the light picture, a white as big as it (it reads even on a dark page); nothing under
        the dark one, which GitHub's dark grounds show through."""
        for part, files in self.files.items():
            for lay in R.LAYOUTS:
                for theme in R.THEMES:
                    with self.subTest(part=part, layout=lay.name, theme=theme):
                        root = ET.fromstring(files[f"{lay.name}-{theme}.svg"])
                        first = [e for e in root if e.tag not in {SVG_NS + t for t in ("title", "style", "defs")}][0]
                        size = (root.get("width"), root.get("height"))
                        page = (first.tag == SVG_NS + "rect" and first.get("x") is None and first.get("y") is None
                                and (first.get("width"), first.get("height")) == size)
                        self.assertEqual(page and first.get("fill"), "#ffffff" if theme == "light" else False)

    def test_the_kit_is_drawn_from_these_words_and_this_type(self):
        self.assertEqual(R.kit()["made_from"], json.loads(json.dumps(R.type_spec())),
                         "the words or the type changed: run hero/kit.py again")

    def test_the_colours_read(self):
        def lum(h):
            c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
            c = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in c]
            return .2126 * c[0] + .7152 * c[1] + .0722 * c[2]

        def ratio(a, b):
            hi, lo = sorted((lum(a), lum(b)), reverse=True)
            return (hi + .05) / (lo + .05)

        grounds = {"light": [R.THEMES["light"]["page"]], "dark": ["#0d1117", "#212830"]}  # #212830 is dark dimmed
        self.assertEqual(R.THEMES["light"]["page"], "#ffffff", "GitHub's light page")
        for theme, bgs in grounds.items():
            th = R.THEMES[theme]
            for bg in bgs:
                self.assertGreaterEqual(ratio(th["ink"], bg), 7, (theme, bg))
                self.assertGreaterEqual(ratio(th["muted"], bg), 4.5, (theme, bg))
                self.assertGreaterEqual(ratio(th["grass"][2], bg), 3, (theme, bg, "the tips, where height is read"))
                self.assertGreaterEqual(ratio(th["dog_line"], bg), 3, (theme, bg))

    def test_no_dashes_anywhere(self):
        here = Path(R.__file__).resolve().parent
        sources = [here.parent / "README.md", here.parent / ".github" / "workflows" / "hero.yml"]
        sources += [p for p in here.iterdir() if p.suffix in (".py", ".json", ".md", ".graphql")]
        for p in sources:
            if p.exists():
                self.assertEqual(DASHES.findall(p.read_text(encoding="utf-8")), [], p.name)
        for files in self.files.values():
            for name, text in files.items():
                self.assertEqual(DASHES.findall(text), [], name)


class TheCommand(unittest.TestCase):
    def run_main(self, *args, now: datetime.datetime | None = None) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = R.main(["render.py", *args], now=now)
        return code, out.getvalue(), err.getvalue()

    def test_it_draws_and_says_which_part(self):
        with tempfile.TemporaryDirectory() as d:
            cal = Path(d) / "calendar.json"
            cal.write_text(json.dumps(graphql(calendar(year()))), encoding="utf-8")  # it ends on 2026-10-14
            code, out, err = self.run_main(str(cal), "night", str(Path(d) / "out"))
            self.assertEqual((code, out), (0, "night\n"))
            self.assertIn("night: 53 weeks", err)
            noon = datetime.datetime(2026, 10, 14, 3, tzinfo=datetime.timezone.utc)  # noon in Seoul
            code, out, _ = self.run_main(str(cal), "auto", str(Path(d) / "out2"), now=noon)
            self.assertEqual((code, out), (0, "afternoon\n"))
            late = datetime.datetime(2026, 10, 16, 0, 30, tzinfo=R.SEOUL)  # 10-15 in UTC
            self.assertEqual(self.run_main(str(cal), "auto", str(Path(d) / "out3"), now=late)[:2], (0, "night\n"))
            code, out, err = self.run_main(str(cal), "auto", str(Path(d) / "out4"), now=noon + datetime.timedelta(days=2))
            self.assertEqual((code, out), (1, ""), "the calendar is two days old")
            self.assertIn("not about today", err)

    def test_it_refuses_what_it_cannot_draw(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(self.run_main("x.json", "noon", d)[0], 2)
            self.assertEqual(self.run_main(str(Path(d) / "none.json"), "night", str(Path(d) / "out"))[0], 1)
            broken = Path(d) / "broken.json"
            broken.write_text("{", encoding="utf-8")
            code, out, err = self.run_main(str(broken), "night", str(Path(d) / "out"))
            self.assertEqual((code, out), (1, ""))
            self.assertTrue(err.startswith("render: "))
            self.assertFalse((Path(d) / "out").exists())


if __name__ == "__main__":
    unittest.main()
