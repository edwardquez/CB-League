# CB League

Stats site for our Call of Duty league, one title at a time: standings, series recaps, player dashboards, rivalries,
projections, records and tournaments, with match entry by scoreboard screenshot. Built with Streamlit and MongoDB Atlas.

![Home page](docs/images/home.png)

## Highlights

- **Every series, recapped.** Map by map results, series totals and full scoreboards, shaded so the standout games jump out.
- **MAR (Maps Above Replacement).** One number for how much a player adds to a map, built from slaying, objective play and
  assists, and explained in full on the Glossary page.
- **Matchup previews.** Pick two lineups and see the odds, head to head history and how each map tends to go.
- **Tournaments.** Single and double elimination, round robin, round robin into playoffs, and Swiss, with brackets that fill
  in as maps are entered. Tournament stats stay separate from the regular season.
- **Fill From Screenshot.** Upload the Codcaster scoreboard from the end of a map and every stat fills itself in.
  Anything the reader isn't sure of is highlighted for a person to check before saving.
- **Practice Mode.** A private copy of the data for trying the Scorekeeper and Tournaments. Nothing is saved.
- **Works on a phone.** Every page is built to read on a small screen.

## Pages

| Page | What it shows |
| --- | --- |
| Home | All-time overview: totals, leaders, single-map records, seasons |
| Standings | Rankings by any stat, overall and per mode |
| Series Log | Every series with a full recap and scoreboards |
| Players | One player's dashboard: MAR, slaying, every mode |
| Rivalries & Matchup Previews | Lineups that keep meeting; pick teams and see the odds |
| Projections | Expected stat lines per player and map, plus the model's track record |
| Records | Season awards and the record book |
| Maps & Modes | Map pool, margins, rivalry record and who plays each map best |
| Visualizations | Percentiles, playstyle radar, MAR race, finishing, fight profile, form, head to head |
| Tournaments | Brackets, standings, match recaps and tournament-only stats |
| Glossary | What every stat means and how MAR is calculated |
| Scorekeeper | Password-protected data entry, players, Season Settings, backup |

## A closer look

<table>
<tr>
<td width="50%"><b>Standings</b><br><img src="docs/images/standings.png" alt="Standings"></td>
<td width="50%"><b>Series Log</b><br><img src="docs/images/series-log.png" alt="Series Log with a recap open"></td>
</tr>
<tr>
<td><b>Player dashboard</b><br><img src="docs/images/player.png" alt="Player dashboard"></td>
<td><b>Matchup preview</b><br><img src="docs/images/matchup-preview.png" alt="Matchup preview"></td>
</tr>
<tr>
<td><b>Visualizations</b><br><img src="docs/images/visualizations.png" alt="Visualizations"></td>
<td><b>Tournament bracket</b><br><img src="docs/images/tournament.png" alt="Double elimination bracket"></td>
</tr>
</table>

## Fill From Screenshot

Match entry reads the Codcaster scoreboard with [Tesseract OCR](https://github.com/tesseract-ocr/tesseract). Upload the
end-of-map board, say which row is which player (saved gamertags fill this in automatically), check the review and save.
Hardpoint and Search and Destroy are supported, 3v3 and 4v4, Modern Warfare 4 and Black Ops 7.

<table>
<tr>
<td width="50%"><b>1. Upload and match players</b><br><img src="docs/images/screenshot-entry.png" alt="Scoreboard read and players matched"></td>
<td width="50%"><b>2. Review every number, then save</b><br><img src="docs/images/screenshot-review.png" alt="Review step"></td>
</tr>
</table>

How it stays accurate:

- The board is found by its two team lines, so any size or crop works as long as the whole scoreboard is in the picture.
- Each column only accepts the characters it can contain (a time has a colon, damage is digits).
- Unsure readings are read a second time with different image settings, and any disagreement is flagged.
- The columns are checked against each other: non-traded kills can't exceed kills, and in Search and Destroy every
  per-round stat must match its total divided by the rounds played.
- Nothing is saved until a person presses Save on the review step. Highlighted cells show the reason on hover.

The screenshot is never stored. Only the numbers are saved, the same as typing them in.

## On a phone

<img src="docs/images/phone.png" alt="Standings and a player page on a phone" width="420">

## Run it locally

Needs Python 3.11 or newer.

```
python -m venv .venv
.venv\Scripts\activate            # Windows (Mac/Linux: source .venv/bin/activate)
pip install -r requirements.txt
```

Create `.streamlit/secrets.toml` with your MongoDB connection string and a Scorekeeper password (the file is in
`.gitignore`, so it never gets pushed):

```toml
[mongo]
uri = "mongodb+srv://USER:PASSWORD@YOUR-CLUSTER.mongodb.net/?retryWrites=true&w=majority"
db = "cb_league"

[scorekeeper]
password = "choose-a-password"
```

Start the app:

```
streamlit run Home.py
```

Without a `secrets.toml`, the app runs in preview mode and nothing is saved.

### Screenshot entry (optional)

Fill From Screenshot needs Tesseract, which is a separate program, not a Python package:

- **Windows:** install it with the [UB Mannheim installer](https://github.com/UB-Mannheim/tesseract/wiki) and keep the
  default folder. The app finds it there.
- **Mac:** `brew install tesseract`
- **Linux:** `sudo apt install tesseract-ocr`

Without Tesseract the screenshot box is simply hidden and everything else works. To check a folder of screenshots
without the app:

```
python scripts/ocr_check.py path/to/screenshots
```

## Deploy (Streamlit Community Cloud)

1. Push the repo to GitHub (`secrets.toml` stays out because of `.gitignore`).
2. New app, pick the repo, main file `Home.py`.
3. Settings, Secrets: paste the contents of your `secrets.toml`.
4. In MongoDB Atlas, Network Access, allow `0.0.0.0/0` so Streamlit Cloud can connect.

`packages.txt` installs Tesseract on the server, so screenshot entry works there too.

## Project layout

```
Home.py                 home page
pages/                  one file per page (the number sets the sidebar order)
cbl/                    app code
  db.py                 MongoDB connection (or preview mode)
  data.py               cached reads and the Scorekeeper's writes
  engine.py             turns the raw documents into every table the pages use
  tourney.py            tournament brackets: formats, results, standings, Swiss pairing
  ocr.py                scoreboard screenshot reader (Tesseract)
  stats/                MAR, ratings, playstyle profile, projections
  ui/                   shared styling, page setup and the map entry flow
config/titles/          starting settings for each title (modes, maps, MAR values)
scripts/
  migrate_bo7.py        loads the Black Ops 7 season into MongoDB (needs the original workbook, not in the repo)
  add_mw4_maps.py       adds the Modern Warfare 4 map pool
  ocr_check.py          reads a folder of scoreboard screenshots
static/maps/            map pictures
docs/images/            screenshots for this README
tests/                  checks the stats against hand-verified numbers
```

## Adding a new title

Season Settings in the Scorekeeper handles maps and modes for an existing title. For a brand-new game, copy
`config/titles/mw4.yaml`, change the id, name, year and order, then run `python scripts/migrate_bo7.py` once so the new
title's settings are created (existing data and settings are left alone). The script reads the original Black Ops 7
workbook, which stays on the scorekeeper's computer and isn't in the repo. Then in Scorekeeper, Season Settings, pick the
new title and press the "Make … the current title" button.

## Tests

```
python tests/test_stats.py
```

The tests check against `data/bo7_seed.json`, a local snapshot written by the migration script (kept out of the repo
because it includes private notes).