"""Offline tests for nhl_gdt_updater. Run with:  python -m unittest discover tests

No network access is needed: HTTP calls go to FakeHttp, which serves fixtures.
The shift chart and box score fixtures are real NHL API data (CAR @ NYR, 2026-11-22).
"""

import json
import logging
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import nhl_gdt_updater as gdt  # noqa: E402

FIXTURES = os.path.join(ROOT, "tests", "fixtures")
logging.disable(logging.CRITICAL)


def load_shifts():
    """Expand the compact shift fixture into NHL shiftcharts rows."""
    rows = []
    with open(os.path.join(FIXTURES, "shifts_2026020373.compact")) as f:
        for item in f.read().strip().split(";"):
            team, pid, period, start, end = item.split(",")
            rows.append({"teamAbbrev": "NYR" if team == "1" else "CAR", "playerId": 8400000 + int(pid),
                         "period": int(period), "startTime": start, "endTime": end, "typeCode": 517})
    return rows


def load_boxscore():
    with open(os.path.join(FIXTURES, "boxscore_2026020373.json")) as f:
        return json.load(f)


def make_boxscore(game_id, game_date, home, away, goalies_by_team):
    """Minimal box score: goalies_by_team = {abbrev: [(id, 'F. Last', starter), ...]}"""
    def side(abbrev):
        return {"forwards": [], "defense": [],
                "goalies": [{"playerId": pid, "name": {"default": name}, "position": "G", "starter": st}
                            for pid, name, st in goalies_by_team.get(abbrev, [])]}
    return {"id": game_id, "gameDate": game_date, "homeTeam": {"abbrev": home}, "awayTeam": {"abbrev": away},
            "playerByGameStats": {"homeTeam": side(home), "awayTeam": side(away)}}


def next_data_page(page_props):
    return ('<html><head><title>x</title></head><body><script id="__NEXT_DATA__" type="application/json">'
            + json.dumps({"props": {"pageProps": page_props}}) + "</script></body></html>")


def player(pid, first, last, **kw):
    return dict({"playerId": pid, "firstName": {"default": first}, "lastName": {"default": last}}, **kw)


GARAND, KORPISALO, SHESTERKIN = 8482193, 8476914, 8478048
UPL, LEVI = 9000001, 9000002


def schedule_game(game_id, game_date, away, home, state, start_utc=None, broadcasts=None, game_type=2):
    return {"id": game_id, "gameDate": game_date, "gameType": game_type, "gameState": state,
            "startTimeUTC": start_utc or f"{game_date}T23:00:00Z", "easternUTCOffset": "-05:00",
            "awayTeam": {"abbrev": away}, "homeTeam": {"abbrev": home},
            "tvBroadcasts": broadcasts or [],
            "gameCenterLink": f"/gamecenter/{away.lower()}-vs-{home.lower()}/{game_date.replace('-', '/')}/{game_id}"}


NYR_SCHEDULE = {"games": [
    schedule_game(2026010001, "2026-09-25", "NYR", "NJD", "OFF", game_type=1),
    schedule_game(2026020370, "2026-11-20", "PHI", "NYR", "OFF"),
    schedule_game(2026020373, "2026-11-22", "CAR", "NYR", "OFF"),
    schedule_game(2026020387, "2026-11-25", "NYR", "BUF", "FUT", start_utc="2026-11-26T00:00:00Z", broadcasts=[
        {"countryCode": "US", "market": "A", "network": "MSG 2"},
        {"countryCode": "US", "market": "H", "network": "MSG-B"},
        {"countryCode": "CA", "market": "N", "network": "SN"}]),
    schedule_game(2026020500, "2027-01-10", "BUF", "NYR", "FUT"),
]}

BUF_SCHEDULE = {"games": [
    schedule_game(2026020376, "2026-11-22", "BUF", "TOR", "OFF"),
    schedule_game(2026020380, "2026-11-24", "BOS", "BUF", "OFF"),
    schedule_game(2026020387, "2026-11-25", "NYR", "BUF", "FUT", start_utc="2026-11-26T00:00:00Z"),
]}


