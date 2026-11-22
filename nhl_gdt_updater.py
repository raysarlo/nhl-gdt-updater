#!/usr/bin/env python3
"""
NHL Game Day Thread (GDT) Updater
Updates an HTML template with current NHL team statistics for TWO teams.
Rangers are always the first team; the opponent is specified by the user.

Usage: python nhl_gdt_updater.py <opponent_team> [--file <path_to_template>]
Example: python nhl_gdt_updater.py "Sabres" --file "GDT Test.txt"

Data sources (in priority order, each step falls back to the next):
  Schedule, standings, stats, leaders, goalie stats ... NHL API (api-web.nhle.com)
  PP% / PK% .......................................... NHL Stats API (api.nhle.com)
  Line combinations ... DailyFaceoff page JSON  ->  derived from NHL shift charts
                        of the team's most recent game
  Starting goalie ..... DailyFaceoff "Confirmed"/"Likely"  ->  rule-based projection
                        from NHL box scores  ->  DailyFaceoff unconfirmed pick
  Injuries ............ ESPN injuries API  ->  DailyFaceoff injured list

Only the Python standard library is used, so the script can be bundled into a
single executable with PyInstaller.
"""

import argparse
import gzip
import html as html_module
import json
import logging
import os
import re
import sys
import time
import unicodedata
import zlib
from datetime import date, datetime, timedelta
from itertools import combinations, permutations
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

log = logging.getLogger("gdt")

NYR = "NYR"

# Rangers radio stations (static - rarely changes)
NYR_RADIO_STATIONS = "98.7 FM, 107.1 FM, 710 AM, Sirius XM"

NHL_API = "https://api-web.nhle.com/v1"
NHL_STATS_API = "https://api.nhle.com/stats/rest/en"
DAILYFACEOFF = "https://www.dailyfaceoff.com"
ESPN_INJURIES_API = "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/injuries"
ROTOWIRE_LINEUPS = "https://www.rotowire.com/hockey/nhl-lineups.php"

# Game states from the NHL API that mean a game is over
FINISHED_STATES = {"OFF", "FINAL"}

# How many recent games to look at when projecting a starting goalie
GOALIE_LOOKBACK_GAMES = 5

# ---------------------------------------------------------------------------
# Team reference data
# ---------------------------------------------------------------------------

# abbreviation -> (full name, DailyFaceoff URL slug)
TEAMS = {
    "ANA": ("Anaheim Ducks", "anaheim-ducks"),
    "BOS": ("Boston Bruins", "boston-bruins"),
    "BUF": ("Buffalo Sabres", "buffalo-sabres"),
    "CGY": ("Calgary Flames", "calgary-flames"),
    "CAR": ("Carolina Hurricanes", "carolina-hurricanes"),
    "CHI": ("Chicago Blackhawks", "chicago-blackhawks"),
    "COL": ("Colorado Avalanche", "colorado-avalanche"),
    "CBJ": ("Columbus Blue Jackets", "columbus-blue-jackets"),
    "DAL": ("Dallas Stars", "dallas-stars"),
    "DET": ("Detroit Red Wings", "detroit-red-wings"),
    "EDM": ("Edmonton Oilers", "edmonton-oilers"),
    "FLA": ("Florida Panthers", "florida-panthers"),
    "LAK": ("Los Angeles Kings", "los-angeles-kings"),
    "MIN": ("Minnesota Wild", "minnesota-wild"),
    "MTL": ("Montreal Canadiens", "montreal-canadiens"),
    "NSH": ("Nashville Predators", "nashville-predators"),
    "NJD": ("New Jersey Devils", "new-jersey-devils"),
    "NYI": ("New York Islanders", "new-york-islanders"),
    "NYR": ("New York Rangers", "new-york-rangers"),
    "OTT": ("Ottawa Senators", "ottawa-senators"),
    "PHI": ("Philadelphia Flyers", "philadelphia-flyers"),
    "PIT": ("Pittsburgh Penguins", "pittsburgh-penguins"),
    "SJS": ("San Jose Sharks", "san-jose-sharks"),
    "SEA": ("Seattle Kraken", "seattle-kraken"),
    "STL": ("St. Louis Blues", "st-louis-blues"),
    "TBL": ("Tampa Bay Lightning", "tampa-bay-lightning"),
    "TOR": ("Toronto Maple Leafs", "toronto-maple-leafs"),
    "UTA": ("Utah Mammoth", "utah-mammoth"),
    "VAN": ("Vancouver Canucks", "vancouver-canucks"),
    "VGK": ("Vegas Golden Knights", "vegas-golden-knights"),
    "WSH": ("Washington Capitals", "washington-capitals"),
    "WPG": ("Winnipeg Jets", "winnipeg-jets"),
}

TEAM_FULL_NAMES = {abbrev: info[0] for abbrev, info in TEAMS.items()}
DAILYFACEOFF_SLUGS = {abbrev: info[1] for abbrev, info in TEAMS.items()}

# Nicknames, cities and other aliases -> abbreviation.
# Full names and abbreviations are added automatically below.
_TEAM_ALIASES = {
    "CAR": ["hurricanes", "canes", "carolina"],
    "CBJ": ["blue jackets", "jackets", "columbus"],
    "NJD": ["devils", "new jersey", "nj"],
    "NYI": ["islanders", "isles"],
    "NYR": ["rangers", "blueshirts"],
    "PHI": ["flyers", "philadelphia", "philly"],
    "PIT": ["penguins", "pens", "pittsburgh"],
    "WSH": ["capitals", "caps", "washington"],
    "BOS": ["bruins", "boston"],
    "BUF": ["sabres", "buffalo"],
    "DET": ["red wings", "wings", "detroit"],
    "FLA": ["panthers", "cats", "florida"],
    "MTL": ["canadiens", "habs", "montreal", "montréal canadiens", "montréal"],
    "OTT": ["senators", "sens", "ottawa"],
    "TBL": ["lightning", "bolts", "tampa bay", "tampa", "tb"],
    "TOR": ["maple leafs", "leafs", "toronto"],
    "CHI": ["blackhawks", "hawks", "chicago"],
    "COL": ["avalanche", "avs", "colorado"],
    "DAL": ["stars", "dallas"],
    "MIN": ["wild", "minnesota"],
    "NSH": ["predators", "preds", "nashville"],
    "STL": ["blues", "st louis blues", "st. louis", "st louis"],
    "UTA": ["mammoth", "utah", "utah hockey club", "utah hc"],
    "WPG": ["jets", "winnipeg"],
    "ANA": ["ducks", "anaheim"],
    "CGY": ["flames", "calgary"],
    "EDM": ["oilers", "oil", "edmonton"],
    "LAK": ["kings", "los angeles", "la kings", "la"],
    "SJS": ["sharks", "san jose", "sj"],
    "SEA": ["kraken", "seattle"],
    "VAN": ["canucks", "nucks", "vancouver"],
    "VGK": ["golden knights", "knights", "vegas"],
}

TEAM_MAPPINGS = {}
for _abbrev, (_name, _slug) in TEAMS.items():
    TEAM_MAPPINGS[_name.lower()] = _abbrev
    TEAM_MAPPINGS[_abbrev.lower()] = _abbrev
    for _alias in _TEAM_ALIASES.get(_abbrev, []):
        TEAM_MAPPINGS[_alias] = _abbrev

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


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def normalize_name(name):
    """Lower-case a name and strip accents/punctuation for loose matching.

    'Alexis Lafrenière' -> 'alexis lafreniere', 'Montréal Canadiens' -> 'montreal canadiens'
    """
    if not name:
        return ""
    text = unicodedata.normalize("NFKD", name)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9 ]", " ", text.lower())
    return " ".join(text.split())


def get_team_abbrev(team_input):
    """Convert team name input to NHL API abbreviation (or None)."""
    if not team_input:
        return None
    normalized = team_input.lower().strip()
    if normalized in TEAM_MAPPINGS:
        return TEAM_MAPPINGS[normalized]
    loose = normalize_name(team_input)
    for alias, abbrev in TEAM_MAPPINGS.items():
        if normalize_name(alias) == loose:
            return abbrev
    return None


