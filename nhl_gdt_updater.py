#!/usr/bin/env python3
"""
NHL Game Day Thread (GDT) Updater
Updates an HTML template with current NHL team statistics for TWO teams.
Rangers are always the first team; the opponent is specified by the user.

Usage: python nhl_gdt_updater.py <opponent_team> [--file <path_to_template>]
Example: python nhl_gdt_updater.py "Sabres" --file "GDT Test.txt"
"""

import argparse
import json
import re
import sys
from datetime import datetime, timedelta
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

# Full team names for display
TEAM_FULL_NAMES = {
    "ANA": "Anaheim Ducks", "ARI": "Arizona Coyotes", "BOS": "Boston Bruins",
    "BUF": "Buffalo Sabres", "CGY": "Calgary Flames", "CAR": "Carolina Hurricanes",
    "CHI": "Chicago Blackhawks", "COL": "Colorado Avalanche", "CBJ": "Columbus Blue Jackets",
    "DAL": "Dallas Stars", "DET": "Detroit Red Wings", "EDM": "Edmonton Oilers",
    "FLA": "Florida Panthers", "LAK": "Los Angeles Kings", "MIN": "Minnesota Wild",
    "MTL": "Montreal Canadiens", "NSH": "Nashville Predators", "NJD": "New Jersey Devils",
    "NYI": "New York Islanders", "NYR": "New York Rangers", "OTT": "Ottawa Senators",
    "PHI": "Philadelphia Flyers", "PIT": "Pittsburgh Penguins", "SJS": "San Jose Sharks",
    "SEA": "Seattle Kraken", "STL": "St. Louis Blues", "TBL": "Tampa Bay Lightning",
    "TOR": "Toronto Maple Leafs", "UTA": "Utah Hockey Club", "VAN": "Vancouver Canucks",
    "VGK": "Vegas Golden Knights", "WSH": "Washington Capitals", "WPG": "Winnipeg Jets",
}

# Rangers radio stations (static - rarely changes)
NYR_RADIO_STATIONS = "98.7 FM, 107.1 FM, 710 AM, Sirius XM"

# Team logo URLs (hosted on media.invisioncic.com)
TEAM_LOGO_URLS = {
    "CAR": "//media.invisioncic.com/c316106/monthly_2021_09/gdt-logos-car.png.9275f196cd692cf0401852115615f87b.png",
    "CBJ": "//media.invisioncic.com/c316106/monthly_2021_09/gdt-logos-cbj.png.0019056d85e2d1a7b9fed8ccbfc08ab5.png",
    "NJD": "//media.invisioncic.com/c316106/monthly_2021_09/gdt-logos-njd.png.995541c7bd89e48ab72a5b888a62c32f.png",
    "NYI": "//media.invisioncic.com/c316106/monthly_2021_09/gdt-logos-nyi.png.3558ca3bb0b5ff4bfbc066e65b9d8079.png",
    "NYR": "//media.invisioncic.com/c316106/monthly_2021_09/gdt-logos-nyr.png.361dbab7a8ecf15de4e4b3a41c339331.png",
    "PHI": "//media.invisioncic.com/c316106/monthly_2021_09/gdt-logos-phi.png.1d82a65c8446787bf7437b955ff134b7.png",
    "PIT": "//media.invisioncic.com/c316106/monthly_2021_09/gdt-logos-pit.png.cc1de7bfb6706e84d860f54e886b3911.png",
    "WSH": "//media.invisioncic.com/c316106/monthly_2021_09/gdt-logos-wsh.png.9e2e91c1b04fee71e9afc923cfc83973.png",
    "BOS": "//media.invisioncic.com/c316106/monthly_2021_09/gdt-logos-bos.png.9245743e69b7ab2a6fa56f66373a9417.png",
    "BUF": "//media.invisioncic.com/c316106/monthly_2021_09/gdt-logos-buf.png.74b16b6cea5f0178680004507f29d0eb.png",
    "DET": "//media.invisioncic.com/c316106/monthly_2021_09/gdt-logos-det.png.a69165f4270e6f15fa6860e115e37720.png",
    "FLA": "//media.invisioncic.com/c316106/monthly_2021_09/gdt-logos-fla.png.d9422e531543403ed33e88b10cc48af6.png",
    "MTL": "//media.invisioncic.com/c316106/monthly_2021_09/gdt-logos-mtl.png.76ee659aed4e8a8a3c9a45717773e7a1.png",
    "OTT": "//media.invisioncic.com/c316106/monthly_2021_09/gdt-logos-ott.png.30279696b5a596d2471e77be9b32c3c3.png",
    "TOR": "//media.invisioncic.com/c316106/monthly_2021_09/gdt-logos-tor.png.4277ed0b6abaa8a22da800e1c7e44074.png",
    "TBL": "//media.invisioncic.com/c316106/monthly_2021_09/gdt-logos-tbl.png.c002d0a6ddc76500f0088b5bbd848f25.png",
    "CHI": "//media.invisioncic.com/c316106/monthly_2021_09/gdt-logos-chi.png.edec18d1a7e150d08338c7a66e8312e6.png",
    "COL": "//media.invisioncic.com/c316106/monthly_2021_09/gdt-logos-col.png.922f5df84a60dc71e5a4489a25c304d1.png",
    "DAL": "//media.invisioncic.com/c316106/monthly_2021_09/gdt-logos-dal.png.4a83ae6b7cc3f2457dae3ffe380d7513.png",
    "MIN": "//media.invisioncic.com/c316106/monthly_2021_09/gdt-logos-min.png.5d3e06f2ddf7bfda4207af327a93b09e.png",
    "NSH": "//media.invisioncic.com/c316106/monthly_2021_09/gdt-logos-nsh.png.263531c037486a4a0775475e2c666696.png",
    "STL": "//media.invisioncic.com/c316106/monthly_2021_09/gdt-logos-stl.png.be1ee6e3201adb94164ca1be4194a331.png",
    "UTA": "//media.invisioncic.com/c316106/monthly_2026_01/Utah_Mam.png.51f6ebab37070cd7c4de6552f2fdf246.png",
    "WPG": "//media.invisioncic.com/c316106/monthly_2021_09/gdt-logos-wpg.png.ba967dfc0e637107ef9c46436cc6d7c7.png",
    "ANA": "//media.invisioncic.com/c316106/monthly_2024_10/ANA.png.e205426d6dd0c0e62a8ca45f4285a848.png",
    "CGY": "//media.invisioncic.com/c316106/monthly_2021_09/gdt-logos-cgy.png.a6a381a09391cff7eaf233cfe8eccbe8.png",
    "EDM": "//media.invisioncic.com/c316106/monthly_2021_09/gdt-logos-edm.png.7bb6a5835c8fab1e96eacd930be2b112.png",
    "LAK": "//media.invisioncic.com/c316106/monthly_2025_03/gdt-logos-lak.png.94aa50efd13cf820f39951f595ff2fff.png",
    "SJS": "//media.invisioncic.com/c316106/monthly_2021_09/gdt-logos-sjs.png.5aec12c85fc975e9b51615fbb48eafef.png",
    "SEA": "//media.invisioncic.com/c316106/monthly_2021_09/gdt-logos-sea.png.e0dc5b9394fafc197ac47c346d4d271a.png",
    "VAN": "//media.invisioncic.com/c316106/monthly_2021_09/gdt-logos-van.png.193f6d61e70c3faa37823d822d085b19.png",
    "VGK": "//media.invisioncic.com/c316106/monthly_2021_09/gdt-logos-vgk.png.6e5a8a5dcfe130477f1ed83a60e445fd.png",
}