def standing(abbrev, **kw):
    base = {"teamAbbrev": {"default": abbrev}, "seasonId": 20262027, "gamesPlayed": 23, "wins": 12, "losses": 9,
            "otLosses": 2, "points": 26, "goalFor": 70, "goalAgainst": 60, "goalDifferential": 10,
            "divisionSequence": 3, "divisionName": "Metropolitan", "regulationPlusOtWins": 11, "pointPctg": 0.565217,
            "homeWins": 7, "homeLosses": 4, "homeOtLosses": 1, "roadWins": 5, "roadLosses": 5, "roadOtLosses": 1,
            "shootoutWins": 1, "shootoutLosses": 0, "l10Wins": 6, "l10Losses": 3, "l10OtLosses": 1,
            "streakCode": "L", "streakCount": 1}
    base.update(kw)
    return base


NYR_CLUB_STATS = {
    "skaters": [
        player(8476459, "Mika", "Zibanejad", positionCode="C", gamesPlayed=23, goals=6, assists=14, points=20,
               plusMinus=3, penaltyMinutes=4, avgTimeOnIcePerGame=1100),
        player(8476468, "J.T.", "Miller", positionCode="C", gamesPlayed=23, goals=11, assists=10, points=21,
               plusMinus=-2, penaltyMinutes=20, avgTimeOnIcePerGame=1250),
        player(8479323, "Adam", "Fox", positionCode="D", gamesPlayed=23, goals=2, assists=15, points=17,
               plusMinus=5, penaltyMinutes=6, avgTimeOnIcePerGame=1400),
        player(8400001, "Call", "Up", positionCode="D", gamesPlayed=1, goals=0, assists=0, points=0,
               plusMinus=0, penaltyMinutes=0, avgTimeOnIcePerGame=1700),
    ],
    "goalies": [
        player(GARAND, "Dylan", "Garand", gamesStarted=14, gamesPlayed=16, wins=7, losses=8, overtimeLosses=1,
               savePercentage=0.909091, goalsAgainstAverage=2.491397, shutouts=1),
        player(KORPISALO, "Joonas", "Korpisalo", gamesStarted=3, gamesPlayed=3, wins=3, losses=0, overtimeLosses=0,
               savePercentage=0.939759, goalsAgainstAverage=1.673796, shutouts=0),
        player(SHESTERKIN, "Igor", "Shesterkin", gamesStarted=5, gamesPlayed=5, wins=3, losses=1, overtimeLosses=0,
               savePercentage=0.926606, goalsAgainstAverage=1.793164, shutouts=0),
    ],
}

BUF_CLUB_STATS = {
    "skaters": [player(1, "Tage", "Thompson", positionCode="C", gamesPlayed=22, goals=12, assists=9, points=21,
                       plusMinus=1, penaltyMinutes=8, avgTimeOnIcePerGame=1150)],
    "goalies": [
        player(UPL, "Ukko-Pekka", "Luukkonen", gamesStarted=15, gamesPlayed=15, wins=8, losses=6, overtimeLosses=1,
               savePercentage=0.905, goalsAgainstAverage=2.8, shutouts=1),
        player(LEVI, "Devon", "Levi", gamesStarted=7, gamesPlayed=8, wins=3, losses=3, overtimeLosses=1,
               savePercentage=0.899, goalsAgainstAverage=3.1, shutouts=0),
    ],
}

DFO_NYR_LINES = {"combinations": {"updatedAt": "2026-11-22T17:08:25Z", "players": [
    {"categoryIdentifier": "ev", "groupIdentifier": f"f{line}", "positionIdentifier": pos, "name": name}
    for line, trio in enumerate([("Gabriel Perreault", "Mika Zibanejad", "Alexis Lafrenière"),
                                 ("Will Cuylle", "J.T. Miller", "Tye Kartye"),
                                 ("Eeli Tolvanen", "Noah Laba", "Jaroslav Chmelar"),
                                 ("Glenn Gawdin", "Max Sasson", "Matt Rempe")], start=1)
    for pos, name in zip(("rw", "c", "lw"), reversed(trio))  # deliberately out of order
] + [
    {"categoryIdentifier": "ev", "groupIdentifier": f"d{pair}", "positionIdentifier": pos, "name": name}
    for pair, duo in enumerate([("Vladislav Gavrikov", "Adam Fox"), ("Marcus Pettersson", "Sean Durzi"),
                                ("Braden Schneider", "Scott Morrow")], start=1)
    for pos, name in zip(("ld", "rd"), duo)
] + [
    {"categoryIdentifier": "ev", "groupIdentifier": "g", "positionIdentifier": "g1", "name": "Dylan Garand"},
    {"categoryIdentifier": "ev", "groupIdentifier": "g", "positionIdentifier": "g2", "name": "Joonas Korpisalo"},
    {"categoryIdentifier": "pp", "groupIdentifier": "pp1", "positionIdentifier": "sk1", "name": "Adam Fox"},
    {"categoryIdentifier": "oi", "groupIdentifier": "ir", "positionIdentifier": "ir1", "name": "Igor Shesterkin",
     "injuryStatus": "ir"},
]}}