def ordinal(n):
    """Convert number to ordinal string (1st, 2nd, 3rd, etc.)."""
    if 11 <= (n % 100) <= 13:
        suffix = 'th'
    else:
        suffix = ['th', 'st', 'nd', 'rd', 'th'][min(n % 10, 4)]
    return f"{n}{suffix}"


def format_three_decimals(value):
    """Format a 0-1 fraction hockey-style: 0.9091 -> '.909', 1.0 -> '1.000'."""
    text = f"{float(value or 0):.3f}"
    return text[1:] if text.startswith("0") else text


def format_streak(streak_code, streak_count):
    """Format streak for display (e.g., 'W3', 'L2', 'OT1')."""
    return f"{streak_code}{streak_count}"


def player_full_name(player):
    """Full name from an NHL API player record with firstName/lastName dicts."""
    first = (player.get('firstName') or {}).get('default', '')
    last = (player.get('lastName') or {}).get('default', '')
    return f"{first} {last}".strip()


def parse_clock(text):
    """'MM:SS' -> seconds."""
    try:
        minutes, seconds = text.split(":")
        return int(minutes) * 60 + int(seconds)
    except (AttributeError, ValueError):
        return 0


def parse_utc_offset(text):
    """'-05:00' -> timedelta(hours=-5)."""
    match = re.match(r'^([+-])(\d{1,2}):?(\d{2})?$', (text or "").strip())
    if not match:
        return timedelta(hours=-5)
    sign = -1 if match.group(1) == '-' else 1
    return sign * timedelta(hours=int(match.group(2)), minutes=int(match.group(3) or 0))


def eastern_today():
    """Today's date (YYYY-MM-DD) in US Eastern time."""
    try:
        from zoneinfo import ZoneInfo  # Python 3.9+
        return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    except Exception:  # zoneinfo/tzdata unavailable: approximate with EST
        return (datetime.utcnow() - timedelta(hours=5)).strftime("%Y-%m-%d")


def add_note(notes, message):
    """Log a message the user should see and record it for the web UI."""
    log.warning("NOTE: %s", message)
    if notes is not None:
        notes.append(message)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

# Only markers that appear on Cloudflare's interstitial pages. (Normal pages served
# through Cloudflare can include a "challenge-platform" script, so that isn't one.)
_CHALLENGE_MARKERS = (
    "<title>just a moment",
    "_cf_chl_opt",
    "cf-chl-",
    "attention required! | cloudflare",
    "enable javascript and cookies to continue",
)


def looks_like_bot_challenge(body):
    """True if an HTML body is a Cloudflare-style bot challenge page."""
    if not body:
        return False
    head = body[:5000].lower()
    return any(marker in head for marker in _CHALLENGE_MARKERS)


class HttpClient:
    """Tiny urllib wrapper with a per-run cache, retries, and bot-wall detection.

    A new client is created for every GDT generation so data is always fresh,
    but the same URL is never downloaded twice within one run.
    """

    USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')

    def __init__(self, timeout=10, retries=1):
        self.timeout = timeout
        self.retries = retries
        self._cache = {}
        self.blocked_hosts = set()
        self._dead_hosts = set()  # unreachable this run; don't keep waiting on them

    @staticmethod
    def _host(url):
        return re.sub(r'^https?://([^/]+).*$', r'\1', url)

    def get_text(self, url, accept="text/html,application/xhtml+xml,*/*;q=0.8"):
        if url in self._cache:
            return self._cache[url]
        host = self._host(url)
        if host in self.blocked_hosts or host in self._dead_hosts:
            return None

        text = None
        for attempt in range(self.retries + 1):
            try:
                req = Request(url, headers={
                    'User-Agent': self.USER_AGENT,
                    'Accept': accept,
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate',
                })
                with urlopen(req, timeout=self.timeout) as response:
                    text = self._decode(response.read(), response.info().get('Content-Encoding'))
                if looks_like_bot_challenge(text):
                    self._report_blocked(url, "challenge page")
                    text = None
                break
            except HTTPError as e:
                body = ""
                try:
                    body = self._decode(e.read(), e.headers.get('Content-Encoding') if e.headers else None)
                except Exception:
                    pass
                if looks_like_bot_challenge(body) or (e.code in (403, 429) and 'cloudflare' in body.lower()):
                    self._report_blocked(url, f"HTTP {e.code}")
                    break
                if e.code >= 500 or e.code == 429:
                    log.debug("HTTP %s for %s (attempt %d)", e.code, url, attempt + 1)
                else:
                    log.warning("HTTP %s fetching %s", e.code, url)
                    break
            except (URLError, OSError) as e:  # includes timeouts and connection resets
                log.debug("Network error for %s (attempt %d): %s", url, attempt + 1, e)
                if attempt == self.retries:
                    log.warning("Could not reach %s: %s", host, e)
                    self._dead_hosts.add(host)
            if attempt < self.retries:
                time.sleep(1.0 * (attempt + 1))

        self._cache[url] = text
        return text

    def get_json(self, url):
        cache_key = ("json", url)
        if cache_key in self._cache:
            return self._cache[cache_key]
        text = self.get_text(url, accept="application/json")
        data = None
        if text:
            try:
                data = json.loads(text)
            except ValueError:
                log.warning("Invalid JSON from %s", url)
        self._cache[cache_key] = data
        return data

    def _report_blocked(self, url, reason):
        host = self._host(url)
        self.blocked_hosts.add(host)
        log.warning("%s blocked the request (bot protection, %s)", host, reason)

    @staticmethod
    def _decode(data, encoding):
        if encoding == 'gzip':
            data = gzip.decompress(data)
        elif encoding == 'deflate':
            try:
                data = zlib.decompress(data)
            except zlib.error:
                data = zlib.decompress(data, -zlib.MAX_WBITS)
        return data.decode('utf-8', errors='replace')


# ---------------------------------------------------------------------------
# Schedule / game info
# ---------------------------------------------------------------------------

def get_season_schedule(http, team_abbrev):
    """All games (preseason, regular season, playoffs) for a team's current season."""
    data = http.get_json(f"{NHL_API}/club-schedule-season/{team_abbrev}/now")
    games = (data or {}).get('games') or []
    return sorted(games, key=lambda g: g.get('startTimeUTC') or '')


def _game_teams(game):
    return (game.get('awayTeam', {}).get('abbrev'), game.get('homeTeam', {}).get('abbrev'))


def find_next_game(schedule, opponent_abbrev):
    """First game against the opponent that hasn't finished yet."""
    for game in schedule:
        if opponent_abbrev in _game_teams(game) and game.get('gameState') not in FINISHED_STATES:
            return game
    return None


def get_game_number(schedule, game):
    """1-based game number of `game` among the team's games of the same type."""
    if not game:
        return None
    count = 0
    for g in schedule:
        if g.get('gameType') == game.get('gameType'):
            count += 1
            if g.get('id') == game.get('id'):
                return count
    return None


def completed_games_before(schedule, game_date=None):
    """Finished games, most recent first, optionally only those before game_date."""
    games = [g for g in schedule if g.get('gameState') in FINISHED_STATES]
    if game_date:
        games = [g for g in games if (g.get('gameDate') or '') < game_date]
    return list(reversed(games))


def select_broadcasts(broadcasts, team_is_home):
    """US TV networks a fan of the team can watch: national + the team's own regional.

    The NHL API tags each broadcast with a market: N (national), H (home team's
    regional) or A (away team's regional). The other team's regional feed is skipped.
    """
    team_market = 'H' if team_is_home else 'A'
    us = [b for b in broadcasts or [] if b.get('countryCode') == 'US' and b.get('network')]
    chosen = [b for b in us if b.get('market') in ('N', team_market)]
    if not chosen:
        chosen = us
    networks = []
    for b in chosen:
        if b['network'] not in networks:
            networks.append(b['network'])
    return networks


