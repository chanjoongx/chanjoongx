#!/usr/bin/env python3
"""The text of the profile README's picture, drawn once as glyph outlines into kit.json, so that the hourly render
(render.py) needs no fonts and installs nothing. Run it again when the words or a layout's type change (render.py
holds those, and a test there fails until this has run) or a font does (the files, weights and tracking are here).

The name in Atkinson Hyperlegible Next at 700 and the lede at 500, balanced to its width (as CSS's text-wrap:
balance) in the site's two tones, ink for the hello and muted for the rest; and Atkinson Hyperlegible Mono at 400 for
the labels under the ground, one glyph a character at the font's one advance (checked here: no kerning, ligature or
alternate moves them). The fonts and their licence (OFL) are in fonts/.

    pip install fonttools brotli uharfbuzz
    python hero/kit.py
"""
from __future__ import annotations

import io
import json
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

import render as R

HERE = Path(__file__).resolve().parent
TRACK = -0.015  # em: the site's tracking for its name and lede


class Face:
    """A weight of a variable font, shaped by HarfBuzz and drawn from its own outlines."""

    def __init__(self, file: str, wght: int):
        tt = TTFont(HERE / "fonts" / file)
        if "fvar" in tt:
            tt = instantiateVariableFont(tt, {"wght": wght})
        tt.flavor = None
        buf = io.BytesIO()
        tt.save(buf)
        data = buf.getvalue()
        self.tt = TTFont(io.BytesIO(data))
        self.font = hb.Font(hb.Face(data))
        self.upem = self.tt["head"].unitsPerEm
        self.cap = self.tt["OS/2"].sCapHeight / self.upem
        self.glyphs = self.tt.getGlyphSet()
        self.order = self.tt.getGlyphOrder()

    def shape(self, text: str, size: float, track: float = 0.0):
        """Glyphs as (glyph id, x, y offset, cluster) and the advance, in px; `track` is letter-spacing in em, after
        every glyph but the last (so a measured width is the ink's run, as CSS lays a line out)."""
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.font, buf, {})
        s = size / self.upem
        x = 0.0
        out = []
        n = len(buf.glyph_infos)
        for i, (info, pos) in enumerate(zip(buf.glyph_infos, buf.glyph_positions)):
            out.append((info.codepoint, x + pos.x_offset * s, -pos.y_offset * s, info.cluster))
            x += pos.x_advance * s + (track * size if i < n - 1 else 0)
        return out, x

    def outline(self, gid: int, size: float) -> str:
        s = size / self.upem
        pen = SVGPathPen(self.glyphs, ntos=lambda v: R.num(v, 1))
        self.glyphs[self.order[gid]].draw(TransformPen(pen, (s, 0, 0, -s, 0, 0)))
        return pen.getCommands()

    def top(self, text: str, size: float, track: float = 0.0) -> float:
        """How far the ink of `text` rises over its baseline, in px: the dots on i and j stand above the capitals."""
        s = size / self.upem
        tops = []
        for gid, _, gy, _ in self.shape(text, size, track)[0]:
            pen = BoundsPen(self.glyphs)
            self.glyphs[self.order[gid]].draw(pen)
            if pen.bounds:
                tops.append(pen.bounds[3] * s - gy)
        return max(tops)


FACES: dict[str, Face] = {}


def face(name: str) -> Face:
    if name not in FACES:
        file, wght = {
            "name": ("atkinson-hyperlegible-next-latin-wght-normal.woff2", 700),
            "lede": ("atkinson-hyperlegible-next-latin-wght-normal.woff2", 500),
            "mono": ("atkinson-hyperlegible-mono-latin-wght-normal.woff2", 400),
        }[name]
        FACES[name] = Face(file, wght)
    return FACES[name]


def measure(key: str, text: str, size: float, track: float = 0.0) -> float:
    return face(key).shape(text, size, track)[1]


def balance(words: list[str], key: str, size: float, track: float, width: float) -> list[str]:
    """The fewest lines that fit `width`, then the breaks that make the longest of them shortest (text-wrap: balance).
    A no-break space keeps its words on one line."""
    n = len(words)
    w = {}
    for i in range(n):
        for j in range(i + 1, n + 1):
            w[i, j] = measure(key, " ".join(words[i:j]), size, track)
    best = {n: (0, 0.0, [])}
    for i in range(n - 1, -1, -1):
        cands = []
        for j in range(i + 1, n + 1):
            if w[i, j] > width and j > i + 1:
                break
            lines, worst, rest = best[j]
            cands.append((lines + 1, max(worst, w[i, j]), [j] + rest))
        best[i] = min(cands, key=lambda c: (c[0], c[1]))
    out, i = [], 0
    for j in best[0][2]:
        out.append(" ".join(words[i:j]))
        i = j
    return out