ESPN_INJURIES = {"injuries": [
    {"displayName": "New York Rangers", "injuries": [
        {"athlete": {"displayName": "Igor Shesterkin"}, "status": "Injured Reserve",
         "type": {"abbreviation": "IR"}, "details": {"type": "Knee"}},
        {"athlete": {"displayName": "Oliver Bjorkstrand"}, "status": "Injured Reserve",
         "type": {"abbreviation": "IR"}, "details": {"type": "Upper Body"}},
        {"athlete": {"displayName": "Joe Veleno"}, "status": "Day-To-Day",
         "type": {"abbreviation": "DTD"}, "details": {"type": "Not Specified"}},
    ]},
    # Buffalo deliberately absent: ESPN omits teams with no injuries
]}


class FakeHttp:
    """Serves fixtures by URL. `blocked` hosts behave like a bot wall (return None)."""

    def __init__(self, blocked=()):
        self.blocked_hosts = set()
        self._blocked = set(blocked)
        self.requested = []
        nyr_last = load_boxscore()
        self.routes = {
            f"{gdt.NHL_API}/club-schedule-season/NYR/now": NYR_SCHEDULE,
            f"{gdt.NHL_API}/club-schedule-season/BUF/now": BUF_SCHEDULE,
            f"{gdt.NHL_API}/standings/now": {"standings": [
                standing("NYR"),
                standing("BUF", wins=10, losses=10, otLosses=3, points=23, goalDifferential=-4,
                         divisionName="Atlantic", divisionSequence=6, streakCode="W", streakCount=2),
                standing("MTL", goalDifferential=20, goalFor=90),
            ]},
            (f"{gdt.NHL_STATS_API}/team/summary?cayenneExp=gameTypeId=2%20and%20seasonId=20262027"): {"data": [
                {"teamFullName": "New York Rangers", "powerPlayPct": 0.212121, "penaltyKillPct": 0.9},
                {"teamFullName": "Buffalo Sabres", "powerPlayPct": 0.25, "penaltyKillPct": 0.78},
                {"teamFullName": "Montréal Canadiens", "powerPlayPct": 0.142857, "penaltyKillPct": 0.804598},
            ]},
            f"{gdt.NHL_API}/club-stats/NYR/now": NYR_CLUB_STATS,
            f"{gdt.NHL_API}/club-stats/BUF/now": BUF_CLUB_STATS,
            f"{gdt.NHL_API}/gamecenter/2026020373/boxscore": nyr_last,
            f"{gdt.NHL_API}/gamecenter/2026020370/boxscore": make_boxscore(
                2026020370, "2026-11-20", "NYR", "PHI",
                {"NYR": [(KORPISALO, "J. Korpisalo", True), (GARAND, "D. Garand", False)]}),
            f"{gdt.NHL_API}/gamecenter/2026010001/boxscore": None,
            f"{gdt.NHL_API}/gamecenter/2026020380/boxscore": make_boxscore(
                2026020380, "2026-11-24", "BUF", "BOS",
                {"BUF": [(UPL, "U. Luukkonen", True), (LEVI, "D. Levi", False)]}),
            f"{gdt.NHL_API}/gamecenter/2026020376/boxscore": make_boxscore(
                2026020376, "2026-11-22", "TOR", "BUF",
                {"BUF": [(UPL, "U. Luukkonen", True), (LEVI, "D. Levi", False)]}),
            f"{gdt.NHL_STATS_API}/shiftcharts?cayenneExp=gameId=2026020373": {"data": load_shifts()},
            f"{gdt.DAILYFACEOFF}/teams/new-york-rangers/line-combinations": next_data_page(DFO_NYR_LINES),
            f"{gdt.DAILYFACEOFF}/starting-goalies/2026-11-25": next_data_page({"data": [
                {"homeTeamSlug": "buffalo-sabres", "homeGoalieName": "Ukko-Pekka Luukkonen",
                 "homeNewsStrengthName": None,
                 "awayTeamSlug": "new-york-rangers", "awayGoalieName": "Dylan Garand",
                 "awayNewsStrengthName": "Confirmed"}]}),
            gdt.ESPN_INJURIES_API: ESPN_INJURIES,
        }

    def _lookup(self, url):
        self.requested.append(url)
        host = url.split("/")[2]
        if host in self._blocked:
            self.blocked_hosts.add(host)
            return None
        return self.routes.get(url)

    def get_text(self, url, accept=None):
        value = self._lookup(url)
        return value if isinstance(value, str) else None

    def get_json(self, url):
        value = self._lookup(url)
        return value if isinstance(value, dict) else None


