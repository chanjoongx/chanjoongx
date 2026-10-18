# The README's picture

My GitHub contribution graph as a lawn, with the dog from [chanjoongx.com](https://chanjoongx.com) on it, drawn
again every hour.

- **The grass.** Each week is a tuft as tall as that week's contributions, on a square-root scale against the busiest
  week of the last year, the newest on the right; a week with none is bare ground. The wide picture holds the last 52
  weeks, the narrow one the last 28, and the label under the ground says when the lawn starts. A tuft's shape comes
  from its week's own date, so it keeps it as the year moves on.
- **The dog** stays at today, past the newest week, facing back over the year, and keeps the hour in Seoul. By day
  it does what the site's dog does as its page opens: it wags its hello, and ten seconds in it dozes off (its eyes
  shut, it lies down, and a "z" comes up). At night (23:00 to 06:00) it is asleep from the start.
- **The motion** is the site dog's, two short acts at its moments: the hello within the first second (WCAG 2.2.2
  asks that motion nobody started be over within five), and the doze, ten seconds in, within a second. At night
  nothing moves. With reduced motion asked for, the picture is still: the dog standing at today, or asleep at night.
- **Two layouts.** Wide beside the README's column at its widest (846 px); narrow for phones and for the tablets'
  narrow column (a window of 768 to 1011 px). README.md shows one and gives the other an empty picture
  (`blank.svg`), by the window's width; where only the plain images are shown, it is the narrow one.
- **Light and dark** follow GitHub's theme, its own setting included. The grass is in GitHub's greens for the graph,
  its tips at least 3:1 on the page in both, since a week's height is read at its tip. The light picture carries
  GitHub's white under it, so it reads even where it lands on a dark page.
- **Text** is drawn as glyph outlines of Atkinson Hyperlegible Next and Mono (OFL, in `fonts/`), so no font loads.

## How it stays on the hour

The workflow `.github/workflows/hero.yml` runs every hour, and on a push that changes `hero/`. It runs the tests,
fetches the calendar with `calendar.graphql` and the workflow's own token, for the 52 weeks it draws (from a Sunday
to now, as `render.py span` gives them), and draws it with `render.py`, which uses the standard library only, so
nothing is installed. The weeks are asked for, as GitHub's own year (a year back from today, widened to that day's
Sunday) reaches a 54th week on a Sunday, and on a Monday too in a year with a 29 February: its calendar holds 53, and
the week it leaves out of the days it still counts in its total, so the days would not add up and nothing would be
drawn all that day. When anything it draws differs from what the `output` branch holds (the branch README.md points
at), it replaces that branch with a single commit of the new files; that is the pictures, or the calendar kept beside
them, which gains a day at midnight (UTC) even when the pictures stay the same. If the calendar does not come, or
does not check out (a day missing or out of order, days that do not add up to its total, a year without a
contribution, a last day that is not about today), nothing is published, and the branch keeps the last pictures.

Private contributions count as they do on the profile: as numbers, nothing else. The workflow's calendar counts days
in UTC, as the public profile does; your own token's counts them in your time zone, so a contribution made near
midnight can sit a day apart between the two.

GitHub pauses a public repository's scheduled workflows after 60 days with no activity in it (its documentation does
not say whether the workflow's own pushes count). Paused, the picture stays as it last was until the workflow is
enabled again: with **Enable workflow** on its page in the Actions tab, with `gh workflow enable hero.yml`, or with a
commit that changes its `cron` line. Other pushes do not wake it.

## Running it here

```sh
python -m unittest discover -s hero -p "test_*.py"
span=$(python hero/render.py span)
gh api graphql -f login=chanjoongx -f from="${span% *}" -f to="${span#* }" -F query=@hero/calendar.graphql \
  > calendar.json
python hero/render.py calendar.json evening out
```

`kit.json` holds the text as glyph outlines. Make it again when the words or a layout's type change (they are in
`render.py`, and a test fails until this has run) or a font does (the files, weights and tracking are in `kit.py`):

```sh
pip install fonttools brotli uharfbuzz
python hero/kit.py
```
