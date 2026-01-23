#!/usr/bin/env python3
"""
NHL Game Day Thread (GDT) Updater
Updates an HTML template with current NHL team statistics.

Usage: python nhl_gdt_updater.py <team_name> [--file <path_to_template>]
Example: python nhl_gdt_updater.py "New York Rangers" --file "GDT Test.txt"
"""

import argparse
import json
import re
import sys
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# NHL team mappings (name variations -> API abbreviation)
TEAM_MAPPINGS = {
    # Metropolitan Division
    "carolina hurricanes": "CAR", "hurricanes": "CAR", "canes": "CAR",
    "columbus blue jackets": "CBJ", "blue jackets": "CBJ", "jackets": "CBJ",
    "new jersey devils": "NJD", "devils": "NJD",
    "new york islanders": "NYI", "islanders": "NYI", "isles": "NYI",
    "new york rangers": "NYR", "rangers": "NYR", "nyr": "NYR",
    "philadelphia flyers": "PHI", "flyers": "PHI",
    "pittsburgh penguins": "PIT", "penguins": "PIT", "pens": "PIT",
    "washington capitals": "WSH", "capitals": "WSH", "caps": "WSH",

    # Atlantic Division
    "boston bruins": "BOS", "bruins": "BOS",
    "buffalo sabres": "BUF", "sabres": "BUF",
    "detroit red wings": "DET", "red wings": "DET", "wings": "DET",
    "florida panthers": "FLA", "panthers": "FLA", "cats": "FLA",
    "montreal canadiens": "MTL", "canadiens": "MTL", "habs": "MTL",
    "ottawa senators": "OTT", "senators": "OTT", "sens": "OTT",
    "tampa bay lightning": "TBL", "lightning": "TBL", "bolts": "TBL",
    "toronto maple leafs": "TOR", "maple leafs": "TOR", "leafs": "TOR",

    # Central Division
    "arizona coyotes": "ARI", "coyotes": "ARI", "yotes": "ARI",
    "chicago blackhawks": "CHI", "blackhawks": "CHI", "hawks": "CHI",
    "colorado avalanche": "COL", "avalanche": "COL", "avs": "COL",
    "dallas stars": "DAL", "stars": "DAL",
    "minnesota wild": "MIN", "wild": "MIN",
    "nashville predators": "NSH", "predators": "NSH", "preds": "NSH",
    "st. louis blues": "STL", "st louis blues": "STL", "blues": "STL",
    "winnipeg jets": "WPG", "jets": "WPG",
    "utah hockey club": "UTA", "utah": "UTA",

    # Pacific Division
    "anaheim ducks": "ANA", "ducks": "ANA",
    "calgary flames": "CGY", "flames": "CGY",
    "edmonton oilers": "EDM", "oilers": "EDM", "oil": "EDM",
    "los angeles kings": "LAK", "kings": "LAK",
    "san jose sharks": "SJS", "sharks": "SJS",
    "seattle kraken": "SEA", "kraken": "SEA",
    "vancouver canucks": "VAN", "canucks": "VAN", "nucks": "VAN",
    "vegas golden knights": "VGK", "golden knights": "VGK", "knights": "VGK",
}

DIVISION_NAMES = {
    "Metropolitan": "Metropolitan",
    "Atlantic": "Atlantic",
    "Central": "Central",
    "Pacific": "Pacific"
}

# DailyFaceoff URL slugs for each team
DAILYFACEOFF_SLUGS = {
    "ANA": "anaheim-ducks",
    "ARI": "arizona-coyotes",
    "BOS": "boston-bruins",
    "BUF": "buffalo-sabres",
    "CGY": "calgary-flames",
    "CAR": "carolina-hurricanes",
    "CHI": "chicago-blackhawks",
    "COL": "colorado-avalanche",
    "CBJ": "columbus-blue-jackets",
    "DAL": "dallas-stars",
    "DET": "detroit-red-wings",
    "EDM": "edmonton-oilers",
    "FLA": "florida-panthers",
    "LAK": "los-angeles-kings",
    "MIN": "minnesota-wild",
    "MTL": "montreal-canadiens",
    "NSH": "nashville-predators",
    "NJD": "new-jersey-devils",
    "NYI": "new-york-islanders",
    "NYR": "new-york-rangers",
    "OTT": "ottawa-senators",
    "PHI": "philadelphia-flyers",
    "PIT": "pittsburgh-penguins",
    "SJS": "san-jose-sharks",
    "SEA": "seattle-kraken",
    "STL": "st-louis-blues",
    "TBL": "tampa-bay-lightning",
    "TOR": "toronto-maple-leafs",
    "UTA": "utah-hockey-club",
    "VAN": "vancouver-canucks",
    "VGK": "vegas-golden-knights",
    "WSH": "washington-capitals",
    "WPG": "winnipeg-jets",
}


