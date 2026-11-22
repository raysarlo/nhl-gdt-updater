# NHL Game Day Thread (GDT) Updater

A Python tool that automatically updates NHL Game Day Thread templates with live data from the NHL API, DailyFaceoff, and ESPN. Designed for Rangers game day threads - automatically fetches data for both the Rangers and their opponent.

## Downloads

Pre-built executables (no Python required):

| Platform | Download |
|----------|----------|
| Windows | [NHL-GDT-Updater-Windows.exe](releases/NHL-GDT-Updater-Windows.exe) |
| Mac | Coming soon (check Releases) |

### Running the Executable

**Option 1: Interactive Mode (Double-click)**

Just double-click the executable and follow the prompts. Enter the opponent team name when asked.

**Option 2: Command Line**

**Windows (Command Prompt or PowerShell):**
```cmd
# Navigate to where you downloaded the exe
cd C:\Users\YourName\Downloads

# Run with opponent team name (Rangers are automatic)
NHL-GDT-Updater-Windows.exe Bruins

# Run with a specific template file
NHL-GDT-Updater-Windows.exe Bruins --file "C:\path\to\template.txt"

# Run with custom output file
NHL-GDT-Updater-Windows.exe BOS --file "template.txt" --output "updated.txt"
```

**Mac (Terminal):**
```bash
# Navigate to where you downloaded the file
cd ~/Downloads

# Make it executable (only needed once)
chmod +x NHL-GDT-Updater-Mac

# Run with opponent team name (Rangers are automatic)
./NHL-GDT-Updater-Mac Bruins

# Run with a specific template file
./NHL-GDT-Updater-Mac Bruins --file "/path/to/template.txt"

# Run with custom output file
./NHL-GDT-Updater-Mac BOS --file "template.txt" --output "updated.txt"
```

## Features

### Game Information (from NHL.com)
- **Game Number**: Rangers' game number for the season
- **Date & Time**: Game date and start time (Eastern)
- **TV Broadcasts**: US national networks plus the Rangers' own regional feed (the opponent's local feed is skipped)
- **Radio Stations**: Rangers radio coverage (98.7 FM, 107.1 FM, 710 AM, Sirius XM)
- **GameCenter Link**: Direct link to NHL.com game page

### Team Logos
- Automatically updates logos for both teams throughout the template
- All 32 NHL team logos supported