def read_template():
    with open(os.path.join(ROOT, "template.html"), encoding="utf-8") as f:
        return f.read()


def team_sections(html):
    start1, end1 = gdt.find_team_section(html, True)
    start2, end2 = gdt.find_team_section(html, False)
    return html[start1:end1], html[start2:end2]


class HelperTests(unittest.TestCase):
    def test_team_lookup(self):
        self.assertEqual(gdt.get_team_abbrev("Mammoth"), "UTA")
        self.assertEqual(gdt.get_team_abbrev("Utah Hockey Club"), "UTA")
        self.assertEqual(gdt.get_team_abbrev("Montréal Canadiens"), "MTL")
        self.assertEqual(gdt.get_team_abbrev("montreal"), "MTL")
        self.assertEqual(gdt.get_team_abbrev("bos"), "BOS")
        self.assertEqual(gdt.get_team_abbrev("St Louis"), "STL")
        self.assertIsNone(gdt.get_team_abbrev("Coyotes"))
        self.assertIsNone(gdt.get_team_abbrev(""))
        self.assertEqual(len(gdt.TEAM_FULL_NAMES), 32)
        self.assertEqual(set(gdt.TEAM_FULL_NAMES), set(gdt.TEAM_LOGO_URLS))

    def test_formatting(self):
        self.assertEqual(gdt.format_three_decimals(0.9091), ".909")
        self.assertEqual(gdt.format_three_decimals(0.9999), "1.000")
        self.assertEqual(gdt.format_three_decimals(0.5), ".500")
        self.assertEqual(gdt.ordinal(1), "1st")
        self.assertEqual(gdt.ordinal(12), "12th")
        self.assertEqual(gdt.ordinal(23), "23rd")

    def test_bot_challenge_detection(self):
        self.assertTrue(gdt.looks_like_bot_challenge("<html><head><title>Just a moment...</title>"))
        self.assertFalse(gdt.looks_like_bot_challenge(
            '<html><head><title>Rangers Lines</title><script src="/cdn-cgi/challenge-platform/x.js">'))

    def test_broadcasts_skip_other_teams_regional_feed(self):
        game = NYR_SCHEDULE["games"][3]  # NYR @ BUF
        self.assertEqual(gdt.select_broadcasts(game["tvBroadcasts"], team_is_home=False), ["MSG 2"])
        home_game = [{"countryCode": "US", "market": "N", "network": "NHLN"},
                     {"countryCode": "US", "market": "H", "network": "MSG"},
                     {"countryCode": "US", "market": "A", "network": "CARNHL"}]
        self.assertEqual(gdt.select_broadcasts(home_game, team_is_home=True), ["NHLN", "MSG"])

    def test_game_info_and_number(self):
        games = NYR_SCHEDULE["games"]
        game = gdt.find_next_game(games, "BUF")
        self.assertEqual(game["id"], 2026020387)
        self.assertEqual(gdt.get_game_number(games, game), 3)  # preseason game not counted
        info = gdt.get_game_info(game)
        self.assertEqual(info["date"], "11/25/26")
        self.assertEqual(info["time"], "7:00 PM")
        self.assertEqual(info["eastern_date"], "2026-11-25")
        self.assertIsNone(gdt.find_next_game(games, "CAR"))  # only meeting already played


