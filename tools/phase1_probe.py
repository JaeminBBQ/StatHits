#!/usr/bin/env python3
"""Phase 1: check what match-v5 returns for ARAM: Mayhem games.

Usage:
    python3 phase1_probe.py "GameName#TAG" --platform na1 [--count 20]

Reads RIOT_API_KEY from .env. The key is sent only as a header and never printed.
Stdlib only (Python 3.9+).
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque

# Queue IDs we believe are Mayhem. Confirmed/corrected by this script's output.
DEFAULT_MAYHEM_QUEUES = {2400}
KNOWN_QUEUES = {
    400: "Normal Draft", 420: "Ranked Solo/Duo", 430: "Normal Blind", 440: "Ranked Flex",
    450: "ARAM", 480: "Swiftplay", 490: "Quickplay", 700: "Clash", 900: "URF/ARURF",
    1700: "Arena", 1710: "Arena", 2400: "ARAM: Mayhem (suspected)",
}

# Platform -> (account-v1 route, match-v5 route). account-v1 has no "sea" route.
PLATFORMS = {
    "na1": ("americas", "americas"), "br1": ("americas", "americas"),
    "la1": ("americas", "americas"), "la2": ("americas", "americas"),
    "euw1": ("europe", "europe"), "eun1": ("europe", "europe"),
    "tr1": ("europe", "europe"), "ru": ("europe", "europe"), "me1": ("europe", "europe"),
    "kr": ("asia", "asia"), "jp1": ("asia", "asia"),
    "oc1": ("asia", "sea"), "sg2": ("asia", "sea"), "tw2": ("asia", "sea"),
    "vn2": ("asia", "sea"),
}

MATCH_FIELDS = [
    "totalDamageDealtToChampions", "physicalDamageDealtToChampions",
    "magicDamageDealtToChampions", "trueDamageDealtToChampions",
    "largestCriticalStrike", "totalDamageTaken", "damageSelfMitigated", "totalHeal",
    "totalHealsOnTeammates", "totalDamageShieldedOnTeammates", "timeCCingOthers",
    "largestMultiKill", "pentaKills", "goldEarned", "gameEndedInEarlySurrender",
]
CHAMP_STATS = ["abilityPower", "attackDamage", "healthMax", "armor", "magicResist", "attackSpeed"]


def load_api_key():
    key = os.environ.get("RIOT_API_KEY")
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not key and os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("RIOT_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not key:
        sys.exit("RIOT_API_KEY not found. Put RIOT_API_KEY=RGAPI-... in .env")
    return key


class RiotClient:
    """Tiny client: sliding-window limits (20/1s, 100/120s) and Retry-After on 429."""

    LIMITS = [(20, 1.0), (100, 120.0)]

    def __init__(self, key):
        self.key = key
        self.sent = deque()
        self.calls = 0

    def _throttle(self):
        while True:
            now = time.monotonic()
            while self.sent and now - self.sent[0] > 120.0:
                self.sent.popleft()
            wait = 0.0
            for limit, window in self.LIMITS:
                recent = [t for t in self.sent if now - t < window]
                if len(recent) >= limit:
                    wait = max(wait, window - (now - recent[0]) + 0.05)
            if wait <= 0:
                return
            print(f"  (rate limit: waiting {wait:.1f}s)", file=sys.stderr)
            time.sleep(wait)

    def get(self, route, path, params=None):
        """Returns (status, json_or_None, error_text_or_None)."""
        url = f"https://{route}.api.riotgames.com{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        last_err = "rate limited"
        for _attempt in range(5):
            self._throttle()
            self.sent.append(time.monotonic())
            self.calls += 1
            req = urllib.request.Request(url, headers={"X-Riot-Token": self.key, "User-Agent": "aram-mayhem-probe/0.1"})
            try:
                with urllib.request.urlopen(req, timeout=20) as resp:
                    return resp.status, json.load(resp), None
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", "replace")[:300]
                if e.code == 429:
                    retry = float(e.headers.get("Retry-After") or 10)
                    print(f"  429 rate limited, Retry-After={retry:.0f}s", file=sys.stderr)
                    time.sleep(retry + 0.5)
                    continue
                if e.code in (500, 502, 503, 504):
                    time.sleep(2)
                    continue
                return e.code, None, body
            except (urllib.error.URLError, OSError) as e:
                last_err = str(getattr(e, "reason", e))
                time.sleep(2)
                continue
        return 0, None, f"gave up after repeated retries ({last_err})"


def fmt_duration(info):
    secs = info.get("gameDuration", 0)
    # Pre-11.20 matches reported ms; modern ones report seconds.
    if secs > 100000:
        secs //= 1000
    return f"{secs // 60}:{secs % 60:02d}"


def queue_label(qid):
    return KNOWN_QUEUES.get(qid, "UNKNOWN")


def augment_fields(participant):
    return {k: v for k, v in participant.items() if "augment" in k.lower()}


def timeline_stats(timeline, participant_id):
    frames = (timeline.get("info") or {}).get("frames") or []
    pid = str(participant_id)
    final, peak = {}, {}
    for frame in frames:
        stats = ((frame.get("participantFrames") or {}).get(pid) or {}).get("championStats") or {}
        for s in CHAMP_STATS:
            if s in stats:
                peak[s] = max(peak.get(s, stats[s]), stats[s])
        if stats:
            final = stats
    return len(frames), final, peak


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("riot_id", help='e.g. "Faker#KR1"')
    ap.add_argument("--platform", default="na1", choices=sorted(PLATFORMS))
    ap.add_argument("--count", type=int, default=20, help="recent matches to inspect (max 100)")
    ap.add_argument("--mayhem-queue", type=int, action="append",
                    help="queue ID(s) to treat as Mayhem (default: 2400)")
    ap.add_argument("--details-all", action="store_true",
                    help="print stat details for every match, not just Mayhem")
    args = ap.parse_args()

    if "#" not in args.riot_id:
        sys.exit('Riot ID must look like "GameName#TAG"')
    game_name, tag = args.riot_id.rsplit("#", 1)
    mayhem_queues = set(args.mayhem_queue or DEFAULT_MAYHEM_QUEUES)
    account_route, match_route = PLATFORMS[args.platform]
    client = RiotClient(load_api_key())

    # 1. Riot ID -> PUUID
    status, acct, err = client.get(
        account_route,
        "/riot/account/v1/accounts/by-riot-id/"
        f"{urllib.parse.quote(game_name)}/{urllib.parse.quote(tag)}",
    )
    if status != 200:
        sys.exit(f"account-v1 failed: HTTP {status} {err}")
    puuid = acct["puuid"]
    print(f"Account: {acct.get('gameName')}#{acct.get('tagLine')}  (routes: account={account_route}, match={match_route})")

    # 2. Recent match IDs, plus a queue-filtered list so we can classify
    #    Mayhem matches even if fetching the match itself fails.
    ids_path = f"/lol/match/v5/matches/by-puuid/{puuid}/ids"
    status, match_ids, err = client.get(match_route, ids_path, {"start": 0, "count": args.count})
    if status != 200:
        sys.exit(f"match id list failed: HTTP {status} {err}")
    queue_filtered = {}
    for q in sorted(mayhem_queues):
        status, ids, err = client.get(match_route, ids_path, {"start": 0, "count": 100, "queue": q})
        if status == 200:
            for mid in ids:
                queue_filtered[mid] = q
            print(f"Queue filter {q}: {len(ids)} match IDs in history")
        else:
            print(f"Queue filter {q}: HTTP {status} {err}")
    print(f"Inspecting {len(match_ids)} most recent matches\n")

    # 3. Fetch each match + timeline
    summary = []  # dicts for the final report
    header = f"{'matchId':<18} {'queue':>5} {'label':<24} {'gameMode':<14} {'dur':>6}  match  timeline"
    print(header)
    print("-" * len(header))
    details = []
    for mid in match_ids:
        m_status, match, m_err = client.get(match_route, f"/lol/match/v5/matches/{mid}")
        t_status, timeline, t_err = client.get(match_route, f"/lol/match/v5/matches/{mid}/timeline")
        info = (match or {}).get("info") or {}
        qid = info.get("queueId", queue_filtered.get(mid))
        is_mayhem = qid in mayhem_queues or mid in queue_filtered
        row = {
            "matchId": mid, "queueId": qid, "gameMode": info.get("gameMode", "?"),
            "mayhem": is_mayhem, "match_status": m_status, "timeline_status": t_status,
            "match_err": m_err, "timeline_err": t_err,
        }
        summary.append(row)
        print(f"{mid:<18} {str(qid):>5} {queue_label(qid) if qid else '?':<24} "
              f"{row['gameMode']:<14} {fmt_duration(info) if info else '?':>6}  "
              f"{m_status:>5}  {t_status:>8}{'  <-- MAYHEM' if is_mayhem else ''}")
        if (is_mayhem or args.details_all) and (match or timeline):
            details.append((mid, qid, match, timeline))

    # 4. Per-match stat details for my participant
    for mid, qid, match, timeline in details:
        print(f"\n=== {mid}  queueId={qid} ===")
        me = None
        if match:
            me = next((p for p in match["info"]["participants"] if p.get("puuid") == puuid), None)
        if not me:
            print("  (match data unavailable or participant not found)")
        else:
            print(f"  champion={me.get('championName')}  participantId={me.get('participantId')}  win={me.get('win')}")
            for f in MATCH_FIELDS:
                print(f"  {f:<34} {me.get(f, 'MISSING')}")
            ch = me.get("challenges")
            dpm = ch.get("damagePerMinute", "MISSING") if isinstance(ch, dict) else "NO challenges OBJECT"
            print(f"  {'challenges.damagePerMinute':<34} {dpm}")
            augs = augment_fields(me)
            print(f"  augment fields: {augs if augs else 'NONE PRESENT'}")
        if timeline and me:
            n_frames, final, peak = timeline_stats(timeline, me["participantId"])
            print(f"  timeline frames: {n_frames}")
            print(f"  {'championStat':<16} {'final':>10} {'peak':>10}")
            for s in CHAMP_STATS:
                print(f"  {s:<16} {str(final.get(s, 'MISSING')):>10} {str(peak.get(s, 'MISSING')):>10}")
        elif not timeline:
            print("  (timeline unavailable)")

    # 5. Error report: Mayhem vs everything else
    print("\n=== Error report ===")
    for label, rows in (("Mayhem", [r for r in summary if r["mayhem"]]),
                        ("Other", [r for r in summary if not r["mayhem"]])):
        m_fail = [r for r in rows if r["match_status"] != 200]
        t_fail = [r for r in rows if r["timeline_status"] != 200]
        print(f"{label}: {len(rows)} matches | match fetch failures: {len(m_fail)} | timeline failures: {len(t_fail)}")
        for r in m_fail:
            print(f"  {r['matchId']} match HTTP {r['match_status']}: {r['match_err']}")
        for r in t_fail:
            print(f"  {r['matchId']} timeline HTTP {r['timeline_status']}: {r['timeline_err']}")
    unknown = sorted({r["queueId"] for r in summary if r["queueId"] and r["queueId"] not in KNOWN_QUEUES})
    if unknown:
        print(f"Unrecognized queue IDs (Mayhem candidates if 2400 is wrong): {unknown}")
    print(f"\nTotal API calls: {client.calls}")


if __name__ == "__main__":
    main()