def get_game_info(game_data, team_abbrev=NYR):
    """Extract display-ready game information from an NHL API schedule entry."""
    if not game_data:
        return None

    formatted_date = ""
    formatted_time = "TBD"
    eastern_date = game_data.get('gameDate')

    start_time_utc = game_data.get('startTimeUTC')
    if start_time_utc:
        try:
            utc_time = datetime.fromisoformat(start_time_utc.replace('Z', '+00:00')).replace(tzinfo=None)
            eastern = utc_time + parse_utc_offset(game_data.get('easternUTCOffset', '-05:00'))
            formatted_date = f"{eastern.month}/{eastern.day}/{eastern.strftime('%y')}"
            hour12 = eastern.hour % 12 or 12
            am_pm = "AM" if eastern.hour < 12 else "PM"
            formatted_time = f"{hour12}:{eastern.minute:02d} {am_pm}"
            eastern_date = eastern.strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            pass

    away, home = _game_teams(game_data)
    gamecenter_url = game_data.get('gameCenterLink', '')
    if gamecenter_url and not gamecenter_url.startswith('http'):
        gamecenter_url = f"https://www.nhl.com{gamecenter_url}"

    return {
        'game_id': game_data.get('id'),
        'game_type': game_data.get('gameType', 2),
        'date': formatted_date,
        'eastern_date': eastern_date,          # YYYY-MM-DD
        'time': formatted_time,
        'tv_broadcasts': select_broadcasts(game_data.get('tvBroadcasts'), team_is_home=(home == team_abbrev)),
        'gamecenter_url': gamecenter_url,
        'away_team': away,
        'home_team': home,
    }


# ---------------------------------------------------------------------------
# Standings, team stats, leaders
# ---------------------------------------------------------------------------

def get_standings(http):
    data = http.get_json(f"{NHL_API}/standings/now")
    return (data or {}).get('standings') or []


def find_team_standing(standings, team_abbrev):
    for team in standings:
        if team.get('teamAbbrev', {}).get('default') == team_abbrev:
            return team
    return None


def get_club_stats(http, team_abbrev):
    return http.get_json(f"{NHL_API}/club-stats/{team_abbrev}/now") or {}