# DailyFaceoff URL slugs for each team
DAILYFACEOFF_SLUGS = {
    "ANA": "anaheim-ducks", "ARI": "arizona-coyotes", "BOS": "boston-bruins",
    "BUF": "buffalo-sabres", "CGY": "calgary-flames", "CAR": "carolina-hurricanes",
    "CHI": "chicago-blackhawks", "COL": "colorado-avalanche", "CBJ": "columbus-blue-jackets",
    "DAL": "dallas-stars", "DET": "detroit-red-wings", "EDM": "edmonton-oilers",
    "FLA": "florida-panthers", "LAK": "los-angeles-kings", "MIN": "minnesota-wild",
    "MTL": "montreal-canadiens", "NSH": "nashville-predators", "NJD": "new-jersey-devils",
    "NYI": "new-york-islanders", "NYR": "new-york-rangers", "OTT": "ottawa-senators",
    "PHI": "philadelphia-flyers", "PIT": "pittsburgh-penguins", "SJS": "san-jose-sharks",
    "SEA": "seattle-kraken", "STL": "st-louis-blues", "TBL": "tampa-bay-lightning",
    "TOR": "toronto-maple-leafs", "UTA": "utah-hockey-club", "VAN": "vancouver-canucks",
    "VGK": "vegas-golden-knights", "WSH": "washington-capitals", "WPG": "winnipeg-jets",
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
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        with urlopen(req, timeout=15) as response:
            return response.read().decode('utf-8')
    except (URLError, HTTPError) as e:
        print(f"Error fetching {url}: {e}")
        return None


def slug_to_name(slug):
    """Convert a URL slug to a proper name (e.g., 'connor-mcdavid' -> 'Connor McDavid')."""
    words = slug.split("-")
    result = []
    i = 0

    while i < len(words):
        word = words[i]
        word_lower = word.lower()

        if len(word) == 1:
            initials = [word.upper()]
            while i + 1 < len(words) and len(words[i + 1]) == 1:
                i += 1
                initials.append(words[i].upper())
            result.append(".".join(initials) + ".")
        elif word_lower.startswith('mc') and len(word_lower) > 2:
            result.append('Mc' + word[2:].capitalize())
        elif word_lower.startswith('mac') and len(word_lower) > 3:
            result.append('Mac' + word[3:].capitalize())
        elif word_lower == "o" and i + 1 < len(words):
            i += 1
            result.append("O'" + words[i].capitalize())
        else:
            result.append(word.capitalize())
        i += 1

    return " ".join(result)


def get_team_abbrev(team_input):
    """Convert team name input to NHL API abbreviation."""
    normalized = team_input.lower().strip()
    if normalized in TEAM_MAPPINGS:
        return TEAM_MAPPINGS[normalized]
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


def find_next_game(team1_abbrev, team2_abbrev):
    """Find the next scheduled game between two teams."""
    print(f"Searching for next {team1_abbrev} vs {team2_abbrev} game...")

    # Get Rangers schedule for the next 30 days
    today = datetime.now()

    for days_ahead in range(60):  # Look up to 60 days ahead
        check_date = today + timedelta(days=days_ahead)
        date_str = check_date.strftime("%Y-%m-%d")

        url = f"https://api-web.nhle.com/v1/schedule/{date_str}"
        data = fetch_json(url)

        if not data or 'gameWeek' not in data:
            continue

        for day in data['gameWeek']:
            for game in day.get('games', []):
                away_abbrev = game.get('awayTeam', {}).get('abbrev')
                home_abbrev = game.get('homeTeam', {}).get('abbrev')

                # Check if this game involves both teams
                teams_in_game = {away_abbrev, home_abbrev}
                if team1_abbrev in teams_in_game and team2_abbrev in teams_in_game:
                    return game

    return None


def get_game_info(game_data):
    """Extract game information from NHL API game data."""
    if not game_data:
        return None

    game_id = game_data.get('id')
    start_time_utc = game_data.get('startTimeUTC')  # ISO format

    # Parse date and time from startTimeUTC
    game_date = None
    formatted_date = ""
    formatted_time = ""

    if start_time_utc:
        try:
            # Parse UTC time
            utc_time = datetime.fromisoformat(start_time_utc.replace('Z', '+00:00'))
            # Convert to Eastern (UTC-5 for EST, UTC-4 for EDT)
            # Use the offset provided by the API if available
            eastern_offset = game_data.get('easternUTCOffset', '-05:00')
            offset_hours = int(eastern_offset.split(':')[0])
            eastern_time = utc_time.replace(tzinfo=None) + timedelta(hours=offset_hours)

            # Format date
            game_date = eastern_time.replace(hour=0, minute=0, second=0, microsecond=0)
            formatted_date = f"{eastern_time.month}/{eastern_time.day}/{eastern_time.strftime('%y')}"

            # Format time
            hour = eastern_time.hour
            minute = eastern_time.minute
            am_pm = "AM" if hour < 12 else "PM"
            if hour > 12:
                hour -= 12
            elif hour == 0:
                hour = 12
            formatted_time = f"{hour}:{minute:02d} {am_pm}"
        except (ValueError, AttributeError) as e:
            formatted_time = "TBD"
            formatted_date = ""

    # Get broadcasts
    tv_broadcasts = []

    broadcasts = game_data.get('tvBroadcasts', [])
    for broadcast in broadcasts:
        network = broadcast.get('network', '')
        country = broadcast.get('countryCode', '')

        # Only include US broadcasts
        if country == 'US' and network:
            tv_broadcasts.append(network)

    # Remove duplicates while preserving order
    seen = set()
    unique_tv = []
    for net in tv_broadcasts:
        if net not in seen:
            seen.add(net)
            unique_tv.append(net)

    # Use gameCenterLink from API if available, otherwise construct it
    gamecenter_url = game_data.get('gameCenterLink', '')
    if gamecenter_url and not gamecenter_url.startswith('http'):
        gamecenter_url = f"https://www.nhl.com{gamecenter_url}"

    return {
        'game_id': game_id,
        'date': formatted_date,
        'date_obj': game_date,
        'time': formatted_time,
        'tv_broadcasts': unique_tv,
        'gamecenter_url': gamecenter_url,
        'away_team': game_data.get('awayTeam', {}).get('abbrev'),
        'home_team': game_data.get('homeTeam', {}).get('abbrev'),
    }


def get_team_game_number(team_abbrev, game_date):
    """Calculate the team's game number for the season."""
    if not game_date:
        return None

    # Get team's schedule and count games up to and including this date
    season_start = datetime(game_date.year if game_date.month >= 10 else game_date.year - 1, 10, 1)

    url = f"https://api-web.nhle.com/v1/club-schedule-season/{team_abbrev}/now"
    data = fetch_json(url)

    if not data or 'games' not in data:
        return None

    game_number = 0
    for game in data['games']:
        game_date_str = game.get('gameDate')
        if game_date_str:
            try:
                gd = datetime.strptime(game_date_str, "%Y-%m-%d")
                if gd <= game_date:
                    game_number += 1
            except ValueError:
                continue

    return game_number


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
        'forwards': [[], [], [], []],
        'defense': [[], [], []],
        'goalies': [],
        'injuries': []
    }

    injuries_marker = html.find('>Injuries<')
    roster_html = html[:injuries_marker] if injuries_marker > 0 else html
    player_slugs = re.findall(r'href="/players/news/([a-zA-Z0-9-]+)/\d+"', roster_html)

    seen = set()
    unique_slugs = []
    for s in player_slugs:
        slug_lower = s.lower()
        if slug_lower not in seen:
            seen.add(slug_lower)
            unique_slugs.append(s)

    player_names = [slug_to_name(s) for s in unique_slugs]

    for i, name in enumerate(player_names[:12]):
        line_num = i // 3
        if line_num < 4:
            lines['forwards'][line_num].append(name)

    for i, name in enumerate(player_names[12:18]):
        pair_num = i // 2
        if pair_num < 3:
            lines['defense'][pair_num].append(name)

    lines['goalies'] = player_names[18:20] if len(player_names) > 18 else []

    # Extract injuries
    injuries_start = html.find('>Injuries<')
    if injuries_start > 0:
        injuries_section = html[injuries_start:injuries_start+10000]
        injury_slugs = re.findall(r'href="/players/news/([a-zA-Z0-9-]+)/\d+"', injuries_section)

        seen_injured = set()
        for slug in injury_slugs:
            slug_lower = slug.lower()
            if slug_lower not in seen_injured and slug_lower not in seen:
                seen_injured.add(slug_lower)
                player_idx = injuries_section.lower().find(slug_lower)
                if player_idx > 0:
                    nearby = injuries_section[player_idx:player_idx+500].lower()
                    status = "IR"
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


