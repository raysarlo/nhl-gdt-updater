# NHL Game Day Thread (GDT) Updater

A Python tool that automatically updates NHL Game Day Thread templates with live data from the NHL API and DailyFaceoff. Designed for Rangers game day threads - automatically fetches data for both the Rangers and their opponent.

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
- **TV Broadcasts**: US broadcast networks for the game
- **Radio Stations**: Rangers radio coverage (98.7 FM, 107.1 FM, 710 AM, Sirius XM)
- **GameCenter Link**: Direct link to NHL.com game page

### Team Logos
- Automatically updates logos for both teams throughout the template
- All 32 NHL team logos supported

### Team Data (for both Rangers AND opponent)
- **Standings**: Record, points, division position, ROW, P%, home/away records, shootout record, L10, streak
- **Team Stats**: Goal differential, GF/GP, GA/GP, PP%, PK% (all with league rankings)
- **Team Leaders**: Goals, assists, points, +/-, PIM, TOI/G for defense & forwards
- **Line Combinations**: Forward lines and defense pairings from DailyFaceoff
- **Starting Goaltender**: Name and stats (GS, record, SV%, GAA, SO)
- **Injuries**: Current injured/scratched players from DailyFaceoff

## Requirements

- Python 3.6 or higher
- No external dependencies (uses only Python standard library)

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
| Central | CHI, COL, DAL, MIN, NSH, STL, UTA, WPG |
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

| Data | Source |
|------|--------|
| Game Schedule & Broadcasts | [NHL API](https://api-web.nhle.com) |
| Standings & Stats | [NHL API](https://api-web.nhle.com) |
| PP% & PK% Rankings | [NHL Stats API](https://api.nhle.com/stats) |
| Line Combinations | [DailyFaceoff](https://www.dailyfaceoff.com) |
| Injuries | [DailyFaceoff](https://www.dailyfaceoff.com) |

## License

MIT License - feel free to use and modify as needed.

## Contributing

Pull requests welcome! Feel free to submit issues for bugs or feature requests.