def fetch_json(url):
    """Fetch JSON data from a URL."""
    try:
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(req, timeout=15) as response:
            return json.loads(response.read().decode('utf-8'))
    except (URLError, HTTPError) as e:
        print(f"Error fetching {url}: {e}")
        return None


def fetch_html(url):
    """Fetch HTML content from a URL."""
    try:
        req = Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        with urlopen(req, timeout=15) as response:
            return response.read().decode('utf-8')
    except (URLError, HTTPError) as e:
        print(f"Error fetching {url}: {e}")
        return None


def slug_to_name(slug):
    """Convert a URL slug to a proper name (e.g., 'connor-mcdavid' -> 'Connor McDavid')."""
    # Handle special cases for Mc/Mac names (e.g., mcdavid -> McDavid)
    words = slug.split("-")
    result = []
    i = 0

    while i < len(words):
        word = words[i]
        word_lower = word.lower()

        # Handle initials (single letters like j-t -> J.T.)
        if len(word) == 1:
            initials = [word.upper()]
            # Collect consecutive single letters
            while i + 1 < len(words) and len(words[i + 1]) == 1:
                i += 1
                initials.append(words[i].upper())
            result.append(".".join(initials) + ".")
        # Handle Mc names (mcdavid -> McDavid, mcmichael -> McMichael)
        elif word_lower.startswith('mc') and len(word_lower) > 2:
            result.append('Mc' + word[2:].capitalize())
        # Handle Mac names (macdonald -> MacDonald)
        elif word_lower.startswith('mac') and len(word_lower) > 3:
            result.append('Mac' + word[3:].capitalize())
        # Handle O' names (o'brien split as o-brien -> O'Brien)
        elif word_lower == "o" and i + 1 < len(words):
            i += 1
            result.append("O'" + words[i].capitalize())
        else:
            result.append(word.capitalize())

        i += 1

    return " ".join(result)