def get_team_stats(team_abbrev):
    """Fetch team statistics from NHL API."""
    url = "https://api-web.nhle.com/v1/standings/now"
    standings = fetch_json(url)

    if not standings:
        return None, None

    all_teams = standings.get('standings', [])

    team_data = None
    season_id = None
    for t in all_teams:
        if t.get('teamAbbrev', {}).get('default') == team_abbrev:
            team_data = t
            season_id = t.get('seasonId')
            break

    if not team_data:
        return None, None

    gp = team_data.get('gamesPlayed', 1)
    gf = team_data.get('goalFor', 0)
    ga = team_data.get('goalAgainst', 0)
    diff = team_data.get('goalDifferential', gf - ga)

    gf_per_game = gf / gp if gp > 0 else 0
    ga_per_game = ga / gp if gp > 0 else 0

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
        if t_ga < ga_per_game:
            ga_rank += 1

    pp_pct = 0
    pk_pct = 0
    pp_rank = 1
    pk_rank = 1

    if season_id:
        stats_url = f"https://api.nhle.com/stats/rest/en/team/summary?cayenneExp=seasonId={season_id}"
        team_stats = fetch_json(stats_url)

        if team_stats and 'data' in team_stats:
            target_name = TEAM_FULL_NAMES.get(team_abbrev, '')
            all_stats = team_stats['data']

            for stat in all_stats:
                if stat.get('teamFullName') == target_name:
                    pp_pct = stat.get('powerPlayPct', 0) * 100
                    pk_pct = stat.get('penaltyKillPct', 0) * 100
                    break

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

    def seconds_to_time(seconds):
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}:{secs:02d}"

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
        else:
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

    selected = None
    if goalie_name:
        goalie_name_lower = goalie_name.lower()
        for g in goalies:
            full_name = f"{g.get('firstName', {}).get('default', '')} {g.get('lastName', {}).get('default', '')}".lower()
            if goalie_name_lower in full_name or full_name in goalie_name_lower:
                selected = g
                break

    if not selected:
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