def get_team_stats(http, team_abbrev, standings, game_type=2):
    """Goal differential, GF/GP, GA/GP, PP%, PK% with league ranks."""
    team_data = find_team_standing(standings, team_abbrev)
    if not team_data:
        return None

    def per_game(t, key):
        gp = t.get('gamesPlayed', 0)
        return t.get(key, 0) / gp if gp else 0

    diff = team_data.get('goalDifferential', team_data.get('goalFor', 0) - team_data.get('goalAgainst', 0))
    gf_per_game = per_game(team_data, 'goalFor')
    ga_per_game = per_game(team_data, 'goalAgainst')

    diff_rank = 1 + sum(1 for t in standings if t.get('goalDifferential', 0) > diff)
    gf_rank = 1 + sum(1 for t in standings if per_game(t, 'goalFor') > gf_per_game)
    ga_rank = 1 + sum(1 for t in standings if per_game(t, 'goalAgainst') < ga_per_game)

    pp_pct = pk_pct = 0.0
    pp_rank = pk_rank = None
    season_id = team_data.get('seasonId')
    if season_id:
        url = (f"{NHL_STATS_API}/team/summary?cayenneExp="
               f"gameTypeId={game_type}%20and%20seasonId={season_id}")
        summary = (http.get_json(url) or {}).get('data') or []
        target = normalize_name(TEAM_FULL_NAMES.get(team_abbrev, ''))
        mine = next((s for s in summary if normalize_name(s.get('teamFullName')) == target), None)
        if mine:
            pp_pct = (mine.get('powerPlayPct') or 0) * 100
            pk_pct = (mine.get('penaltyKillPct') or 0) * 100
            pp_rank = 1 + sum(1 for s in summary if (s.get('powerPlayPct') or 0) * 100 > pp_pct)
            pk_rank = 1 + sum(1 for s in summary if (s.get('penaltyKillPct') or 0) * 100 > pk_pct)
        else:
            log.warning("No special-teams stats found for %s", team_abbrev)

    return {
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


def get_team_leaders(club_stats, team_games_played=0):
    """Team leaders from NHL club-stats. TOI leaders must have played a third of team games."""
    leaders = {
        'goals': {'name': 'N/A', 'value': 0},
        'assists': {'name': 'N/A', 'value': 0},
        'points': {'name': 'N/A', 'value': 0},
        'plusMinus': {'name': 'N/A', 'value': 0},
        'pim': {'name': 'N/A', 'value': 0},
        'toi_d': {'name': 'N/A', 'value': '0:00'},
        'toi_f': {'name': 'N/A', 'value': '0:00'},
    }
    skaters = (club_stats or {}).get('skaters') or []
    if not skaters:
        return leaders

    for stat_key, api_key in [('goals', 'goals'), ('assists', 'assists'), ('points', 'points'),
                              ('plusMinus', 'plusMinus'), ('pim', 'penaltyMinutes')]:
        best = max(skaters, key=lambda p: p.get(api_key, 0))
        value = best.get(api_key, 0)
        if stat_key != 'plusMinus' and value <= 0:
            continue
        if stat_key == 'plusMinus':
            value = f"+{value}" if value > 0 else str(value)
        leaders[stat_key] = {'name': player_full_name(best), 'value': value}

    min_games = max(1, team_games_played // 3)
    qualified = [p for p in skaters if p.get('gamesPlayed', 0) >= min_games] or skaters

    def seconds_to_time(seconds):
        return f"{int(seconds // 60)}:{int(seconds % 60):02d}"

    for key, is_defense in (('toi_d', True), ('toi_f', False)):
        group = [p for p in qualified if (p.get('positionCode') == 'D') == is_defense]
        if group:
            best = max(group, key=lambda p: p.get('avgTimeOnIcePerGame', 0))
            leaders[key] = {'name': player_full_name(best),
                            'value': seconds_to_time(best.get('avgTimeOnIcePerGame', 0))}
    return leaders


def get_goalie_stats(club_stats, goalie_name=None, player_id=None):
    """Season stats for a goalie (matched by id or name); defaults to the goalie with most starts."""
    goalies = (club_stats or {}).get('goalies') or []
    if not goalies:
        return None

    selected = None
    if player_id:
        selected = next((g for g in goalies if g.get('playerId') == player_id), None)
    if not selected and goalie_name:
        wanted = normalize_name(goalie_name)
        wanted_last = wanted.split(" ")[-1] if wanted else ""
        for g in goalies:
            full = normalize_name(player_full_name(g))
            if full == wanted or (wanted and (wanted in full or full in wanted)):
                selected = g
                break
        if not selected and wanted_last:
            matches = [g for g in goalies if normalize_name(player_full_name(g)).split(" ")[-1] == wanted_last]
            if len(matches) == 1:
                selected = matches[0]
    if not selected:
        if goalie_name:
            log.warning("Goalie '%s' not found in team stats; using the goalie with most starts", goalie_name)
        selected = max(goalies, key=lambda g: (g.get('gamesStarted', 0), g.get('gamesPlayed', 0)))

    wins = selected.get('wins', 0)
    losses = selected.get('losses', 0)
    otl = selected.get('overtimeLosses', 0)
    return {
        'name': player_full_name(selected),
        'player_id': selected.get('playerId'),
        'games_started': selected.get('gamesStarted', wins + losses + otl),
        'record': f"{wins}-{losses}-{otl}",
        'sv_pct': format_three_decimals(selected.get('savePercentage', 0)),
        'gaa': f"{selected.get('goalsAgainstAverage', 0):.2f}",
        'shutouts': selected.get('shutouts', 0),
    }


# ---------------------------------------------------------------------------
# DailyFaceoff (page JSON)
# ---------------------------------------------------------------------------

def extract_next_data(page_html):
    """Return the parsed __NEXT_DATA__ JSON embedded in a Next.js page, or None."""
    if not page_html:
        return None
    match = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', page_html, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except ValueError:
        return None


_INJURY_STATUS_MAP = {
    'ir': 'IR', 'ltir': 'LTIR', 'out': 'OUT', 'dtd': 'DTD', 'day-to-day': 'DTD',
    'susp': 'SUSP', 'suspended': 'SUSP', 'suspension': 'SUSP',
    'injured reserve': 'IR', 'long-term injured reserve': 'LTIR',
    'questionable': 'Q', 'doubtful': 'D', 'probable': 'P',
}


def parse_dailyfaceoff_lineup(next_data):
    """Parse DailyFaceoff team line-combinations page data.

    Returns {'forwards': [[lw, c, rw] x4], 'defense': [[ld, rd] x3], 'goalies': [g1, g2],
             'injuries': [...], 'updated_at': str} or None.
    """
    try:
        combos = next_data['props']['pageProps']['combinations']
        players = combos['players']
    except (KeyError, TypeError):
        return None

    slot_order = {'lw': 0, 'c': 1, 'rw': 2, 'ld': 0, 'rd': 1, 'g1': 0, 'g2': 1}
    groups = {}
    injuries = []
    for p in players:
        category = p.get('categoryIdentifier')
        group = p.get('groupIdentifier') or ''
        name = (p.get('name') or '').strip()
        if not name:
            continue
        if category == 'ev':
            groups.setdefault(group, []).append((slot_order.get(p.get('positionIdentifier'), 9), name))
        elif category == 'oi':
            raw = (p.get('injuryStatus') or group or 'ir').lower()
            injuries.append({'name': name, 'status': _INJURY_STATUS_MAP.get(raw, raw.upper()),
                             'detail': 'Undisclosed'})

    def names(group_id):
        return [n for _, n in sorted(groups.get(group_id, []))]

    lineup = {
        'forwards': [names(f"f{i}") for i in range(1, 5)],
        'defense': [names(f"d{i}") for i in range(1, 4)],
        'goalies': names('g'),
        'injuries': injuries,
        'updated_at': combos.get('updatedAt'),
    }
    if not any(lineup['forwards']) and not any(lineup['defense']):
        return None
    return lineup


def get_dailyfaceoff_lineup(http, team_abbrev):
    slug = DAILYFACEOFF_SLUGS.get(team_abbrev)
    if not slug:
        return None
    page = http.get_text(f"{DAILYFACEOFF}/teams/{slug}/line-combinations")
    lineup = parse_dailyfaceoff_lineup(extract_next_data(page))
    if page and not lineup:
        log.warning("DailyFaceoff page for %s loaded but had no line data (site layout may have changed)",
                    team_abbrev)
    return lineup


def parse_dailyfaceoff_starting_goalie(next_data, team_abbrev):
    """Find the team's goalie on a DailyFaceoff starting-goalies page.

    Returns {'name', 'status'} where status is DailyFaceoff's label
    ('Confirmed', 'Likely', ...) or 'Unconfirmed' when no news yet.
    """
    slug = DAILYFACEOFF_SLUGS.get(team_abbrev)
    try:
        games = next_data['props']['pageProps']['data'] or []
    except (KeyError, TypeError):
        return None
    for game in games:
        for side in ('home', 'away'):
            if game.get(f'{side}TeamSlug') == slug or game.get(f'{side}TeamAbbreviation') == team_abbrev:
                name = (game.get(f'{side}GoalieName') or '').strip()
                if name:
                    return {'name': name, 'status': game.get(f'{side}NewsStrengthName') or 'Unconfirmed'}
    return None


def get_dailyfaceoff_starting_goalie(http, team_abbrev, game_date):
    page = http.get_text(f"{DAILYFACEOFF}/starting-goalies/{game_date}")
    return parse_dailyfaceoff_starting_goalie(extract_next_data(page), team_abbrev)


# RotoWire sometimes uses 2-letter codes; try both forms.
_ROTOWIRE_ABBREVS = {'TBL': 'TB', 'LAK': 'LA', 'SJS': 'SJ', 'NJD': 'NJ', 'VGK': 'VGK'}


def parse_rotowire_starting_goalie(page_html, team_abbrev):
    """Find the team's goalie on RotoWire's NHL lineups page (today's games only).

    Returns {'name', 'status': 'Confirmed'|'Expected'} or None.
    RotoWire isn't behind the bot protection that blocks DailyFaceoff from cloud
    servers, so this is the main "reported starter" source on Render.
    """
    if not page_html:
        return None
    codes = {team_abbrev, _ROTOWIRE_ABBREVS.get(team_abbrev, team_abbrev)}
    for box in re.split(r'<div class="lineup__box"', page_html)[1:]:
        abbrevs = re.findall(r'lineup__abbr">\s*([A-Z]{2,4})\s*<', box)
        code = next((c for c in abbrevs if c in codes), None)
        if not code:
            continue
        # Visiting team is listed first; work out which side we are
        team_pos = box.find(f'>{code}<')
        before = box[:team_pos] if team_pos >= 0 else box
        side = 'is-home' if before.rfind('is-home') > before.rfind('is-visit') else 'is-visit'
        if team_pos < 0:
            side = 'is-visit' if abbrevs.index(code) == 0 else 'is-home'
        lineup = re.search(rf'lineup__list {side}">(.*?)(?:lineup__list|</div>\s*</div>\s*</div>)', box, re.DOTALL)
        if not lineup:
            continue
        goalie = re.search(r'lineup__player-highlight-name[^>]*>.*?<a[^>]*>([^<]+)</a>',
                           lineup.group(1), re.DOTALL)
        if goalie:
            name = html_module.unescape(goalie.group(1)).strip()
            status = 'Confirmed' if 'is-confirmed' in lineup.group(1) else 'Expected'
            return {'name': name, 'status': status}
    return None


def get_rotowire_starting_goalie(http, team_abbrev):
    return parse_rotowire_starting_goalie(http.get_text(ROTOWIRE_LINEUPS), team_abbrev)


# ---------------------------------------------------------------------------
# Injuries (ESPN API)
# ---------------------------------------------------------------------------

def parse_espn_injuries(data, team_abbrev):
    """Injuries for one team from ESPN's league injuries JSON.

    ESPN omits teams with no injuries, so a missing team means an empty list.
    """
    target = normalize_name(TEAM_FULL_NAMES.get(team_abbrev, ''))
    for team in (data or {}).get('injuries') or []:
        if normalize_name(team.get('displayName')) != target:
            continue
        result = []
        for item in team.get('injuries') or []:
            name = ((item.get('athlete') or {}).get('displayName') or '').strip()
            if not name:
                continue
            status_text = (item.get('status') or '').lower()
            status = _INJURY_STATUS_MAP.get(status_text) or ((item.get('type') or {}).get('abbreviation') or 'IR')
            details = item.get('details') or {}
            detail = details.get('type') or 'Undisclosed'
            if detail.lower() in ('not specified', 'undisclosed', ''):
                detail = 'Undisclosed'
            result.append({'name': name, 'status': status, 'detail': detail})
        return result
    return []


def get_espn_injuries(http, team_abbrev):
    """Team injuries from ESPN, or None if ESPN couldn't be reached."""
    data = http.get_json(ESPN_INJURIES_API)
    if data is None or 'injuries' not in data:
        return None
    return parse_espn_injuries(data, team_abbrev)


# ---------------------------------------------------------------------------
# Lines derived from NHL shift charts (fallback that can't be bot-blocked)
# ---------------------------------------------------------------------------

def _boxscore_side(boxscore, team_abbrev):
    if (boxscore.get('homeTeam') or {}).get('abbrev') == team_abbrev:
        return 'homeTeam'
    if (boxscore.get('awayTeam') or {}).get('abbrev') == team_abbrev:
        return 'awayTeam'
    return None


def boxscore_roster(boxscore, team_abbrev):
    """{'forwards': {id: pos}, 'defense': {id: pos}, 'goalies': [goalie dicts], 'names': {id: name}}"""
    side = _boxscore_side(boxscore or {}, team_abbrev)
    if not side:
        return None
    stats = (boxscore.get('playerByGameStats') or {}).get(side) or {}
    names = {}
    for group in ('forwards', 'defense', 'goalies'):
        for p in stats.get(group) or []:
            names[p['playerId']] = (p.get('name') or {}).get('default', '')
    return {
        'forwards': {p['playerId']: p.get('position', 'C') for p in stats.get('forwards') or []},
        'defense': {p['playerId']: 'D' for p in stats.get('defense') or []},
        'goalies': stats.get('goalies') or [],
        'names': names,
    }


def _order_line(player_ids, positions, slots):
    """Arrange players into slots (e.g. L/C/R) with as few position mismatches as possible."""
    best = None
    for perm in permutations(player_ids):
        cost = sum(1 for pid, slot in zip(perm, slots) if positions.get(pid) != slot)
        if best is None or cost < best[0]:
            best = (cost, perm)
    return list(best[1]) if best else list(player_ids)


def build_lines_from_shifts(shifts, team_abbrev, forwards, defense, goalie_ids):
    """Reconstruct forward lines and defense pairs from one game's shift chart.

    shifts:     NHL shiftcharts rows (both teams) with teamAbbrev, playerId, period,
                startTime, endTime, typeCode (517 = shift)
    forwards:   {playerId: 'L'|'C'|'R'} for the team's dressed forwards
    defense:    {playerId: 'D'} for the team's dressed defensemen
    goalie_ids: ids of every goalie in the game (both teams), excluded from skater counts

    Players who spent the most 5-on-5 time together are grouped. Lines are ordered
    by total ice time (first line = most used).
    Returns {'forwards': [[ids] x<=4], 'defense': [[ids] x<=3]}.
    """
    on_ice = {}  # period -> list of sets of (team, playerId), one per second
    for row in shifts or []:
        if row.get('typeCode') not in (517, None):
            continue
        start, end = parse_clock(row.get('startTime')), parse_clock(row.get('endTime'))
        if end <= start:
            continue
        timeline = on_ice.setdefault(row.get('period', 1), [])
        if len(timeline) < end:
            timeline.extend(set() for _ in range(end - len(timeline)))
        key = (row.get('teamAbbrev'), row.get('playerId'))
        for second in range(start, end):
            timeline[second].add(key)

    goalie_ids = set(goalie_ids)
    tracked = set(forwards) | set(defense)
    pair_time_5v5, pair_time_all = {}, {}
    toi_5v5, toi_all = {}, {}

    for timeline in on_ice.values():
        for players in timeline:
            mine = [pid for team, pid in players if team == team_abbrev and pid in tracked]
            if not mine:
                continue
            skaters_mine = sum(1 for team, pid in players if team == team_abbrev and pid not in goalie_ids)
            skaters_theirs = sum(1 for team, pid in players if team != team_abbrev and pid not in goalie_ids)
            even = skaters_mine == 5 and skaters_theirs == 5
            for pid in mine:
                toi_all[pid] = toi_all.get(pid, 0) + 1
                if even:
                    toi_5v5[pid] = toi_5v5.get(pid, 0) + 1
            for a, b in combinations(sorted(mine), 2):
                pair_time_all[(a, b)] = pair_time_all.get((a, b), 0) + 1
                if even:
                    pair_time_5v5[(a, b)] = pair_time_5v5.get((a, b), 0) + 1

    # Use 5-on-5 time when there is enough of it, otherwise all situations
    use_even = sum(toi_5v5.values()) > 600
    pair_time = pair_time_5v5 if use_even else pair_time_all
    toi = toi_5v5 if use_even else toi_all

    def together(group):
        return sum(pair_time.get(tuple(sorted(pair)), 0) for pair in combinations(group, 2))

    def greedy_groups(candidates, size, count):
        remaining = [pid for pid in candidates if toi.get(pid, 0) > 0]
        groups = []
        while len(groups) < count and len(remaining) >= size:
            best = max(combinations(remaining, size),
                       key=lambda g: (together(g), sum(toi.get(pid, 0) for pid in g)))
            groups.append(list(best))
            remaining = [pid for pid in remaining if pid not in best]
        if len(groups) < count and remaining:
            groups.append(remaining[:size])
        # Order by total ice time in all situations, the best proxy for the coach's depth chart
        groups.sort(key=lambda g: sum(toi_all.get(pid, 0) for pid in g), reverse=True)
        return groups

    forward_lines = [_order_line(g, forwards, ['L', 'C', 'R']) for g in greedy_groups(list(forwards), 3, 4)]
    defense_pairs = greedy_groups(list(defense), 2, 3)
    return {'forwards': forward_lines, 'defense': defense_pairs}


def derive_lines_from_last_game(http, team_abbrev, schedule, club_stats, before_date=None):
    """Line combinations from the team's most recent completed game (NHL API only)."""
    recent = completed_games_before(schedule, before_date)
    if not recent:
        return None
    game = recent[0]
    boxscore = http.get_json(f"{NHL_API}/gamecenter/{game['id']}/boxscore")
    shifts = (http.get_json(f"{NHL_STATS_API}/shiftcharts?cayenneExp=gameId={game['id']}") or {}).get('data')
    roster = boxscore_roster(boxscore, team_abbrev) if boxscore else None
    if not roster or not shifts:
        return None

    other_side = 'awayTeam' if _boxscore_side(boxscore, team_abbrev) == 'homeTeam' else 'homeTeam'
    other_goalies = ((boxscore.get('playerByGameStats') or {}).get(other_side) or {}).get('goalies') or []
    goalie_ids = [g['playerId'] for g in roster['goalies'] + other_goalies]

    lines = build_lines_from_shifts(shifts, team_abbrev, roster['forwards'], roster['defense'], goalie_ids)

    full_names = {p.get('playerId'): player_full_name(p) for p in (club_stats or {}).get('skaters') or []}

    def name(pid):
        return full_names.get(pid) or roster['names'].get(pid) or str(pid)

    return {
        'forwards': [[name(pid) for pid in line] for line in lines['forwards']],
        'defense': [[name(pid) for pid in pair] for pair in lines['defense']],
        'goalies': [],
        'injuries': [],
        'source_game': game.get('gameDate'),
    }


# ---------------------------------------------------------------------------
# Starting goalie projection
# ---------------------------------------------------------------------------

def project_starting_goalie(team_abbrev, recent_boxscores, game_date=None, injured_names=(), club_stats=None):
    """Rule-based guess at the starting goalie when no confirmation exists.

    recent_boxscores: the team's most recent completed games' box scores, newest first.
    Rules, in order:
      1. Only goalies who dressed for the most recent game are candidates (that is the
         current tandem; it naturally excludes injured or demoted goalies). Anyone on
         the injury list is removed.
      2. Second night of a back-to-back: the goalie who did NOT start last night.
      3. Otherwise: whoever started the most of the recent games.
      4. Ties: more season starts, then whoever started the most recent game.
    Returns {'name', 'player_id', 'status': 'Projected', 'reason'} or None.
    """
    injured = {normalize_name(n) for n in injured_names}
    full_names = {g.get('playerId'): player_full_name(g) for g in (club_stats or {}).get('goalies') or []}
    season_starts = {g.get('playerId'): g.get('gamesStarted', 0) for g in (club_stats or {}).get('goalies') or []}

    def display_name(goalie):
        return full_names.get(goalie['playerId']) or (goalie.get('name') or {}).get('default', '')

    games = []  # (gameDate, starter_id, [goalies dressed])
    for box in recent_boxscores or []:
        roster = boxscore_roster(box, team_abbrev)
        if not roster or not roster['goalies']:
            continue
        starter = next((g['playerId'] for g in roster['goalies'] if g.get('starter')), None)
        games.append((box.get('gameDate'), starter, roster['goalies']))

    if games:
        tandem = [g for g in games[0][2] if normalize_name(display_name(g)) not in injured]
    else:
        tandem = []
    if not tandem:
        # No box scores: fall back to the team's season stats
        tandem = [{'playerId': g.get('playerId'), 'name': {'default': player_full_name(g)}}
                  for g in sorted((club_stats or {}).get('goalies') or [],
                                  key=lambda g: g.get('gamesStarted', 0), reverse=True)
                  if normalize_name(player_full_name(g)) not in injured][:2]
    if not tandem:
        return None

    by_id = {g['playerId']: g for g in tandem}

    def result(player_id, reason):
        return {'name': display_name(by_id[player_id]), 'player_id': player_id,
                'status': 'Projected', 'reason': reason}

    # Rule 2: back-to-back
    if games and game_date and len(tandem) > 1:
        last_date, last_starter, _ = games[0]
        try:
            gap = (date.fromisoformat(game_date) - date.fromisoformat(last_date)).days
        except (TypeError, ValueError):
            gap = None
        if gap == 1 and last_starter in by_id:
            other = next(pid for pid in by_id if pid != last_starter)
            return result(other, f"second game of a back-to-back; "
                                 f"{display_name(by_id[last_starter])} started last night")

    # Rules 3-4: recent workload
    window = games[:GOALIE_LOOKBACK_GAMES]
    recent_starts = {pid: sum(1 for _, starter, _ in window if starter == pid) for pid in by_id}
    last_starter = games[0][1] if games else None
    best = max(by_id, key=lambda pid: (recent_starts[pid], season_starts.get(pid, 0), pid == last_starter))
    if window:
        reason = f"started {recent_starts[best]} of the last {len(window)} games"
    else:
        reason = "most starts this season"
    return result(best, reason)


def choose_starting_goalie(http, team_abbrev, game_info, schedule, club_stats, injuries, lineup, notes=None):
    """Pick the starting goalie.

    DailyFaceoff Confirmed/Likely > RotoWire (today's games) > rule-based projection >
    DailyFaceoff's unconfirmed pick.
    """
    team_name = TEAM_FULL_NAMES.get(team_abbrev, team_abbrev)
    game_date = (game_info or {}).get('eastern_date') or datetime.now().strftime("%Y-%m-%d")

    dfo = get_dailyfaceoff_starting_goalie(http, team_abbrev, game_date)
    if dfo and dfo['status'] in ('Confirmed', 'Likely', 'Expected'):
        log.info("  Starting goalie (DailyFaceoff, %s): %s", dfo['status'], dfo['name'])
        return dfo

    # RotoWire's lineups page only covers today's games
    if game_date == eastern_today():
        rw = get_rotowire_starting_goalie(http, team_abbrev)
        if rw:
            log.info("  Starting goalie (RotoWire, %s): %s", rw['status'], rw['name'])
            if rw['status'] != 'Confirmed':
                add_note(notes, f"{team_name} starting goalie {rw['name']} is expected per RotoWire "
                                f"but not confirmed yet")
            return rw

    recent = completed_games_before(schedule, game_date)[:GOALIE_LOOKBACK_GAMES]
    boxscores = [b for b in (http.get_json(f"{NHL_API}/gamecenter/{g['id']}/boxscore") for g in recent) if b]
    injured_names = [i['name'] for i in injuries or []]
    projected = project_starting_goalie(team_abbrev, boxscores, game_date, injured_names, club_stats)
    if projected:
        message = f"{team_name} starting goalie not confirmed yet; projected {projected['name']} ({projected['reason']})"
        if dfo and normalize_name(dfo['name']) != normalize_name(projected['name']):
            message += f". DailyFaceoff currently lists {dfo['name']} (unconfirmed)"
        add_note(notes, message)
        return projected

    if dfo:
        add_note(notes, f"{team_name} starting goalie not confirmed; using DailyFaceoff's unconfirmed pick {dfo['name']}")
        return dfo
    if lineup and lineup.get('goalies'):
        add_note(notes, f"{team_name} starting goalie not confirmed; using DailyFaceoff depth chart ({lineup['goalies'][0]})")
        return {'name': lineup['goalies'][0], 'status': 'Projected'}
    return None


# ---------------------------------------------------------------------------
# Gathering everything for a team
# ---------------------------------------------------------------------------

def _lineup_complete(lineup):
    return (lineup and len([l for l in lineup['forwards'] if len(l) == 3]) == 4
            and len([p for p in lineup['defense'] if len(p) == 2]) == 3)


def get_line_combinations(http, team_abbrev, schedule, club_stats, game_date=None, notes=None):
    """Lines from DailyFaceoff, falling back to lines derived from the last game's shifts."""
    team_name = TEAM_FULL_NAMES.get(team_abbrev, team_abbrev)
    lineup = get_dailyfaceoff_lineup(http, team_abbrev)
    if _lineup_complete(lineup):
        log.info("  Lines: DailyFaceoff (updated %s)", lineup.get('updated_at') or 'unknown')
        return lineup, 'DailyFaceoff'

    derived = derive_lines_from_last_game(http, team_abbrev, schedule, club_stats, game_date)
    if derived and any(derived['forwards']):
        reason = "DailyFaceoff was unavailable" if not lineup else "DailyFaceoff's lines were incomplete"
        add_note(notes, f"{team_name} lines are from their last game ({derived['source_game']}) "
                        f"because {reason}; double-check before posting")
        if lineup:  # keep DailyFaceoff's goalies/injuries even if its lines were partial
            derived['goalies'] = lineup.get('goalies', [])
            derived['injuries'] = lineup.get('injuries', [])
        return derived, 'last game'

    if lineup:
        add_note(notes, f"{team_name} lines from DailyFaceoff are incomplete")
        return lineup, 'DailyFaceoff (partial)'
    add_note(notes, f"Could not get line combinations for {team_name}; lineup left unchanged")
    return None, None


def gather_team_data(http, team_abbrev, standings, game_info=None, notes=None):
    """Fetch everything needed for one team's section of the GDT."""
    log.info("Fetching data for %s...", team_abbrev)
    game_type = (game_info or {}).get('game_type', 2)
    game_date = (game_info or {}).get('eastern_date')

    standing = find_team_standing(standings, team_abbrev)
    stats = get_team_stats(http, team_abbrev, standings, game_type) if standing else None
    club_stats = get_club_stats(http, team_abbrev)
    leaders = get_team_leaders(club_stats, (standing or {}).get('gamesPlayed', 0))
    schedule = get_season_schedule(http, team_abbrev)

    lineup, lines_source = get_line_combinations(http, team_abbrev, schedule, club_stats, game_date, notes)

    injuries = get_espn_injuries(http, team_abbrev)
    if injuries is None:
        injuries = (lineup or {}).get('injuries')
        if injuries is not None:
            log.info("  Injuries: DailyFaceoff (ESPN unavailable)")
        else:
            add_note(notes, f"Could not get injuries for {TEAM_FULL_NAMES.get(team_abbrev, team_abbrev)}")
    else:
        log.info("  Injuries: ESPN (%d listed)", len(injuries))

    # Don't list injured players in lines rebuilt from an earlier game
    if lineup and injuries and lines_source == 'last game':
        hurt = {normalize_name(i['name']) for i in injuries}
        lineup['forwards'] = [[n for n in line if normalize_name(n) not in hurt] for line in lineup['forwards']]
        lineup['defense'] = [[n for n in pair if normalize_name(n) not in hurt] for pair in lineup['defense']]

    starter = choose_starting_goalie(http, team_abbrev, game_info, schedule, club_stats, injuries, lineup, notes)
    goalie = get_goalie_stats(club_stats, (starter or {}).get('name'), (starter or {}).get('player_id'))
    if goalie and starter:
        goalie['status'] = starter.get('status')

    return {
        'abbrev': team_abbrev,
        'standing': standing,
        'stats': stats,
        'leaders': leaders,
        'lineup': lineup,
        'goalie': goalie,
        'injuries': injuries,
    }


# ---------------------------------------------------------------------------
# Template updating
# ---------------------------------------------------------------------------

def _sub_once(pattern, replacement_fn, text, flags=re.IGNORECASE | re.DOTALL):
    """re.sub with a function replacement (so data can never be read as a backreference)."""
    return re.sub(pattern, replacement_fn, text, count=1, flags=flags)


def set_gdt_field(section, tag_pattern, value):
    """Replace the contents of <p data-gdt="***UPDATE ...***"> whose tag matches tag_pattern."""
    pattern = r'(<p\s+data-gdt="\*\*\*UPDATE\s+' + tag_pattern + r'\*\*\*"\s*>).*?(</p>)'
    return _sub_once(pattern, lambda m: f"{m.group(1)}\n\t\t\t\t{value}\n\t\t\t{m.group(2)}", section)


def esc(text):
    return html_module.escape(str(text), quote=False)


def update_team_logos(content, nyr_abbrev, opponent_abbrev):
    """Update team logos throughout the template (order: NYR, opponent, NYR, opponent)."""
    nyr_logo_url = TEAM_LOGO_URLS.get(nyr_abbrev)
    opponent_logo_url = TEAM_LOGO_URLS.get(opponent_abbrev)
    if not nyr_logo_url or not opponent_logo_url:
        log.warning("Could not find logo URLs for %s or %s", nyr_abbrev, opponent_abbrev)
        return content

    logo_pattern = r'(data-src=")[^"]*(?:invisioncic\.com|blueshirtsbrotherhood\.com)[^"]*\.png[^"]*(")'
    matches = list(re.finditer(logo_pattern, content, re.IGNORECASE))
    if len(matches) < 4:
        log.warning("Found only %d logo images, expected 4", len(matches))

    for i, match in reversed(list(enumerate(matches[:4]))):
        url = nyr_logo_url if i % 2 == 0 else opponent_logo_url
        content = content[:match.start()] + f'{match.group(1)}{url}{match.group(2)}' + content[match.end():]

    log.info("Updated logos: %s and %s", nyr_abbrev, opponent_abbrev)
    return content


def update_game_header(content, game_info, nyr_game_number):
    """Update the game header section with game info."""
    if not game_info:
        return content

    if nyr_game_number and game_info.get('date'):
        content = _sub_once(r'(REGULAR SEASON GAME #)\d+(\s*&mdash;\s*)\d+/\d+/\d+',
                            lambda m: f"{m.group(1)}{nyr_game_number}{m.group(2)}{game_info['date']}", content)

    if game_info.get('time'):
        content = _sub_once(r'(<b>Time</b>:\s*)(?:\d+:\d+\s*[AP]M|TBD)',
                            lambda m: f"{m.group(1)}{game_info['time']}", content)

    if game_info.get('tv_broadcasts'):
        tv_str = esc(', '.join(game_info['tv_broadcasts']))
        content = _sub_once(r'(<b>TV</b><span>:</span>&nbsp;)[^<]+', lambda m: f"{m.group(1)}{tv_str}", content)

    content = _sub_once(r'(<b>&nbsp;Radio</b>:\s*)[^<]+', lambda m: f"{m.group(1)}{NYR_RADIO_STATIONS}", content)

    if game_info.get('gamecenter_url'):
        content = _sub_once(r'(href=")[^"]*nhl\.com/gamecenter[^"]*(")',
                            lambda m: f"{m.group(1)}{game_info['gamecenter_url']}{m.group(2)}", content)
    return content


def find_team_section(content, is_first_team):
    """(start, end) of a team's section, based on the <hr> separators.

    3+ HRs: HR1-HR2 is the first team, HR2-HR3 the second team.
    2 HRs:  both teams share HR1-HR2.
    """
    hr_matches = list(re.finditer(r'<hr\s+style="width:\d+%">', content))
    if len(hr_matches) >= 3:
        if is_first_team:
            return hr_matches[0].start(), hr_matches[1].start()
        return hr_matches[1].start(), hr_matches[2].start()
    if len(hr_matches) == 2:
        return hr_matches[0].start(), hr_matches[1].start()
    log.warning("Template has fewer than 2 <hr> separators; updating the whole document")
    return 0, len(content)


def _is_blank_paragraph(inner):
    return not re.sub(r'(&nbsp;|<br\s*/?>|\s)', '', inner, flags=re.IGNORECASE)


def render_lineup(section, lineup, is_first_team=True):
    """Fill the forwards and defense paragraphs under the "Starting Lineup" header.

    Uses the first two non-blank <p> blocks between the header and "Starting
    Goaltender", so it works for both team sections and tolerates spacing,
    spacer paragraphs and minor template edits. (is_first_team kept for
    backwards compatibility; both sections are handled the same way.)
    """
    forward_lines = [" / ".join(esc(n) for n in line) for line in lineup.get('forwards', []) if line]
    defense_pairs = [" / ".join(esc(n) for n in pair) for pair in lineup.get('defense', []) if pair]

    header = re.search(r'<b>\s*Starting Lineup:?\s*\^?\s*</b>\s*</h3>', section, re.IGNORECASE)
    if not header:
        log.warning("  'Starting Lineup' header not found in template section; lines not written")
        return section
    stop = re.search(r'Starting Goaltender|<hr\b', section[header.end():], re.IGNORECASE)
    region_end = header.end() + stop.start() if stop else len(section)
    region = section[header.end():region_end]

    paragraphs = [m for m in re.finditer(r'<p>(.*?)</p>', region, re.IGNORECASE | re.DOTALL)
                  if not _is_blank_paragraph(m.group(1))]
    edits = []
    if forward_lines and paragraphs:
        edits.append((paragraphs[0], "\n\t\t" + "<br>\n\t\t".join(forward_lines) + "\n\t"))
    if defense_pairs and len(paragraphs) > 1:
        # Keep a leading <br> spacer if the template uses one (opponent section does)
        lead = "\n\t\t<br>" if re.match(r'\s*<br\s*/?>', paragraphs[1].group(1), re.IGNORECASE) else ""
        edits.append((paragraphs[1], lead + "\n\t\t" + "<br>\n\t\t".join(defense_pairs) + "\n\t"))
    elif defense_pairs:
        log.warning("  Template has no defense paragraph under 'Starting Lineup'; pairs not written")

    for match, inner in reversed(edits):
        region = region[:match.start(1)] + inner + region[match.end(1):]
    log.info("  Line combinations updated (%d forward lines, %d defense pairs)",
             len(forward_lines) if edits else 0, len(defense_pairs) if len(edits) > 1 else 0)
    return section[:header.end()] + region + section[region_end:]


def update_team_section(content, team, is_first_team=True):
    """Write one team's gathered data into its section of the template."""
    section_start, section_end = find_team_section(content, is_first_team)
    section = content[section_start:section_end]

    s = team.get('standing')
    team_tag = r'(?:[A-Z]{2,3}\s+)?'  # e.g. "NYR " in ***UPDATE NYR RECORD***
    fields = []
    if not s:
        log.error("No standings data for %s; standings fields left unchanged", team['abbrev'])
    else:
        fields += [
            (team_tag + r'RECORD', f"{s.get('wins', 0)}-{s.get('losses', 0)}-{s.get('otLosses', 0)} "
                                   f"(<b>{s.get('points', 0)} Points</b>)"),
            (r'POSITION', f"{ordinal(s.get('divisionSequence', 0))} &mdash; "
                          f"{esc(s.get('divisionName', 'Division'))}"),
            (r'ROW', s.get('regulationPlusOtWins', 0)),
            (r'P%', format_three_decimals(s.get('pointPctg', 0))),
            (r'RECORD\s+HOME', f"{s.get('homeWins', 0)}-{s.get('homeLosses', 0)}-{s.get('homeOtLosses', 0)}"),
            (r'RECORD\s+AWAY', f"{s.get('roadWins', 0)}-{s.get('roadLosses', 0)}-{s.get('roadOtLosses', 0)}"),
            (r'S/O', f"{s.get('shootoutWins', 0)}-{s.get('shootoutLosses', 0)}"),
            (r'LAST\s+10', f"{s.get('l10Wins', 0)}-{s.get('l10Losses', 0)}-{s.get('l10OtLosses', 0)}"),
            (r'STREAK', format_streak(s.get('streakCode', '-'), s.get('streakCount', 0))),
        ]

    stats = team.get('stats')
    if stats:
        def rank(r):
            return f" ({ordinal(r)})" if r else ""
        diff_str = f"+{stats['diff']}" if stats['diff'] > 0 else str(stats['diff'])
        fields += [
            (team_tag + r'DIFF', f"{diff_str}{rank(stats['diff_rank'])}"),
            (r'GF/GP', f"{stats['gf_per_game']:.2f}{rank(stats['gf_rank'])}"),
            (r'GA/GP', f"{stats['ga_per_game']:.2f}{rank(stats['ga_rank'])}"),
            (r'PP%', f"{stats['pp_pct']}%{rank(stats['pp_rank'])}"),
            (r'PK%', f"{stats['pk_pct']}%{rank(stats['pk_rank'])}"),
        ]

    leaders = team.get('leaders') or {}
    for tag, key in [(team_tag + r'GOALS', 'goals'), (r'ASSISTS', 'assists'), (r'POINTS', 'points'),
                     (r'\+/-', 'plusMinus'), (r'PIM', 'pim'), (r'TOI/G\s*\(D\)', 'toi_d'),
                     (r'TOI/G\s*\(F\)', 'toi_f')]:
        if key in leaders:
            fields.append((tag, f"{esc(leaders[key]['name'])} ({leaders[key]['value']})"))

    goalie = team.get('goalie')
    if goalie:
        fields += [
            (r'GS', goalie['games_started']),
            (r'REC', goalie['record']),
            (r'SV%', goalie['sv_pct']),
            (r'GAA', goalie['gaa']),
            (r'SO', goalie['shutouts']),
        ]

    for tag, value in fields:
        section = set_gdt_field(section, tag, value)

    lineup = team.get('lineup')
    if lineup:
        section = render_lineup(section, lineup, is_first_team)

    if goalie:
        section = _sub_once(r'(<b>\s*Starting Goaltender:?\s*</b>\s*</h3>\s*<p>).*?(<br\s*/?>|&nbsp;|</p>)',
                            lambda m: f"{m.group(1)}\n\t\t{esc(goalie['name'])}{m.group(2)}", section)

    injuries = team.get('injuries')
    if injuries is not None:
        if injuries:
            injuries_html = "<br>\n\t\t".join(
                f"{esc(i['name'])} <span class=\"gdtAlert\">[{esc(i['status'])}]</span> &mdash; {esc(i['detail'])}"
                for i in injuries)
        else:
            injuries_html = "None"
        section = _sub_once(r'(<b>\s*Injuries,\s*Suspensions,\s*(?:&amp;|&)\s*Scratches:?\s*</b>\s*</h3>\s*<p>)'
                            r'.*?(</p>)',
                            lambda m: f"{m.group(1)}\n\t\t{injuries_html}\n\t{m.group(2)}", section)

    return content[:section_start] + section + content[section_end:]


def update_template(template_content, opponent_abbrev, notes=None, http=None):
    """Update the template with data for both teams.

    notes: optional list that receives human-readable warnings (unconfirmed goalie,
           fallback lines, unreachable sources) for display in the web UI.
    """
    http = http or HttpClient()
    log.info("=" * 50)
    log.info("  Updating Game Day Thread: %s vs %s", NYR, opponent_abbrev)
    log.info("=" * 50)

    template_content = update_team_logos(template_content, NYR, opponent_abbrev)

    nyr_schedule = get_season_schedule(http, NYR)
    game_data = find_next_game(nyr_schedule, opponent_abbrev)
    game_info = get_game_info(game_data, NYR) if game_data else None
    if game_info:
        log.info("Found game: %s @ %s on %s at %s (TV: %s)", game_info['away_team'], game_info['home_team'],
                 game_info['date'], game_info['time'], ', '.join(game_info['tv_broadcasts']) or 'TBD')
        template_content = update_game_header(template_content, game_info, get_game_number(nyr_schedule, game_data))
    else:
        add_note(notes, f"No upcoming {NYR} vs {opponent_abbrev} game found; game header left unchanged")

    standings = get_standings(http)
    if not standings:
        add_note(notes, "Could not load NHL standings; team stats were not updated")

    for abbrev, first in ((NYR, True), (opponent_abbrev, False)):
        log.info("-" * 40)
        team = gather_team_data(http, abbrev, standings, game_info, notes)
        template_content = update_team_section(template_content, team, is_first_team=first)

    if http.blocked_hosts:
        add_note(notes, "Blocked by bot protection: " + ", ".join(sorted(http.blocked_hosts))
                 + " (fallback sources were used)")
    return template_content


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------

def interactive_mode():
    """Run in interactive mode - prompts user for input."""
    print("=" * 50)
    print("  NHL Game Day Thread (GDT) Updater")
    print("  Rangers vs. Opponent")
    print("=" * 50)
    print()
    print("The Rangers are automatically set as the first team.")
    print("Enter the opponent team name (e.g. Sabres, BUF, Buffalo Sabres).")
    print()

    while True:
        team_input = input("Enter opponent team: ").strip()
        opponent_abbrev = get_team_abbrev(team_input)
        if not team_input:
            print("Please enter a team name.")
        elif not opponent_abbrev:
            print(f"Could not recognize '{team_input}'. Examples: Sabres, BUF, Buffalo Sabres")
        elif opponent_abbrev == NYR:
            print("The Rangers can't play themselves! Enter a different opponent.")
        else:
            print(f"Opponent identified: {opponent_abbrev} ({TEAM_FULL_NAMES.get(opponent_abbrev, '')})")
            break

    print()
    print("Enter the path to your template file.")
    print("(You can drag and drop the file into this window)")
    print()

    while True:
        file_path = input("Template file path: ").strip().strip('"').strip("'")
        if not file_path:
            print("Please enter a file path.")
        elif os.path.exists(file_path):
            break
        else:
            print(f"File not found: {file_path}")

    print()
    return opponent_abbrev, file_path


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    launched_interactively = len(sys.argv) <= 1  # e.g. double-clicked the .exe

    def fail(message):
        log.error("Error: %s", message)
        if launched_interactively:
            input("\nPress Enter to exit...")
        sys.exit(1)

    if launched_interactively:
        opponent_abbrev, file_path = interactive_mode()
        output_path = file_path
    else:
        parser = argparse.ArgumentParser(
            description='Update NHL Game Day Thread template with data for Rangers vs Opponent')
        parser.add_argument('opponent', nargs='?', help='Opponent team name (e.g., "Sabres", "BUF")')
        parser.add_argument('--file', '-f', help='Path to the template file')
        parser.add_argument('--output', '-o', help='Output file path (defaults to overwriting input)')
        parser.add_argument('--interactive', '-i', action='store_true', help='Run in interactive mode')
        parser.add_argument('--verbose', '-v', action='store_true', help='Show debug output')
        args = parser.parse_args()
        if args.verbose:
            logging.getLogger().setLevel(logging.DEBUG)

        if args.interactive or not args.opponent:
            opponent_abbrev, file_path = interactive_mode()
            output_path = file_path
        else:
            opponent_abbrev = get_team_abbrev(args.opponent)
            if not opponent_abbrev:
                fail(f"Could not recognize team '{args.opponent}'. Try e.g. 'Sabres' or 'BUF'.")
            if opponent_abbrev == NYR:
                fail("Rangers can't play themselves! Enter a different opponent.")
            if not args.file:
                fail("Please specify a template file with --file")
            log.info("Opponent identified: %s (%s)", opponent_abbrev, TEAM_FULL_NAMES.get(opponent_abbrev, ''))
            file_path = args.file
            output_path = args.output or args.file

    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            template = f.read()
    except OSError as e:
        fail(f"Could not read template {file_path}: {e}")

    notes = []
    updated = update_template(template, opponent_abbrev, notes)

    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(updated)
    except OSError as e:
        fail(f"Could not write output {output_path}: {e}")

    log.info("")
    log.info("Successfully updated: %s", output_path)
    if notes:
        log.info("")
        log.info("Things to double-check:")
        for note in notes:
            log.info("  - %s", note)

    if launched_interactively:
        print()
        input("Press Enter to exit...")


if __name__ == '__main__':
    main()