def get_line_combinations(team_abbrev):
    """Fetch line combinations from DailyFaceoff."""
    slug = DAILYFACEOFF_SLUGS.get(team_abbrev)
    if not slug:
        print(f"No DailyFaceoff slug found for {team_abbrev}")
        return None

    url = f"https://www.dailyfaceoff.com/teams/{slug}/line-combinations/"
    html = fetch_html(url)

    if not html:
        return None

    lines = {
        'forwards': [[], [], [], []],  # 4 forward lines, each with [LW, C, RW]
        'defense': [[], [], []],        # 3 defense pairs, each with [LD, RD]
        'goalies': [],                  # Starting goalie(s)
        'injuries': []                  # Injured/scratched players
    }

    # DailyFaceoff structure: player names appear in <span> tags inside <a> links
    # Pattern: <a href="/players/news/{slug}/{id}"><span...>{Name}</span></a>
    # Each player appears twice (image link + name link), so we use unique slugs

    # Extract unique player slugs in order from the page
    # The order is: Forwards (4 lines x 3 players), Defense (3 pairs x 2 players), Goalies
    # IMPORTANT: Only extract from BEFORE the "Injuries" section to avoid including injured players
    injuries_marker = html.find('>Injuries<')
    roster_html = html[:injuries_marker] if injuries_marker > 0 else html
    player_slugs = re.findall(r'href="/players/news/([a-zA-Z0-9-]+)/\d+"', roster_html)

    # Remove duplicates while preserving order
    seen = set()
    unique_slugs = []
    for s in player_slugs:
        slug_lower = s.lower()
        if slug_lower not in seen:
            seen.add(slug_lower)
            unique_slugs.append(s)

    # Convert slugs to names
    player_names = [slug_to_name(s) for s in unique_slugs]

    # Assign players to positions
    # First 12 are forwards (4 lines of 3)
    for i, name in enumerate(player_names[:12]):
        line_num = i // 3
        if line_num < 4:
            lines['forwards'][line_num].append(name)

    # Next 6 are defensemen (3 pairs of 2)
    for i, name in enumerate(player_names[12:18]):
        pair_num = i // 2
        if pair_num < 3:
            lines['defense'][pair_num].append(name)

    # Remaining are goalies (usually 2)
    lines['goalies'] = player_names[18:20] if len(player_names) > 18 else []

    # Validate we got data
    total_forwards = sum(len(line) for line in lines['forwards'])
    total_defense = sum(len(pair) for pair in lines['defense'])

    if total_forwards < 6 or total_defense < 4:
        print(f"Warning: Could not parse enough players from DailyFaceoff (F:{total_forwards}, D:{total_defense})")

    # Extract injuries/scratches
    # DailyFaceoff has a dedicated "Injuries" section
    # Find it by looking for ">Injuries<" header

    injuries_start = html.find('>Injuries<')
    if injuries_start > 0:
        # Get the section after "Injuries" header (next ~5000 chars should cover it)
        injuries_section = html[injuries_start:injuries_start+10000]

        # Find the end of injuries section (usually before next major section or end of container)
        # Look for player slugs in this section
        injury_slugs = re.findall(r'href="/players/news/([a-zA-Z0-9-]+)/\d+"', injuries_section)

        # Get unique injured players
        seen_injured = set()
        for slug in injury_slugs:
            slug_lower = slug.lower()
            if slug_lower not in seen_injured and slug_lower not in seen:
                seen_injured.add(slug_lower)

                # Look for status near this player in the injuries section
                # Status appears as <span>ir</span> or <span>out</span> etc.
                player_idx = injuries_section.lower().find(slug_lower)
                if player_idx > 0:
                    # Check nearby text (within 500 chars after player) for status
                    nearby = injuries_section[player_idx:player_idx+500].lower()
                    status = "IR"  # Default

                    if '>out<' in nearby or '>out ' in nearby:
                        status = "OUT"
                    elif '>dtd<' in nearby or 'day-to-day' in nearby:
                        status = "DTD"
                    elif '>ltir<' in nearby:
                        status = "LTIR"
                    elif '>ir<' in nearby:
                        status = "IR"

                name = slug_to_name(slug)
                lines['injuries'].append({
                    'name': name,
                    'status': status,
                    'detail': "Undisclosed"
                })

    return lines


def get_team_abbrev(team_input):
    """Convert team name input to NHL API abbreviation."""
    normalized = team_input.lower().strip()
    if normalized in TEAM_MAPPINGS:
        return TEAM_MAPPINGS[normalized]
    # Check if it's already an abbreviation
    if normalized.upper() in TEAM_MAPPINGS.values():
        return normalized.upper()
    return None


def ordinal(n):
    """Convert number to ordinal string (1st, 2nd, 3rd, etc.)."""
    if 11 <= (n % 100) <= 13:
        suffix = 'th'
    else:
        suffix = ['th', 'st', 'nd', 'rd', 'th'][min(n % 10, 4)]
    return f"{n}{suffix}"


def format_streak(streak_code, streak_count):
    """Format streak for display (e.g., 'W3', 'L2', 'OT1')."""
    return f"{streak_code}{streak_count}"


def get_standings_data(team_abbrev):
    """Fetch team standings and statistics from NHL API."""
    url = "https://api-web.nhle.com/v1/standings/now"
    data = fetch_json(url)

    if not data or 'standings' not in data:
        return None

    for team in data['standings']:
        if team.get('teamAbbrev', {}).get('default') == team_abbrev:
            return team
    return None