def update_team_logos(content, nyr_abbrev, opponent_abbrev):
    """Update team logos throughout the template."""
    nyr_logo_url = TEAM_LOGO_URLS.get(nyr_abbrev)
    opponent_logo_url = TEAM_LOGO_URLS.get(opponent_abbrev)

    if not nyr_logo_url or not opponent_logo_url:
        print(f"Warning: Could not find logo URLs for {nyr_abbrev} or {opponent_abbrev}")
        return content

    # Find all img tags with data-src containing logo URLs
    # Pattern matches data-src="...invisioncic.com...png..." or "...blueshirtsbrotherhood.com...png..."
    logo_pattern = r'(data-src=")[^"]*(?:invisioncic\.com|blueshirtsbrotherhood\.com)[^"]*\.png[^"]*(")'

    # Find all matches and their positions
    matches = list(re.finditer(logo_pattern, content, re.IGNORECASE))

    if len(matches) < 4:
        print(f"Warning: Found only {len(matches)} logo images, expected 4")

    # Replace logos in reverse order to preserve positions
    # Logo order: 1=NYR (header), 2=Opponent (header), 3=NYR (section), 4=Opponent (section)
    replacements = []
    for i, match in enumerate(matches):
        if i == 0 or i == 2:  # NYR logos (1st and 3rd)
            replacements.append((match.start(), match.end(), f'{match.group(1)}{nyr_logo_url}{match.group(2)}'))
        elif i == 1 or i == 3:  # Opponent logos (2nd and 4th)
            replacements.append((match.start(), match.end(), f'{match.group(1)}{opponent_logo_url}{match.group(2)}'))

    # Apply replacements in reverse order
    for start, end, replacement in reversed(replacements):
        content = content[:start] + replacement + content[end:]

    print(f"Updated logos: NYR and {opponent_abbrev}")
    return content