def main():
    ids: dict[tuple, str] = {}
    outlines: dict[str, str] = {}

    def glyph(key: str, size: float, gid: int) -> str:
        """The glyph's id in the kit, its outline kept once; "" for one that draws nothing (a space)."""
        k = (key, size, gid)
        if k not in ids:
            d = face(key).outline(gid, size)
            ids[k] = f"g{len(outlines)}" if d else ""
            if d:
                outlines[ids[k]] = d
        return ids[k]

    def run(key: str, text: str, size: float, x: float, y: float, tone, track: float = 0.0) -> list:
        """One line at baseline y, as [glyph id, x, y, tone]; `tone` is a tone or a function of the character's
        index (two tones)."""
        shaped, _ = face(key).shape(text, size, track)
        out = []
        for gid, gx, gy, cl in shaped:
            g = glyph(key, size, gid)
            if g and text[cl] not in "  ":
                out.append([g, round(x + gx, 2), round(y + gy, 2), tone(cl) if callable(tone) else tone])
        return out

    layouts = {}
    for lay in R.LAYOUTS:
        # the name a pixel under the picture's top, then the lede in its two tones (its words "tools and apps" kept on
        # one line)
        name_base = 1 + face("name").top(R.NAME, lay.name_size, TRACK)
        text = run("name", R.NAME, lay.name_size, 0, name_base, "ink", TRACK)
        words = (R.HELLO + " " + R.LEDE.replace("tools and apps", "tools and apps")).split(" ")
        lines = balance(words, "lede", lay.lede_size, TRACK, lay.lede_width)
        first = name_base + lay.lede_gap + face("lede").cap * lay.lede_size
        off = 0
        for i, line in enumerate(lines):
            text += run("lede", line.replace(" ", " "), lay.lede_size, 0, first + i * lay.lede_lh,
                        lambda cl, start=off: "ink" if start + cl < len(R.HELLO) else "muted", TRACK)
            off += len(line) + 1
        last = first + (len(lines) - 1) * lay.lede_lh

        # the labels: every character they can hold, each its glyph at the one advance, and whole labels shaped to
        # make sure that is how the font sets them
        mono = face("mono")
        chars = sorted(set("".join(R.MONTHS) + "0123456789 Seoul," + "".join(R.PARTS)))
        raw, advs = {}, set()
        for ch in chars:
            shaped, width = mono.shape(ch, lay.mono)
            ((gid, gx, gy, _),) = shaped
            assert gx == 0 and gy == 0, ch
            raw[ch] = gid
            advs.add(round(width, 6))
        assert len(advs) == 1, f"the mono face has more than one advance: {advs}"
        (adv,) = advs
        for sample in [f"{m} 2025" for m in R.MONTHS] + ["Seoul, 0123456789"] + [f"Seoul, {p}" for p in R.PARTS]:
            shaped, _ = mono.shape(sample, lay.mono)
            got = [(gid, round(gx, 6), round(gy, 6)) for gid, gx, gy, _ in shaped]
            want = [(raw[ch], round(i * adv, 6), 0) for i, ch in enumerate(sample)]
            assert got == want, f"{sample!r} does not set a glyph a character"
        layouts[lay.name] = {
            "text": text,
            "last": round(last, 3),
            "mono": {"adv": adv, "glyphs": {ch: glyph("mono", lay.mono, raw[ch]) for ch in chars}},
        }

    kit = {"about": "The text of the README's picture as glyph outlines, made by hero/kit.py from hero/fonts/ (OFL). "
                    "Not edited by hand.",
           "made_from": R.type_spec(), "glyphs": outlines, "layouts": layouts}
    with open(HERE / "kit.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(kit, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"kit.json: {len(outlines)} glyphs; "
          + "; ".join(f"{k}: {len(v['text'])} placed, last baseline {v['last']}, mono advance {v['mono']['adv']}"
                      for k, v in layouts.items()))


if __name__ == "__main__":
    main()