def get_team_stats(team_abbrev):
    """Fetch team statistics from NHL API."""
    # Get standings data
    url = "https://api-web.nhle.com/v1/standings/now"
    standings = fetch_json(url)

    if not standings:
        return None, None

    # Calculate league-wide stats for rankings
    all_teams = standings.get('standings', [])

    # Find team data and get season ID
    team_data = None
    season_id = None
    for t in all_teams:
        if t.get('teamAbbrev', {}).get('default') == team_abbrev:
            team_data = t
            season_id = t.get('seasonId')
            break

    if not team_data:
        return None, None

    # Calculate basic rankings from standings
    gp = team_data.get('gamesPlayed', 1)
    gf = team_data.get('goalFor', 0)
    ga = team_data.get('goalAgainst', 0)
    diff = team_data.get('goalDifferential', gf - ga)

    gf_per_game = gf / gp if gp > 0 else 0
    ga_per_game = ga / gp if gp > 0 else 0

    # Calculate rankings for basic stats
    diff_rank = 1
    gf_rank = 1
    ga_rank = 1

    for t in all_teams:
        t_gp = t.get('gamesPlayed', 1)
        t_diff = t.get('goalDifferential', 0)
        t_gf = t.get('goalFor', 0) / t_gp if t_gp > 0 else 0
        t_ga = t.get('goalAgainst', 0) / t_gp if t_gp > 0 else 0

        if t_diff > diff:
            diff_rank += 1
        if t_gf > gf_per_game:
            gf_rank += 1
        if t_ga < ga_per_game:  # Lower GA is better
            ga_rank += 1

    # Fetch PP% and PK% from stats API (different endpoint)
    pp_pct = 0
    pk_pct = 0
    pp_rank = 1
    pk_rank = 1

    if season_id:
        stats_url = f"https://api.nhle.com/stats/rest/en/team/summary?cayenneExp=seasonId={season_id}"
        team_stats = fetch_json(stats_url)

        if team_stats and 'data' in team_stats:
            # Map abbreviations to full team names for matching
            team_name_map = {
                'NYR': 'New York Rangers', 'NYI': 'New York Islanders',
                'NJD': 'New Jersey Devils', 'PHI': 'Philadelphia Flyers',
                'PIT': 'Pittsburgh Penguins', 'WSH': 'Washington Capitals',
                'CAR': 'Carolina Hurricanes', 'CBJ': 'Columbus Blue Jackets',
                'BOS': 'Boston Bruins', 'BUF': 'Buffalo Sabres',
                'DET': 'Detroit Red Wings', 'FLA': 'Florida Panthers',
                'MTL': 'Montreal Canadiens', 'OTT': 'Ottawa Senators',
                'TBL': 'Tampa Bay Lightning', 'TOR': 'Toronto Maple Leafs',
                'CHI': 'Chicago Blackhawks', 'COL': 'Colorado Avalanche',
                'DAL': 'Dallas Stars', 'MIN': 'Minnesota Wild',
                'NSH': 'Nashville Predators', 'STL': 'St. Louis Blues',
                'WPG': 'Winnipeg Jets', 'UTA': 'Utah Hockey Club',
                'ANA': 'Anaheim Ducks', 'CGY': 'Calgary Flames',
                'EDM': 'Edmonton Oilers', 'LAK': 'Los Angeles Kings',
                'SJS': 'San Jose Sharks', 'SEA': 'Seattle Kraken',
                'VAN': 'Vancouver Canucks', 'VGK': 'Vegas Golden Knights',
                'ARI': 'Arizona Coyotes',
            }
            target_name = team_name_map.get(team_abbrev, '')

            all_stats = team_stats['data']
            for stat in all_stats:
                if stat.get('teamFullName') == target_name:
                    pp_pct = stat.get('powerPlayPct', 0) * 100  # Convert to percentage
                    pk_pct = stat.get('penaltyKillPct', 0) * 100
                    break

            # Calculate PP/PK rankings
            for stat in all_stats:
                t_pp = stat.get('powerPlayPct', 0) * 100
                t_pk = stat.get('penaltyKillPct', 0) * 100
                if t_pp > pp_pct:
                    pp_rank += 1
                if t_pk > pk_pct:
                    pk_rank += 1

    stats = {
        'diff': diff,
        'diff_rank': diff_rank,
        'gf_per_game': round(gf_per_game, 2),
        'gf_rank': gf_rank,
        'ga_per_game': round(ga_per_game, 2),
        'ga_rank': ga_rank,
        'pp_pct': round(pp_pct, 1),
        'pp_rank': pp_rank,
        'pk_pct': round(pk_pct, 1),
        'pk_rank': pk_rank,
    }

    return team_data, stats