def update_game_header(content, game_info, nyr_game_number):
    """Update the game header section with game info."""
    if not game_info:
        return content

    # Update game number and date in the header
    # Pattern: REGULAR SEASON GAME #XX &mdash; M/D/YY
    game_header_pattern = r'(REGULAR SEASON GAME #)\d+(\s*&mdash;\s*)\d+/\d+/\d+'
    if nyr_game_number:
        game_header_replacement = rf'\g<1>{nyr_game_number}\g<2>{game_info["date"]}'
        content = re.sub(game_header_pattern, game_header_replacement, content, count=1)

    # Update time
    # Pattern: <b>Time</b>: X:XX PM
    time_pattern = r'(<b>Time</b>:\s*)\d+:\d+\s*[AP]M'
    time_replacement = rf'\g<1>{game_info["time"]}'
    content = re.sub(time_pattern, time_replacement, content, count=1, flags=re.IGNORECASE)

    # Update TV broadcasts
    if game_info['tv_broadcasts']:
        tv_str = ', '.join(game_info['tv_broadcasts'])
        # Pattern: <b>TV</b>: ... <br> or similar
        tv_pattern = r'(<b>TV</b><span>:</span>&nbsp;)[^<]+'
        tv_replacement = rf'\g<1>{tv_str}'
        content = re.sub(tv_pattern, tv_replacement, content, count=1, flags=re.IGNORECASE)

    # Update Radio stations (static for Rangers)
    radio_pattern = r'(<b>&nbsp;Radio</b>:\s*)[^<]+'
    radio_replacement = rf'\g<1>{NYR_RADIO_STATIONS}'
    content = re.sub(radio_pattern, radio_replacement, content, count=1, flags=re.IGNORECASE)

    # Update GameCenter link
    if game_info['gamecenter_url']:
        gc_pattern = r'(href=")[^"]*nhl\.com/gamecenter[^"]*(")'
        gc_replacement = rf'\g<1>{game_info["gamecenter_url"]}\g<2>'
        content = re.sub(gc_pattern, gc_replacement, content, count=1)

    return content