### Team Data (for both Rangers AND opponent)
- **Standings**: Record, points, division position, ROW, P%, home/away records, shootout record, L10, streak
- **Team Stats**: Goal differential, GF/GP, GA/GP, PP%, PK% (all with league rankings)
- **Team Leaders**: Goals, assists, points, +/-, PIM, TOI/G for defense & forwards
- **Line Combinations**: Forward lines and defense pairings (see [How lines and goalies are chosen](#how-lines-and-goalies-are-chosen))
- **Starting Goaltender**: Confirmed starter when available, otherwise a rule-based projection, plus stats (GS, record, SV%, GAA, SO)
- **Injuries**: Current injured/suspended players with status and body area

### Double-check notes
When something had to be guessed or a source was unavailable (unconfirmed goalie, lines taken from the last game, a site blocking requests), the tool lists it at the end of the run, and the web app shows it in a yellow box above the output.

## Requirements

- Python 3.7 or higher
- No external dependencies for the command-line tool (uses only the Python standard library)

## Installation

1. Download `nhl_gdt_updater.py`
2. Place it in any folder
3. Run from command line

## Usage

```bash
python nhl_gdt_updater.py <opponent_team> [--file <template_path>] [--output <output_path>]
```

**Note:** The Rangers are always set as the first team. You only need to specify the opponent.

### Examples

```bash
# Update for Rangers vs Bruins
python nhl_gdt_updater.py Bruins --file "template.txt"

# Use team abbreviation
python nhl_gdt_updater.py BOS --file "template.txt"

# Use full team name
python nhl_gdt_updater.py "Boston Bruins" --file "template.txt"

# Write to a different output file
python nhl_gdt_updater.py Sabres --file "template.txt" --output "gdt_output.txt"
```

### Supported Teams

All 32 NHL teams are supported via full name, city, nickname, or 3-letter abbreviation:

| Division | Teams |
|----------|-------|
| Metropolitan | CAR, CBJ, NJD, NYI, NYR, PHI, PIT, WSH |
| Atlantic | BOS, BUF, DET, FLA, MTL, OTT, TBL, TOR |
| Central | CHI, COL, DAL, MIN, NSH, STL, UTA (Mammoth), WPG |
| Pacific | ANA, CGY, EDM, LAK, SJS, SEA, VAN, VGK |

## Template Format

The tool expects an HTML template with specific `data-gdt` attributes for the fields to update. See `template_example.txt` for the expected format.

The template should have two team sections separated by `<hr>` tags:
1. **First section**: Rangers data
2. **Second section**: Opponent data

### Key Template Tags

```html
<!-- Standings -->
<p data-gdt="***UPDATE NYR RECORD***">...</p>
<p data-gdt="***UPDATE POSITION***">...</p>
<p data-gdt="***UPDATE ROW***">...</p>
<p data-gdt="***UPDATE P%***">...</p>
<p data-gdt="***UPDATE RECORD HOME***">...</p>
<p data-gdt="***UPDATE RECORD AWAY***">...</p>
<p data-gdt="***UPDATE S/O***">...</p>
<p data-gdt="***UPDATE LAST 10***">...</p>
<p data-gdt="***UPDATE STREAK***">...</p>

<!-- Team Stats -->
<p data-gdt="***UPDATE NYR DIFF***">...</p>
<p data-gdt="***UPDATE GF/GP***">...</p>
<p data-gdt="***UPDATE GA/GP***">...</p>
<p data-gdt="***UPDATE PP%***">...</p>
<p data-gdt="***UPDATE PK%***">...</p>

<!-- Team Leaders -->
<p data-gdt="***UPDATE NYR GOALS***">...</p>
<p data-gdt="***UPDATE ASSISTS***">...</p>
<p data-gdt="***UPDATE POINTS***">...</p>
<p data-gdt="***UPDATE +/-***">...</p>
<p data-gdt="***UPDATE PIM***">...</p>
<p data-gdt="***UPDATE TOI/G (D)***">...</p>
<p data-gdt="***UPDATE TOI/G (F)***">...</p>

<!-- Goaltender -->
<p data-gdt="***UPDATE GS***">...</p>
<p data-gdt="***UPDATE REC***">...</p>
<p data-gdt="***UPDATE SV%***">...</p>
<p data-gdt="***UPDATE GAA***">...</p>
<p data-gdt="***UPDATE SO***">...</p>
```

## Data Sources

| Data | Primary source | Fallback |
|------|----------------|----------|
| Game Schedule & Broadcasts | [NHL API](https://api-web.nhle.com) (team season schedule) | — |
| Standings, Stats, Leaders, Goalie Stats | [NHL API](https://api-web.nhle.com) | — |
| PP% & PK% Rankings | [NHL Stats API](https://api.nhle.com/stats) | — |
| Line Combinations | [DailyFaceoff](https://www.dailyfaceoff.com) (data embedded in the team page) | Rebuilt from NHL shift charts of the team's last game |
| Starting Goalie | [DailyFaceoff starting goalies](https://www.dailyfaceoff.com/starting-goalies/) (Confirmed/Likely) | [RotoWire lineups](https://www.rotowire.com/hockey/nhl-lineups.php) (game-day only), then a rule-based projection from NHL box scores |
| Injuries | [ESPN injuries API](https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/injuries) | DailyFaceoff injured list |

The NHL and ESPN sources are JSON APIs with no bot protection. DailyFaceoff is behind Cloudflare and blocks automated requests from cloud servers (the Render deployment gets HTTP 403); when it does, the fallbacks are used automatically and a note is shown. RotoWire has not been blocking, so on Render it is the main source for reported starters.

## How lines and goalies are chosen

**Lines.** DailyFaceoff's projected lines are used when available. Otherwise the tool downloads the NHL's shift chart for the team's most recent game and groups the players who spent the most 5-on-5 time together into four forward lines and three defense pairs. They are ranked by how long each unit was on the ice together (all situations) over the last 3 games, so one unusual game doesn't reshuffle the order: the trio with the most shared ice time is the 1st line, and so on. Players currently on the injury list are left out.

**Starting goalie.** If DailyFaceoff marks the starter as *Confirmed* or *Likely*, that goalie is used. On game day, RotoWire's *Confirmed* or *Expected* starter is used next. Otherwise the starter is projected with these rules:
1. Only goalies who dressed for the team's most recent game are considered (that is the current tandem, so injured or reassigned goalies drop out), and anyone on the injury list is removed.
2. On the second night of a back-to-back, the goalie who did **not** start the night before gets the start.
3. Otherwise, whoever started the most of the last 5 games.
4. Ties go to the goalie with more starts this season, then to whoever started the most recent game.

If the projection disagrees with DailyFaceoff's unconfirmed pick, both names appear in the notes.

## Development

Run the offline test suite (no network needed; uses saved NHL data in `tests/fixtures`):

```bash
python -m unittest discover tests
```

Tests also run automatically on GitHub for every push. Run with `-v`/`--verbose` to see debug output from the updater.

### Rebuilding the executables

The `.exe` in `releases/` is built from the code at the time it was committed. After changing the code, push a version tag (for example `git tag v2.0.0 && git push --tags`) and the **Build Executables** workflow builds Windows and Mac executables and attaches them to a GitHub Release.

## License

MIT License - feel free to use and modify as needed.

## Contributing

Pull requests welcome! Feel free to submit issues for bugs or feature requests.