def get_team_leaders(team_abbrev):
    """Fetch team leaders from NHL API."""
    # Get roster and stats
    url = f"https://api-web.nhle.com/v1/club-stats/{team_abbrev}/now"
    data = fetch_json(url)

    leaders = {
        'goals': {'name': 'N/A', 'value': 0},
        'assists': {'name': 'N/A', 'value': 0},
        'points': {'name': 'N/A', 'value': 0},
        'plusMinus': {'name': 'N/A', 'value': 0},
        'pim': {'name': 'N/A', 'value': 0},
        'toi_d': {'name': 'N/A', 'value': '0:00'},
        'toi_f': {'name': 'N/A', 'value': '0:00'},
    }

    if not data:
        return leaders

    skaters = data.get('skaters', [])
    goalies = data.get('goalies', [])

    # Find leaders among skaters
    for stat_key, api_key in [('goals', 'goals'), ('assists', 'assists'),
                               ('points', 'points'), ('plusMinus', 'plusMinus'),
                               ('pim', 'penaltyMinutes')]:
        best = None
        best_val = -9999 if stat_key != 'pim' else 0
        for player in skaters:
            val = player.get(api_key, 0)
            if stat_key == 'plusMinus':
                if val > best_val:
                    best_val = val
                    best = player
            elif val > best_val:
                best_val = val
                best = player
        if best:
            name = f"{best.get('firstName', {}).get('default', '')} {best.get('lastName', {}).get('default', '')}".strip()
            if stat_key == 'plusMinus':
                leaders[stat_key] = {'name': name, 'value': f"+{best_val}" if best_val > 0 else str(best_val)}
            else:
                leaders[stat_key] = {'name': name, 'value': best_val}

    # TOI leaders by position
    def seconds_to_time(seconds):
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}:{secs:02d}"

    # Defensemen TOI
    best_d = None
    best_d_toi = 0
    best_f = None
    best_f_toi = 0

    for player in skaters:
        pos = player.get('positionCode', 'F')
        toi = player.get('avgTimeOnIcePerGame', 0)
        if pos == 'D':
            if toi > best_d_toi:
                best_d_toi = toi
                best_d = player
        else:  # Forward
            if toi > best_f_toi:
                best_f_toi = toi
                best_f = player

    if best_d:
        name = f"{best_d.get('firstName', {}).get('default', '')} {best_d.get('lastName', {}).get('default', '')}".strip()
        leaders['toi_d'] = {'name': name, 'value': seconds_to_time(best_d_toi)}

    if best_f:
        name = f"{best_f.get('firstName', {}).get('default', '')} {best_f.get('lastName', {}).get('default', '')}".strip()
        leaders['toi_f'] = {'name': name, 'value': seconds_to_time(best_f_toi)}

    return leaders


def get_goalie_stats(team_abbrev, goalie_name=None):
    """Fetch goaltender statistics."""
    url = f"https://api-web.nhle.com/v1/club-stats/{team_abbrev}/now"
    data = fetch_json(url)

    if not data:
        return None

    goalies = data.get('goalies', [])
    if not goalies:
        return None

    # If goalie name specified, find them; otherwise use starter (most games)
    selected = None
    if goalie_name:
        goalie_name_lower = goalie_name.lower()
        for g in goalies:
            full_name = f"{g.get('firstName', {}).get('default', '')} {g.get('lastName', {}).get('default', '')}".lower()
            if goalie_name_lower in full_name or full_name in goalie_name_lower:
                selected = g
                break

    if not selected:
        # Get goalie with most games played
        selected = max(goalies, key=lambda x: x.get('gamesPlayed', 0))

    if selected:
        wins = selected.get('wins', 0)
        losses = selected.get('losses', 0)
        otl = selected.get('overtimeLosses', 0)

        return {
            'name': f"{selected.get('firstName', {}).get('default', '')} {selected.get('lastName', {}).get('default', '')}".strip(),
            'games_started': selected.get('gamesStarted', selected.get('gamesPlayed', 0)),
            'record': f"{wins}-{losses}-{otl}",
            'sv_pct': f".{int(selected.get('savePercentage', 0) * 1000):03d}"[:4] if selected.get('savePercentage', 0) > 0 else ".000",
            'gaa': f"{selected.get('goalsAgainstAverage', 0):.2f}",
            'shutouts': selected.get('shutouts', 0),
        }
    return None