def update_team_section(content, team_abbrev, is_first_team=True):
    """Update a team's section in the template."""
    print(f"Fetching data for {team_abbrev}...")

    standings, stats = get_team_stats(team_abbrev)
    if not standings:
        print(f"Error: Could not fetch standings data for {team_abbrev}")
        return content

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

    # Split content into sections based on <hr> tags
    # First team section is before the second <hr>, second team is after
    hr_pattern = r'<hr\s+style="width:\d+%">'
    hr_matches = list(re.finditer(hr_pattern, content))

    if len(hr_matches) >= 2:
        if is_first_team:
            # First team: from start to second <hr>
            section_start = 0
            section_end = hr_matches[1].start()
        else:
            # Second team: from second <hr> to third <hr> (or end)
            section_start = hr_matches[1].start()
            section_end = hr_matches[2].start() if len(hr_matches) > 2 else len(content)

        section = content[section_start:section_end]
    else:
        # Fallback: process entire content
        section = content
        section_start = 0
        section_end = len(content)

    # Helper to replace content in a section
    def replace_in_section(section_content, pattern, replacement):
        return re.sub(pattern, replacement, section_content, count=1, flags=re.IGNORECASE | re.DOTALL)

    # Update standings - RECORD
    record_pattern = r'(<p\s+data-gdt="[^"]*UPDATE[^"]*RECORD[^"]*">)\s*[^<]*(<b>[^<]*</b>)?\s*(</p>)'
    record_replacement = rf'\1\n\t\t\t\t{record} (<b>{points} Points</b>)\n\t\t\t\2'
    # More specific pattern for record with points
    record_pattern = r'(<p\s+data-gdt="[^"]*UPDATE[^"]*RECORD\*\*\*">)[^<]*(?:<[^>]*>[^<]*</[^>]*>)?[^<]*(</p>)'
    record_replacement = rf'\1\n\t\t\t\t{record} (<b>{points} Points</b>)\n\t\t\t\2'
    section = replace_in_section(section, record_pattern, record_replacement)

    # Update POSITION
    pos_pattern = r'(<p\s+data-gdt="[^"]*UPDATE\s*POSITION[^"]*">)\s*[^<]*(</p>)'
    pos_replacement = rf'\1\n\t\t\t\t{ordinal(div_rank)} &mdash; {div_name}\n\t\t\t\2'
    section = replace_in_section(section, pos_pattern, pos_replacement)

    # Update ROW
    row_pattern = r'(<p\s+data-gdt="[^"]*UPDATE\s*ROW[^"]*">)\s*[^<]*(</p>)'
    row_replacement = rf'\1\n\t\t\t\t{row}\n\t\t\t\2'
    section = replace_in_section(section, row_pattern, row_replacement)

    # Update P%
    pct_pattern = r'(<p\s+data-gdt="[^"]*UPDATE\s*P%[^"]*">)\s*[^<]*(</p>)'
    pct_str = f".{int(pts_pct * 1000):03d}"[:4]
    pct_replacement = rf'\1\n\t\t\t\t{pct_str}\n\t\t\t\2'
    section = replace_in_section(section, pct_pattern, pct_replacement)

    # Update HOME record
    home_pattern = r'(<p\s+data-gdt="[^"]*UPDATE\s*RECORD\s*HOME[^"]*">)\s*[^<]*(</p>)'
    home_replacement = rf'\1\n\t\t\t\t{home_record}\n\t\t\t\2'
    section = replace_in_section(section, home_pattern, home_replacement)

    # Update AWAY record
    away_pattern = r'(<p\s+data-gdt="[^"]*UPDATE\s*RECORD\s*AWAY[^"]*">)\s*[^<]*(</p>)'
    away_replacement = rf'\1\n\t\t\t\t{road_record}\n\t\t\t\2'
    section = replace_in_section(section, away_pattern, away_replacement)

    # Update S/O record
    so_pattern = r'(<p\s+data-gdt="[^"]*UPDATE\s*S/O[^"]*">)\s*[^<]*(</p>)'
    so_replacement = rf'\1\n\t\t\t\t{so_record}\n\t\t\t\2'
    section = replace_in_section(section, so_pattern, so_replacement)

    # Update LAST 10
    l10_pattern = r'(<p\s+data-gdt="[^"]*UPDATE\s*LAST\s*10[^"]*">)\s*[^<]*(</p>)'
    l10_replacement = rf'\1\n\t\t\t\t{l10_record}\n\t\t\t\2'
    section = replace_in_section(section, l10_pattern, l10_replacement)

    # Update STREAK
    streak_pattern = r'(<p\s+data-gdt="[^"]*UPDATE\s*STREAK[^"]*">)\s*[^<]*(</p>)'
    streak_replacement = rf'\1\n\t\t\t\t{streak}\n\t\t\t\2'
    section = replace_in_section(section, streak_pattern, streak_replacement)

    # Update Team Statistics
    if stats:
        diff_str = f"+{stats['diff']}" if stats['diff'] > 0 else str(stats['diff'])

        diff_pattern = r'(<p\s+data-gdt="[^"]*UPDATE[^"]*DIFF[^"]*">)\s*[^<]*(</p>)'
        diff_replacement = rf'\1\n\t\t\t\t{diff_str} ({ordinal(stats["diff_rank"])})\n\t\t\t\2'
        section = replace_in_section(section, diff_pattern, diff_replacement)

        gfgp_pattern = r'(<p\s+data-gdt="[^"]*UPDATE\s*GF/GP[^"]*">)\s*[^<]*(</p>)'
        gfgp_replacement = rf'\1\n\t\t\t\t{stats["gf_per_game"]:.2f} ({ordinal(stats["gf_rank"])})\n\t\t\t\2'
        section = replace_in_section(section, gfgp_pattern, gfgp_replacement)

        gagp_pattern = r'(<p\s+data-gdt="[^"]*UPDATE\s*GA/GP[^"]*">)\s*[^<]*(</p>)'
        gagp_replacement = rf'\1\n\t\t\t\t{stats["ga_per_game"]:.2f} ({ordinal(stats["ga_rank"])})\n\t\t\t\2'
        section = replace_in_section(section, gagp_pattern, gagp_replacement)

        pp_pattern = r'(<p\s+data-gdt="[^"]*UPDATE\s*PP%[^"]*">)\s*[^<]*(</p>)'
        pp_replacement = rf'\1\n\t\t\t\t{stats["pp_pct"]}% ({ordinal(stats["pp_rank"])})\n\t\t\t\2'
        section = replace_in_section(section, pp_pattern, pp_replacement)

        pk_pattern = r'(<p\s+data-gdt="[^"]*UPDATE\s*PK%[^"]*">)\s*[^<]*(</p>)'
        pk_replacement = rf'\1\n\t\t\t\t{stats["pk_pct"]}% ({ordinal(stats["pk_rank"])})\n\t\t\t\2'
        section = replace_in_section(section, pk_pattern, pk_replacement)

    # Update Team Leaders
    goals_pattern = r'(<p\s+data-gdt="[^"]*UPDATE[^"]*GOALS[^"]*">)\s*[^<]*(</p>)'
    goals_replacement = rf'\1\n\t\t\t\t{leaders["goals"]["name"]} ({leaders["goals"]["value"]})\n\t\t\t\2'
    section = replace_in_section(section, goals_pattern, goals_replacement)

    assists_pattern = r'(<p\s+data-gdt="[^"]*UPDATE\s*ASSISTS[^"]*">)\s*[^<]*(</p>)'
    assists_replacement = rf'\1\n\t\t\t\t{leaders["assists"]["name"]} ({leaders["assists"]["value"]})\n\t\t\t\2'
    section = replace_in_section(section, assists_pattern, assists_replacement)

    points_pattern = r'(<p\s+data-gdt="[^"]*UPDATE\s*POINTS[^"]*">)\s*[^<]*(</p>)'
    points_replacement = rf'\1\n\t\t\t\t{leaders["points"]["name"]} ({leaders["points"]["value"]})\n\t\t\t\2'
    section = replace_in_section(section, points_pattern, points_replacement)

    plusminus_pattern = r'(<p\s+data-gdt="[^"]*UPDATE\s*\+/-[^"]*">)\s*[^<]*(</p>)'
    plusminus_replacement = rf'\1\n\t\t\t\t{leaders["plusMinus"]["name"]} ({leaders["plusMinus"]["value"]})\n\t\t\t\2'
    section = replace_in_section(section, plusminus_pattern, plusminus_replacement)

    pim_pattern = r'(<p\s+data-gdt="[^"]*UPDATE\s*PIM[^"]*">)\s*[^<]*(</p>)'
    pim_replacement = rf'\1\n\t\t\t\t{leaders["pim"]["name"]} ({leaders["pim"]["value"]})\n\t\t\t\2'
    section = replace_in_section(section, pim_pattern, pim_replacement)

    toid_pattern = r'(<p\s+data-gdt="[^"]*UPDATE\s*TOI/G\s*\(D\)[^"]*">)\s*[^<]*(</p>)'
    toid_replacement = rf'\1\n\t\t\t\t{leaders["toi_d"]["name"]} ({leaders["toi_d"]["value"]})\n\t\t\t\2'
    section = replace_in_section(section, toid_pattern, toid_replacement)

    toif_pattern = r'(<p\s+data-gdt="[^"]*UPDATE\s*TOI/G\s*\(F\)[^"]*">)\s*[^<]*(</p>)'
    toif_replacement = rf'\1\n\t\t\t\t{leaders["toi_f"]["name"]} ({leaders["toi_f"]["value"]})\n\t\t\t\2'
    section = replace_in_section(section, toif_pattern, toif_replacement)

    # Update goaltender stats
    if goalie:
        gs_pattern = r'(<p\s+data-gdt="[^"]*UPDATE\s*GS[^"]*">)\s*[^<]*(</p>)'
        gs_replacement = rf'\1\n\t\t\t\t{goalie["games_started"]}\n\t\t\t\2'
        section = replace_in_section(section, gs_pattern, gs_replacement)

        rec_pattern = r'(<p\s+data-gdt="[^"]*UPDATE\s*REC[^"]*">)\s*[^<]*(</p>)'
        rec_replacement = rf'\1\n\t\t\t\t{goalie["record"]}\n\t\t\t\2'
        section = replace_in_section(section, rec_pattern, rec_replacement)

        sv_pattern = r'(<p\s+data-gdt="[^"]*UPDATE\s*SV%[^"]*">)\s*[^<]*(</p>)'
        sv_replacement = rf'\1\n\t\t\t\t{goalie["sv_pct"]}\n\t\t\t\2'
        section = replace_in_section(section, sv_pattern, sv_replacement)

        gaa_pattern = r'(<p\s+data-gdt="[^"]*UPDATE\s*GAA[^"]*">)\s*[^<]*(</p>)'
        gaa_replacement = rf'\1\n\t\t\t\t{goalie["gaa"]}\n\t\t\t\2'
        section = replace_in_section(section, gaa_pattern, gaa_replacement)

        so_stat_pattern = r'(<p\s+data-gdt="[^"]*UPDATE\s*SO[^"]*">)\s*[^<]*(</p>)'
        so_stat_replacement = rf'\1\n\t\t\t\t{goalie["shutouts"]}\n\t\t\t\2'
        section = replace_in_section(section, so_stat_pattern, so_stat_replacement)

    # Fetch and update line combinations
    print(f"Fetching line combinations for {team_abbrev} from DailyFaceoff...")
    lines = get_line_combinations(team_abbrev)

    if lines:
        # Build forward lines
        forward_lines = []
        for line in lines['forwards']:
            if len(line) >= 3:
                forward_lines.append(f"{line[0]} / {line[1]} / {line[2]}")
            elif len(line) > 0:
                forward_lines.append(" / ".join(line))

        if forward_lines:
            forwards_html = "<br>\n\t\t".join(forward_lines)
            # Match everything between <p> after "Starting Lineup" and the next </p>, including nested tags
            lineup_pattern = r'(<b>Starting Lineup:\^?</b>\s*</h3>\s*<p>).*?(</p>\s*<p>)'
            lineup_replacement = rf'\1\n\t\t{forwards_html}\n\t\2'
            section = replace_in_section(section, lineup_pattern, lineup_replacement)

        # Build defense pairs
        defense_pairs = []
        for pair in lines['defense']:
            if len(pair) >= 2:
                defense_pairs.append(f"{pair[0]} / {pair[1]}")
            elif len(pair) > 0:
                defense_pairs.append(pair[0])

        if defense_pairs:
            defense_html = "<br>\n\t\t".join(defense_pairs)
            # Find the defense section - handles two patterns:
            # 1. First team: <p>&nbsp;</p> then <p>defense</p>
            # 2. Second team: <p><br>defense</p>
            # Try pattern 1 first (with &nbsp; spacer)
            defense_pattern1 = r'(&nbsp;\s*</p>\s*<p>).*?(</p>\s*(?:<h4>|<h3>\s*<b>Starting Goaltender))'
            defense_replacement = rf'\1\n\t\t{defense_html}\n\t\2'
            new_section = re.sub(defense_pattern1, defense_replacement, section, count=1, flags=re.IGNORECASE | re.DOTALL)

            # If pattern 1 didn't match (section unchanged), try pattern 2 (with <br> start)
            if new_section == section:
                defense_pattern2 = r'(</p>\s*<p>\s*)<br>.*?(</p>\s*(?:<h4>|<h3>\s*<b>Starting Goaltender))'
                defense_replacement2 = rf'\1\n\t\t{defense_html}\n\t\2'
                new_section = re.sub(defense_pattern2, defense_replacement2, section, count=1, flags=re.IGNORECASE | re.DOTALL)

            section = new_section

        # Update starting goaltender name
        if lines['goalies'] and len(lines['goalies']) > 0:
            goalie_name = lines['goalies'][0]
            goalie_name_pattern = r'(<b>Starting Goaltender:</b>\s*</h3>\s*<p>)\s*[^<\n]+(<br>|&nbsp;)'
            goalie_name_replacement = rf'\1\n\t\t{goalie_name}\2'
            section = replace_in_section(section, goalie_name_pattern, goalie_name_replacement)
            print(f"  Starting goaltender: {goalie_name}")

        print(f"  Line combinations updated ({len(forward_lines)} forward lines, {len(defense_pairs)} defense pairs)")

    # Reconstruct content
    content = content[:section_start] + section + content[section_end:]

    return content


