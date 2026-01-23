# NHL Game Day Thread (GDT) Updater

A Python tool that automatically updates NHL Game Day Thread templates with live team data from the NHL API and DailyFaceoff.

## Downloads

Pre-built executables (no Python required):

| Platform | Download |
|----------|----------|
| Windows | [NHL-GDT-Updater-Windows.exe](releases/NHL-GDT-Updater-Windows.exe) |
| Mac | Coming soon (check Releases) |

### Running the Executable

**Option 1: Interactive Mode (Double-click)**

Just double-click the executable and follow the prompts.

**Option 2: Command Line**

**Windows (Command Prompt or PowerShell):**
```cmd
# Navigate to where you downloaded the exe
cd C:\Users\YourName\Downloads

# Run with team name
NHL-GDT-Updater-Windows.exe Rangers

# Run with a specific template file
NHL-GDT-Updater-Windows.exe Rangers --file "C:\path\to\template.txt"

# Run with custom output file
NHL-GDT-Updater-Windows.exe NYR --file "template.txt" --output "updated.txt"
```

**Mac (Terminal):**
```bash
# Navigate to where you downloaded the file
cd ~/Downloads

# Make it executable (only needed once)
chmod +x NHL-GDT-Updater-Mac

# Run with team name
./NHL-GDT-Updater-Mac Rangers

# Run with a specific template file
./NHL-GDT-Updater-Mac Rangers --file "/path/to/template.txt"

# Run with custom output file
./NHL-GDT-Updater-Mac NYR --file "template.txt" --output "updated.txt"
```

## Features

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
python nhl_gdt_updater.py <team_name> [--file <template_path>] [--output <output_path>]
```

### Examples

```bash
# Update for a team (uses default template location)
python nhl_gdt_updater.py "New York Rangers"

# Use team abbreviation
python nhl_gdt_updater.py NYR

# Use team nickname
python nhl_gdt_updater.py Rangers

# Specify a different template file
python nhl_gdt_updater.py "Boston Bruins" --file "path/to/template.txt"

# Write to a different output file
python nhl_gdt_updater.py NYR --output "path/to/output.txt"
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

### Key Template Tags

```html
<p data-gdt="***UPDATE RECORD***">...</p>
<p data-gdt="***UPDATE POSITION***">...</p>
<p data-gdt="***UPDATE PP% (POSITION)***">...</p>
<!-- etc. -->
```

## Data Sources

| Data | Source |
|------|--------|
| Standings & Stats | [NHL API](https://api-web.nhle.com) |
| PP% & PK% Rankings | [NHL Stats API](https://api.nhle.com/stats) |
| Line Combinations | [DailyFaceoff](https://www.dailyfaceoff.com) |
| Injuries | [DailyFaceoff](https://www.dailyfaceoff.com) |

## License

MIT License - feel free to use and modify as needed.

## Contributing

Pull requests welcome! Feel free to submit issues for bugs or feature requests.