def update_template(template_content, team_abbrev):
    """Update the template with fetched data."""
    print(f"Fetching data for {team_abbrev}...")

    # Fetch all data
    standings, stats = get_team_stats(team_abbrev)
    if not standings:
        print("Error: Could not fetch standings data")
        return None

    leaders = get_team_leaders(team_abbrev)
    goalie = get_goalie_stats(team_abbrev)

    # Extract standings data
    wins = standings.get('wins', 0)
    losses = standings.get('losses', 0)
    otl = standings.get('otLosses', 0)
    points = standings.get('points', 0)
    record = f"{wins}-{losses}-{otl}"

    div_rank = standings.get('divisionSequence', 0)
    div_name = standings.get('divisionName', 'Division')

    row = standings.get('regulationPlusOtWins', 0)
    pts_pct = standings.get('pointPctg', 0)

    home_wins = standings.get('homeWins', 0)
    home_losses = standings.get('homeLosses', 0)
    home_otl = standings.get('homeOtLosses', 0)
    home_record = f"{home_wins}-{home_losses}-{home_otl}"

    road_wins = standings.get('roadWins', 0)
    road_losses = standings.get('roadLosses', 0)
    road_otl = standings.get('roadOtLosses', 0)
    road_record = f"{road_wins}-{road_losses}-{road_otl}"

    so_wins = standings.get('shootoutWins', 0)
    so_losses = standings.get('shootoutLosses', 0)
    so_record = f"{so_wins}-{so_losses}"

    l10_wins = standings.get('l10Wins', 0)
    l10_losses = standings.get('l10Losses', 0)
    l10_otl = standings.get('l10OtLosses', 0)
    l10_record = f"{l10_wins}-{l10_losses}-{l10_otl}"

    streak_code = standings.get('streakCode', 'W')
    streak_count = standings.get('streakCount', 0)
    streak = format_streak(streak_code, streak_count)

    # Prepare replacements using regex
    content = template_content

    # Helper function to replace content between p tags with specific data-gdt attribute
    def replace_p_content(content, data_gdt_pattern, new_value):
        # Match <p data-gdt="...">...</p> and replace the content
        pattern = rf'(<p\s+data-gdt="[^"]*{data_gdt_pattern}[^"]*">)\s*.*?\s*(</p>)'
        replacement = rf'\1\n\t\t\t\t\t\t\t{new_value}\n\t\t\t\t\t\t\2'
        return re.sub(pattern, replacement, content, flags=re.IGNORECASE | re.DOTALL)

    # Update Standings section (team record first, before goalie section uses same pattern)
    # Use very specific pattern for team record that won't match goalie record
    team_record_pattern = r'(<p\s+data-gdt="\*\*\*UPDATE RECORD\*\*\*">)\s*.*?\s*(</p>)'
    team_record_replacement = rf'\1\n\t\t\t\t\t\t\t{record} (<b>{points} Points</b>)\n\t\t\t\t\t\t\2'
    content = re.sub(team_record_pattern, team_record_replacement, content, count=1, flags=re.IGNORECASE | re.DOTALL)

    content = replace_p_content(content, r'UPDATE POSITION', f'{ordinal(div_rank)} &mdash; {div_name}')
    content = replace_p_content(content, r'UPDATE ROW', str(row))
    content = replace_p_content(content, r'UPDATE POINTS%', f'.{int(pts_pct * 1000):03d}'[:4])
    content = replace_p_content(content, r'UPDATE RECORD HOME', home_record)
    content = replace_p_content(content, r'UPDATE RECORD AWAY', road_record)
    content = replace_p_content(content, r'UPDATE SHOOTOUT', so_record)
    content = replace_p_content(content, r'UPDATE LAST 10', l10_record)
    content = replace_p_content(content, r'UPDATE STREAK', streak)

    # Update Team Statistics section
    if stats:
        diff_str = f"+{stats['diff']}" if stats['diff'] > 0 else str(stats['diff'])
        content = replace_p_content(content, r'GOAL DIFFERENTIAL', f"{diff_str} ({ordinal(stats['diff_rank'])})")
        content = replace_p_content(content, r'GF/GP', f"{stats['gf_per_game']:.2f} ({ordinal(stats['gf_rank'])})")
        content = replace_p_content(content, r'GA/GP', f"{stats['ga_per_game']:.2f} ({ordinal(stats['ga_rank'])})")
        content = replace_p_content(content, r'PP%', f"{stats['pp_pct']}% ({ordinal(stats['pp_rank'])})")
        content = replace_p_content(content, r'PK%', f"{stats['pk_pct']}% ({ordinal(stats['pk_rank'])})")

    # Update Team Leaders section
    content = replace_p_content(content, r'INDIVIDUAL GOALS', f"{leaders['goals']['name']} ({leaders['goals']['value']})")
    content = replace_p_content(content, r'(?:INDIVIDUALASSISTS|INDIVIDUAL ASSISTS)', f"{leaders['assists']['name']} ({leaders['assists']['value']})")
    content = replace_p_content(content, r'INDIVIDUAL POINTS', f"{leaders['points']['name']} ({leaders['points']['value']})")
    content = replace_p_content(content, r'INDIVIDUAL \+/-', f"{leaders['plusMinus']['name']} ({leaders['plusMinus']['value']})")
    content = replace_p_content(content, r'INDIVIDUAL PIM', f"{leaders['pim']['name']} ({leaders['pim']['value']})")
    content = replace_p_content(content, r'DEFENSE', f"{leaders['toi_d']['name']} ({leaders['toi_d']['value']})")
    content = replace_p_content(content, r'OFFENSE', f"{leaders['toi_f']['name']} ({leaders['toi_f']['value']})")

    # Update Goaltender section
    if goalie:
        # Update goaltender name (the <p> tag right after "Starting Goaltender:" header)
        goalie_name_pattern = r'(<b>Starting Goaltender:</b>\s*</h3>\s*<p>)\s*[^<]+<br>'
        goalie_name_replacement = rf'\1\n\t\t\t\t{goalie["name"]}<br>'
        content = re.sub(goalie_name_pattern, goalie_name_replacement, content, flags=re.IGNORECASE | re.DOTALL)

        content = replace_p_content(content, r'GAMES PLAYED', str(goalie['games_started']))
        # Find the second RECORD (goalie record) - bit tricky, use more specific matching
        # The goalie record section is after the "Starting Goaltender" header
        goalie_section_match = re.search(r'(Starting Goaltender.*?data-gdt="[^"]*UPDATE RECORD[^"]*">)\s*.*?\s*(</p>)', content, re.DOTALL | re.IGNORECASE)
        if goalie_section_match:
            old_text = goalie_section_match.group(0)
            new_text = f'{goalie_section_match.group(1)}\n\t\t\t\t\t\t\t{goalie["record"]}\n\t\t\t\t\t\t{goalie_section_match.group(2)}'
            content = content.replace(old_text, new_text)

        content = replace_p_content(content, r'UPDATE SV%', goalie['sv_pct'])
        content = replace_p_content(content, r'UPDATE GAA', goalie['gaa'])
        content = replace_p_content(content, r'UPDATE SO\*\*\*', str(goalie['shutouts']))

    # Fetch and update line combinations from DailyFaceoff
    print("Fetching line combinations from DailyFaceoff...")
    lines = get_line_combinations(team_abbrev)

    if lines:
        # Build forward lines HTML
        forward_lines = []
        for i, line in enumerate(lines['forwards']):
            if len(line) >= 3:
                forward_lines.append(f"{line[0]} / {line[1]} / {line[2]}")
            elif len(line) > 0:
                forward_lines.append(" / ".join(line))

        if forward_lines:
            forwards_html = "<br>\n\t\t\t\t".join(forward_lines)
            # Find and replace the forwards section (first <p> after "Starting Lineup:")
            # Use .*? to match any content including <strong> tags for captain/alternate markers
            lineup_pattern = r'(<b>Starting Lineup:\^?</b>\s*</h3>\s*<p>).*?(</p>\s*<p>\s*&nbsp;)'
            lineup_replacement = rf'\1\n\t\t\t\t{forwards_html}\n\t\t\t\2'
            content = re.sub(lineup_pattern, lineup_replacement, content, count=1, flags=re.IGNORECASE | re.DOTALL)

        # Build defense pairs HTML
        defense_pairs = []
        for pair in lines['defense']:
            if len(pair) >= 2:
                defense_pairs.append(f"{pair[0]} / {pair[1]}")
            elif len(pair) > 0:
                defense_pairs.append(pair[0])

        if defense_pairs:
            defense_html = "<br>\n\t\t\t\t".join(defense_pairs)
            # Find and replace the defense section (third <p> after "Starting Lineup:", after the spacer)
            # Pattern: find the <p> with defense pairings (contains " / " pattern typical of D pairs)
            # The defense section comes after a <p>&nbsp;</p> spacer
            defense_pattern = r'(<p>\s*&nbsp;\s*</p>\s*<p>)\s*[^<]+(?:<br>\s*[^<]+)*\s*(</p>\s*<h3>\s*<b>Starting Goaltender:)'
            defense_replacement = rf'\1\n\t\t\t\t{defense_html}\n\t\t\t\2'
            content = re.sub(defense_pattern, defense_replacement, content, count=1, flags=re.IGNORECASE | re.DOTALL)

        # Update starting goaltender from DailyFaceoff if available
        if lines['goalies'] and len(lines['goalies']) > 0:
            df_goalie_name = lines['goalies'][0]
            goalie_name_pattern = r'(<b>Starting Goaltender:</b>\s*</h3>\s*<p>)\s*[^<]+<br>'
            goalie_name_replacement = rf'\1\n\t\t\t\t{df_goalie_name}<br>'
            content = re.sub(goalie_name_pattern, goalie_name_replacement, content, flags=re.IGNORECASE | re.DOTALL)
            print(f"Starting goaltender: {df_goalie_name}")

        print(f"Line combinations updated ({len(forward_lines)} forward lines, {len(defense_pairs)} defense pairs)")

        # Update injuries section
        if lines.get('injuries'):
            injuries_html_parts = []
            for injury in lines['injuries']:
                # Format: Player Name&nbsp;<span class="gdtAlert">[STATUS]</span> &mdash; Detail
                status = injury['status']
                # Normalize status display
                if status in ['IR', 'LTIR', 'OUT', 'DTD']:
                    status_display = status
                else:
                    status_display = status.upper()

                injury_line = f'{injury["name"]}&nbsp;<span class="gdtAlert">[{status_display}]</span> &mdash; {injury["detail"]}'
                injuries_html_parts.append(injury_line)

            if injuries_html_parts:
                # Build the full injuries HTML
                # Each injury is in its own <p> tag
                injuries_html = "\n\t\t</p>\n\n\n\t\t<p>\n\t\t\t\t".join(injuries_html_parts)

                # Find and replace the injuries section
                # Pattern: from "Injuries, Suspensions" header to the end of the injury <p> tags
                injuries_pattern = r'(<b>Injuries, Suspensions, &amp; Scratches:</b>\s*</h3>)\s*(?:<p>.*?</p>\s*)+'
                injuries_replacement = rf'\1\n\n\n\t\t<p>\n\t\t\t\t{injuries_html}\n\t\t</p>\n\n\n\t\t<p>\n\t\t\t\t&nbsp;\n\t\t</p>\n\n'

                new_content = re.sub(injuries_pattern, injuries_replacement, content, count=1, flags=re.IGNORECASE | re.DOTALL)

                if new_content != content:
                    content = new_content
                    print(f"Injuries updated ({len(lines['injuries'])} players)")
                else:
                    print("Warning: Could not update injuries section (pattern not matched)")
        else:
            print("No injuries found on DailyFaceoff")

    else:
        print("Warning: Could not fetch line combinations from DailyFaceoff")

    return content