def update_template(template_content, opponent_abbrev):
    """Update the template with data for both teams."""
    print("=" * 50)
    print("  Updating Game Day Thread")
    print("=" * 50)
    print()

    nyr_abbrev = "NYR"

    # Update team logos throughout the template
    template_content = update_team_logos(template_content, nyr_abbrev, opponent_abbrev)

    # Find the next game between Rangers and opponent
    game_data = find_next_game(nyr_abbrev, opponent_abbrev)

    if game_data:
        game_info = get_game_info(game_data)
        if game_info:
            print(f"Found game: {game_info['away_team']} @ {game_info['home_team']}")
            print(f"  Date: {game_info['date']}")
            print(f"  Time: {game_info['time']}")
            print(f"  TV: {', '.join(game_info['tv_broadcasts']) if game_info['tv_broadcasts'] else 'TBD'}")
            print(f"  Radio: {NYR_RADIO_STATIONS}")
            print()

            # Get Rangers game number
            nyr_game_number = get_team_game_number(nyr_abbrev, game_info.get('date_obj'))

            # Update game header
            template_content = update_game_header(template_content, game_info, nyr_game_number)
    else:
        print(f"Warning: Could not find upcoming game between {nyr_abbrev} and {opponent_abbrev}")
        print()

    # Update Rangers section (first team)
    print("-" * 40)
    print(f"Updating {nyr_abbrev} (Rangers)...")
    print("-" * 40)
    template_content = update_team_section(template_content, nyr_abbrev, is_first_team=True)
    print()

    # Update opponent section (second team)
    print("-" * 40)
    print(f"Updating {opponent_abbrev} ({TEAM_FULL_NAMES.get(opponent_abbrev, opponent_abbrev)})...")
    print("-" * 40)
    template_content = update_team_section(template_content, opponent_abbrev, is_first_team=False)
    print()

    return template_content