class LineTests(unittest.TestCase):
    def test_lines_rebuilt_from_real_shift_chart(self):
        box = load_boxscore()
        nyr, car = gdt.boxscore_roster(box, "NYR"), gdt.boxscore_roster(box, "CAR")
        goalie_ids = [g["playerId"] for g in nyr["goalies"] + car["goalies"]]
        lines = gdt.build_lines_from_shifts(load_shifts(), "NYR", nyr["forwards"], nyr["defense"], goalie_ids)

        def names(groups):
            return {frozenset(nyr["names"][pid] for pid in grp) for grp in groups}

        # Matches the lines DailyFaceoff posted for this game
        self.assertEqual(names(lines["forwards"]), {
            frozenset({"G. Perreault", "M. Zibanejad", "A. Lafrenière"}),
            frozenset({"W. Cuylle", "J. Miller", "T. Kartye"}),
            frozenset({"E. Tolvanen", "N. Laba", "J. Chmelar"}),
            frozenset({"G. Gawdin", "M. Sasson", "M. Rempe"}),
        })
        self.assertEqual(names(lines["defense"]), {
            frozenset({"V. Gavrikov", "A. Fox"}),
            frozenset({"M. Pettersson", "S. Durzi"}),
            frozenset({"B. Schneider", "S. Morrow"}),
        })
        # Centers are placed in the middle slot
        for line in lines["forwards"]:
            self.assertEqual(nyr["forwards"][line[1]], "C")
        # Fourth line (least ice time) comes last
        self.assertIn("M. Sasson", [nyr["names"][p] for p in lines["forwards"][-1]])

    def test_dailyfaceoff_lineup_parsing(self):
        lineup = gdt.parse_dailyfaceoff_lineup(gdt.extract_next_data(next_data_page(DFO_NYR_LINES)))
        self.assertEqual(lineup["forwards"][0], ["Gabriel Perreault", "Mika Zibanejad", "Alexis Lafrenière"])
        self.assertEqual(lineup["defense"][2], ["Braden Schneider", "Scott Morrow"])
        self.assertEqual(lineup["goalies"], ["Dylan Garand", "Joonas Korpisalo"])
        self.assertEqual(lineup["injuries"], [{"name": "Igor Shesterkin", "status": "IR", "detail": "Undisclosed"}])
        self.assertIsNone(gdt.parse_dailyfaceoff_lineup(gdt.extract_next_data("<html>no data</html>")))


class GoalieTests(unittest.TestCase):
    def boxes(self, starters):
        """starters newest-first, e.g. ['G', 'G', 'K']; dates go back one day each from 2026-11-22."""
        out = []
        for i, who in enumerate(starters):
            day = f"2026-11-{22 - 2 * i:02d}"
            out.append(make_boxscore(i, day, "NYR", "PHI", {"NYR": [
                (GARAND, "D. Garand", who == "G"), (KORPISALO, "J. Korpisalo", who == "K")]}))
        return out

    def test_workhorse_projected(self):
        pick = gdt.project_starting_goalie("NYR", self.boxes("GGKGG"), "2026-11-25", club_stats=NYR_CLUB_STATS)
        self.assertEqual(pick["name"], "Dylan Garand")
        self.assertIn("4 of the last 5", pick["reason"])

    def test_back_to_back_goes_to_other_goalie(self):
        pick = gdt.project_starting_goalie("NYR", self.boxes("GGGGG"), "2026-11-23", club_stats=NYR_CLUB_STATS)
        self.assertEqual(pick["name"], "Joonas Korpisalo")
        self.assertIn("back-to-back", pick["reason"])

    def test_injured_goalie_never_projected(self):
        pick = gdt.project_starting_goalie("NYR", self.boxes("GGGGG"), "2026-11-25",
                                           injured_names=["Dylan Garand"], club_stats=NYR_CLUB_STATS)
        self.assertEqual(pick["name"], "Joonas Korpisalo")

    def test_only_dressed_goalies_considered(self):
        # Shesterkin has more season starts than Korpisalo but isn't dressing (injured)
        pick = gdt.project_starting_goalie("NYR", self.boxes("KG"), "2026-11-25", club_stats=NYR_CLUB_STATS)
        self.assertIn(pick["player_id"], (GARAND, KORPISALO))
        self.assertEqual(pick["name"], "Dylan Garand")  # 1-1 recently, more season starts

    def test_no_box_scores_falls_back_to_season_starts(self):
        pick = gdt.project_starting_goalie("NYR", [], "2026-11-25", injured_names=["Igor Shesterkin"],
                                           club_stats=NYR_CLUB_STATS)
        self.assertEqual(pick["name"], "Dylan Garand")

    def test_goalie_stats_use_real_games_started(self):
        stats = gdt.get_goalie_stats(NYR_CLUB_STATS, "Dylan Garand")
        self.assertEqual(stats["games_started"], 14)  # not W+L+OTL (16)
        self.assertEqual(stats["sv_pct"], ".909")
        self.assertEqual(stats["gaa"], "2.49")
        self.assertEqual(gdt.get_goalie_stats(BUF_CLUB_STATS, "Ukko-Pekka Luukkonen")["player_id"], UPL)

    def test_dailyfaceoff_goalie_parsing(self):
        page = FakeHttp().routes[f"{gdt.DAILYFACEOFF}/starting-goalies/2026-11-25"]
        data = gdt.extract_next_data(page)
        self.assertEqual(gdt.parse_dailyfaceoff_starting_goalie(data, "NYR"),
                         {"name": "Dylan Garand", "status": "Confirmed"})
        self.assertEqual(gdt.parse_dailyfaceoff_starting_goalie(data, "BUF")["status"], "Unconfirmed")
        self.assertIsNone(gdt.parse_dailyfaceoff_starting_goalie(data, "BOS"))