def main():
    parser = argparse.ArgumentParser(description='Update NHL Game Day Thread template with team data')
    parser.add_argument('team', help='NHL team name (e.g., "New York Rangers", "Rangers", "NYR")')
    parser.add_argument('--file', '-f', default=r'C:\Users\raysa\Downloads\GDT Test.txt',
                        help='Path to the template file')
    parser.add_argument('--output', '-o', help='Output file path (defaults to overwriting input file)')

    args = parser.parse_args()

    # Resolve team
    team_abbrev = get_team_abbrev(args.team)
    if not team_abbrev:
        print(f"Error: Could not recognize team '{args.team}'")
        print("Try using the full team name (e.g., 'New York Rangers') or abbreviation (e.g., 'NYR')")
        sys.exit(1)

    print(f"Team identified: {team_abbrev}")

    # Read template
    try:
        with open(args.file, 'r', encoding='utf-8-sig') as f:
            template = f.read()
    except FileNotFoundError:
        print(f"Error: Template file not found: {args.file}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading template: {e}")
        sys.exit(1)

    # Update template
    updated = update_template(template, team_abbrev)
    if not updated:
        print("Error: Failed to update template")
        sys.exit(1)

    # Write output
    output_path = args.output or args.file
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(updated)
        print(f"Successfully updated: {output_path}")
    except Exception as e:
        print(f"Error writing output: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