def interactive_mode():
    """Run in interactive mode - prompts user for input."""
    print("=" * 50)
    print("  NHL Game Day Thread (GDT) Updater")
    print("  Rangers vs. Opponent")
    print("=" * 50)
    print()

    print("The Rangers are automatically set as the first team.")
    print("Enter the opponent team name.")
    print()
    print("Supported: Sabres, Oilers, Leafs, Bruins, etc.")
    print("You can use full names, nicknames, or abbreviations")
    print()

    while True:
        team_input = input("Enter opponent team: ").strip()
        if not team_input:
            print("Please enter a team name.")
            continue

        opponent_abbrev = get_team_abbrev(team_input)
        if opponent_abbrev:
            if opponent_abbrev == "NYR":
                print("The Rangers can't play themselves! Enter a different opponent.")
                continue
            print(f"Opponent identified: {opponent_abbrev} ({TEAM_FULL_NAMES.get(opponent_abbrev, '')})")
            break
        else:
            print(f"Could not recognize '{team_input}'. Please try again.")
            print("Examples: Sabres, BUF, Buffalo Sabres, etc.")

    print()

    print("Enter the path to your template file.")
    print("(You can drag and drop the file into this window)")
    print()

    while True:
        file_path = input("Template file path: ").strip()
        file_path = file_path.strip('"').strip("'")

        if not file_path:
            print("Please enter a file path.")
            continue

        import os
        if os.path.exists(file_path):
            break
        else:
            print(f"File not found: {file_path}")
            print("Please check the path and try again.")

    print()

    return opponent_abbrev, file_path


def main():
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(
            description='Update NHL Game Day Thread template with data for Rangers vs Opponent'
        )
        parser.add_argument('opponent', nargs='?',
                          help='Opponent team name (e.g., "Sabres", "BUF")')
        parser.add_argument('--file', '-f', help='Path to the template file')
        parser.add_argument('--output', '-o', help='Output file path (defaults to overwriting input)')
        parser.add_argument('--interactive', '-i', action='store_true', help='Run in interactive mode')

        args = parser.parse_args()

        if args.interactive or not args.opponent:
            opponent_abbrev, file_path = interactive_mode()
            output_path = file_path
        else:
            opponent_abbrev = get_team_abbrev(args.opponent)
            if not opponent_abbrev:
                print(f"Error: Could not recognize team '{args.opponent}'")
                print("Try using the full team name or abbreviation (e.g., 'Sabres', 'BUF')")
                sys.exit(1)

            if opponent_abbrev == "NYR":
                print("Error: Rangers can't play themselves! Enter a different opponent.")
                sys.exit(1)

            print(f"Opponent identified: {opponent_abbrev} ({TEAM_FULL_NAMES.get(opponent_abbrev, '')})")

            if not args.file:
                print("Error: Please specify a template file with --file")
                sys.exit(1)

            file_path = args.file
            output_path = args.output or args.file
    else:
        opponent_abbrev, file_path = interactive_mode()
        output_path = file_path

    # Read template
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            template = f.read()
    except FileNotFoundError:
        print(f"Error: Template file not found: {file_path}")
        input("\nPress Enter to exit...")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading template: {e}")
        input("\nPress Enter to exit...")
        sys.exit(1)

    # Update template
    updated = update_template(template, opponent_abbrev)
    if not updated:
        print("Error: Failed to update template")
        input("\nPress Enter to exit...")
        sys.exit(1)

    # Write output
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(updated)
        print(f"Successfully updated: {output_path}")
    except Exception as e:
        print(f"Error writing output: {e}")
        input("\nPress Enter to exit...")
        sys.exit(1)

    if len(sys.argv) <= 1:
        print()
        input("Press Enter to exit...")


if __name__ == '__main__':
    main()