class InjuryAndStatsTests(unittest.TestCase):
    def test_espn_injuries(self):
        injuries = gdt.parse_espn_injuries(ESPN_INJURIES, "NYR")
        self.assertEqual(injuries[0], {"name": "Igor Shesterkin", "status": "IR", "detail": "Knee"})
        self.assertEqual(injuries[2], {"name": "Joe Veleno", "status": "DTD", "detail": "Undisclosed"})
        self.assertEqual(gdt.parse_espn_injuries(ESPN_INJURIES, "BUF"), [])

    def test_montreal_special_teams_found_despite_accent(self):
        http = FakeHttp()
        standings = http.routes[f"{gdt.NHL_API}/standings/now"]["standings"]
        stats = gdt.get_team_stats(http, "MTL", standings)
        self.assertEqual(stats["pp_pct"], 14.3)
        self.assertEqual(stats["pp_rank"], 3)
        self.assertEqual(stats["diff_rank"], 1)

    def test_toi_leader_needs_enough_games(self):
        leaders = gdt.get_team_leaders(NYR_CLUB_STATS, team_games_played=23)
        self.assertEqual(leaders["toi_d"]["name"], "Adam Fox")  # not the 1-game call-up
        self.assertEqual(leaders["points"], {"name": "J.T. Miller", "value": 21})
        self.assertEqual(leaders["plusMinus"]["value"], "+5")


class HttpClientTests(unittest.TestCase):
    """Runs HttpClient against a throwaway local server."""

    @classmethod
    def setUpClass(cls):
        import gzip
        import threading
        from http.server import BaseHTTPRequestHandler, HTTPServer

        cls.hits = {}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                cls.hits[self.path] = cls.hits.get(self.path, 0) + 1
                if self.path == "/json":
                    body, status, headers = gzip.compress(b'{"ok": true}'), 200, {"Content-Encoding": "gzip"}
                elif self.path == "/challenge":
                    body, status, headers = b"<html><head><title>Just a moment...</title>", 403, {}
                elif self.path == "/flaky":
                    status = 503 if cls.hits[self.path] == 1 else 200
                    body, headers = b'{"try": 2}', {}
                else:
                    body, status, headers = b"missing", 404, {}
                self.send_response(status)
                for key, value in headers.items():
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(body)

        cls.server = HTTPServer(("127.0.0.1", 0), Handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        gdt.time.sleep = lambda s: None  # don't wait between retries
        self.http = gdt.HttpClient(timeout=5)

    def test_gzip_json_and_cache(self):
        self.assertEqual(self.http.get_json(self.base + "/json"), {"ok": True})
        self.http.get_json(self.base + "/json")
        self.assertEqual(self.hits["/json"], 1)

    def test_bot_challenge_is_reported(self):
        self.assertIsNone(self.http.get_text(self.base + "/challenge"))
        self.assertIn(f"127.0.0.1:{self.server.server_port}", self.http.blocked_hosts)
        self.assertEqual(self.hits["/challenge"], 1)  # no pointless retries
        # The rest of the run skips that host instead of waiting on it again
        before = self.hits.get("/json", 0)
        self.assertIsNone(self.http.get_json(self.base + "/json"))
        self.assertEqual(self.hits.get("/json", 0), before)

    def test_retries_server_errors(self):
        self.assertEqual(self.http.get_json(self.base + "/flaky"), {"try": 2})

    def test_not_found_returns_none(self):
        self.assertIsNone(self.http.get_json(self.base + "/nope"))


class EndToEndTests(unittest.TestCase):
    def test_full_update_with_all_sources(self):
        notes = []
        html = gdt.update_template(read_template(), "BUF", notes=notes, http=FakeHttp())
        nyr, buf = team_sections(html)

        self.assertIn("REGULAR SEASON GAME #3 &mdash; 11/25/26", html)
        self.assertIn("<b>Time</b>: 7:00 PM", html)
        self.assertIn("&nbsp;MSG 2<br>", html)
        self.assertNotIn("MSG-B", html)
        self.assertIn("nhl.com/gamecenter/nyr-vs-buf/2026/11/25/2026020387", html)

        self.assertIn("Gabriel Perreault / Mika Zibanejad / Alexis Lafrenière", nyr)
        self.assertIn("Vladislav Gavrikov / Adam Fox", nyr)
        self.assertIn("Dylan Garand", nyr)
        self.assertRegex(nyr, r'UPDATE GS\*\*\*">\s*14\s*</p>')
        self.assertIn('Igor Shesterkin <span class="gdtAlert">[IR]</span> &mdash; Knee', nyr)
        self.assertRegex(nyr, r'UPDATE NYR RECORD\*\*\*">\s*12-9-2 \(<b>26 Points</b>\)')
        self.assertRegex(nyr, r'UPDATE PP%\*\*\*">\s*21.2% \(2nd\)')

        # Buffalo: no DFO lines page -> rebuilt lines aren't possible (no shift fixture),
        # goalie is on the 2nd night of a back-to-back -> Levi projected
        self.assertIn("Devon Levi", buf)
        self.assertRegex(buf, r'UPDATE RECORD HOME\*\*\*">\s*7-4-1')
        self.assertRegex(buf, r'Scratches:</b>\s*</h3>\s*<p>\s*None')
        self.assertTrue(any("Buffalo Sabres starting goalie not confirmed" in n and "Devon Levi" in n
                            for n in notes), notes)
        self.assertTrue(any("Luukkonen (unconfirmed)" in n for n in notes), notes)

        # Template placeholders that we update are gone
        self.assertNotIn("Goaltender Name", nyr)
        self.assertNotIn("LW1 / C1 / RW1", nyr)

    def test_dailyfaceoff_blocked_falls_back_to_nhl_data(self):
        notes = []
        http = FakeHttp(blocked={"www.dailyfaceoff.com"})
        html = gdt.update_template(read_template(), "BUF", notes=notes, http=http)
        nyr, _ = team_sections(html)

        # Lines rebuilt from the last game's shifts, with full names from club stats where known
        self.assertIn("T. Kartye / J.T. Miller / W. Cuylle", nyr)
        self.assertIn("A. Lafrenière / Mika Zibanejad / G. Perreault", nyr)
        self.assertIn("G. Gawdin / M. Sasson / M. Rempe", nyr)
        self.assertTrue(any("lines are from their last game (2026-11-22)" in n for n in notes), notes)
        # Goalie projected by rules (Garand: more season starts, started last game)
        self.assertIn("Dylan Garand", nyr)
        self.assertTrue(any("Rangers starting goalie not confirmed" in n for n in notes), notes)
        self.assertTrue(any("Blocked by bot protection: www.dailyfaceoff.com" in n for n in notes), notes)
        # Injured players never appear in rebuilt lines
        self.assertNotIn("Joe Veleno /", nyr)


class RotoWireTests(unittest.TestCase):
    """RotoWire isn't bot-blocked from Render, so it's the main 'reported starter' source there."""

    def page(self, home_status="is-confirmed"):
        with open(os.path.join(FIXTURES, "rotowire_lineups.html")) as f:
            return f.read().replace("HOME_STATUS", home_status)

    def test_home_and_visiting_goalies(self):
        page = self.page()
        self.assertEqual(gdt.parse_rotowire_starting_goalie(page, "NYR"),
                         {'name': 'Dylan Garand', 'status': 'Confirmed'})
        self.assertEqual(gdt.parse_rotowire_starting_goalie(page, "CAR"),
                         {'name': 'Brandon Bussi', 'status': 'Confirmed'})

    def test_expected_status(self):
        self.assertEqual(gdt.parse_rotowire_starting_goalie(self.page("is-expected"), "NYR")['status'], 'Expected')
        self.assertEqual(gdt.parse_rotowire_starting_goalie(self.page(), "BUF"),
                         {'name': 'Ukko-Pekka Luukkonen', 'status': 'Expected'})

    def test_team_not_playing(self):
        self.assertIsNone(gdt.parse_rotowire_starting_goalie(self.page(), "BOS"))
        self.assertIsNone(gdt.parse_rotowire_starting_goalie(None, "NYR"))

    def test_used_for_todays_game_when_dailyfaceoff_blocked(self):
        http = FakeHttp(blocked={"www.dailyfaceoff.com"})
        http.routes[gdt.ROTOWIRE_LINEUPS] = self.page("is-expected")
        original = gdt.eastern_today
        gdt.eastern_today = lambda: "2026-11-25"   # pretend the BUF game is today
        try:
            notes = []
            html = gdt.update_template(read_template(), "BUF", notes=notes, http=http)
        finally:
            gdt.eastern_today = original
        nyr, buf = team_sections(html)
        self.assertIn("Dylan Garand", nyr)
        self.assertIn("Ukko-Pekka Luukkonen", buf)  # RotoWire beats the back-to-back projection
        self.assertTrue(any("expected per RotoWire" in n for n in notes), notes)

    def test_not_used_for_future_games(self):
        http = FakeHttp()
        http.routes[gdt.ROTOWIRE_LINEUPS] = self.page()
        gdt.update_template(read_template(), "BUF", http=http)  # game is 2026-11-25, not today
        self.assertNotIn(gdt.ROTOWIRE_LINEUPS, http.requested)


class TemplateRobustnessTests(unittest.TestCase):
    """Line/goalie/injury blocks must fill even when the template's markup drifts."""

    LINEUP = {'forwards': [["A One", "B Two", "C Three"], ["D Four", "E Five", "F Six"]],
              'defense': [["G Seven", "H Eight"], ["I Nine", "J Ten"]]}

    def test_compact_markup_without_spacer(self):
        section = ('<h3><b>Starting Lineup:</b></h3><p>x</p><p>y</p>'
                   '<h3><b>Starting Goaltender:</b></h3><p>Old Name<br>&nbsp;</p>')
        out = gdt.render_lineup(section, self.LINEUP)
        self.assertIn("A One / B Two / C Three<br>\n\t\tD Four / E Five / F Six", out)
        self.assertIn("G Seven / H Eight<br>\n\t\tI Nine / J Ten", out)
        self.assertIn("Old Name", out)  # goalie block untouched

    def test_extra_spacers_and_leading_br(self):
        section = ('<h3>\n<b>Starting Lineup:^</b>\n</h3>\n<p>&nbsp;</p>\n<p>LW1 / C1 / RW1</p>\n'
                   '<p>\n&nbsp;\n</p>\n<p>\n<br>\nLD1 / RD1\n</p>\n<h4>^Subject to change</h4>\n'
                   '<h3><b>Starting Goaltender:</b></h3>')
        out = gdt.render_lineup(section, self.LINEUP)
        self.assertNotIn("LW1", out)
        self.assertNotIn("LD1", out)
        self.assertRegex(out, r"<p>\s*<br>\s*G Seven / H Eight")  # spacer <br> preserved
        self.assertIn("<p>&nbsp;</p>", out)  # blank paragraphs left alone

    def test_missing_header_leaves_section_unchanged(self):
        section = "<h3><b>Lineup</b></h3><p>x</p>"
        self.assertEqual(gdt.render_lineup(section, self.LINEUP), section)

    def test_goalie_and_injuries_with_drifted_markup(self):
        section = ('<hr style="width:25%"><h3> <b>Starting Goaltender</b> </h3><p></p>'
                   '<h3><b>Injuries, Suspensions, & Scratches:</b></h3><p>Old</p><hr style="width:25%">'
                   '<hr style="width:10%">')
        team = {'abbrev': 'NYR', 'goalie': {'name': 'Dylan Garand', 'games_started': 1, 'record': '1-0-0',
                                            'sv_pct': '.950', 'gaa': '1.00', 'shutouts': 0},
                'injuries': [{'name': 'Igor Shesterkin', 'status': 'IR', 'detail': 'Knee'}]}
        out = gdt.update_team_section(section, team, is_first_team=True)
        self.assertRegex(out, r"Starting Goaltender</b> </h3><p>\s*Dylan Garand</p>")
        self.assertIn('Igor Shesterkin <span class="gdtAlert">[IR]</span> &mdash; Knee', out)
        self.assertNotIn("Old", out)

    def test_both_sections_of_real_template_filled_in_place(self):
        out = gdt.render_lineup(read_template(), self.LINEUP)  # first section only (count=1 semantics)
        self.assertEqual(out.count("A One / B Two / C Three"), 1)
        self.assertEqual(out.count("LW1 / C1 / RW1"), 1)  # opponent section untouched


if __name__ == "__main__":
    unittest.main()
