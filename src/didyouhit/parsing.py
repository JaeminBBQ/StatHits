"""Pure parsing of match-v5 match + timeline JSON into records. No I/O.

Timeline frames are ~60s snapshots; "peak" is the max across frames and
"final" is the last frame that has stats (see `docs/ARCHITECTURE.md`).
"""

from __future__ import annotations

from dataclasses import dataclass

CHAMP_STATS = ("abilityPower", "attackDamage", "healthMax", "armor", "magicResist", "attackSpeed")

# MemberGameStats field -> Riot participant JSON key
MATCH_STAT_MAP = {
    "damage_to_champions": "totalDamageDealtToChampions",
    "physical_damage_to_champions": "physicalDamageDealtToChampions",
    "magic_damage_to_champions": "magicDamageDealtToChampions",
    "true_damage_to_champions": "trueDamageDealtToChampions",
    "largest_crit": "largestCriticalStrike",
    "damage_taken": "totalDamageTaken",
    "damage_mitigated": "damageSelfMitigated",
    "total_heal": "totalHeal",
    "heals_on_teammates": "totalHealsOnTeammates",
    "shields_on_teammates": "totalDamageShieldedOnTeammates",
    "cc_time": "timeCCingOthers",
    "largest_multikill": "largestMultiKill",
    "penta_kills": "pentaKills",
    "gold_earned": "goldEarned",
}


@dataclass(frozen=True)
class MatchSummary:
    match_id: str
    platform: str
    queue_id: int | None
    game_mode: str | None
    game_start_ms: int | None
    game_end_ms: int | None
    duration_s: int | None
    is_arena: bool
    is_valid: bool


@dataclass(frozen=True)
class MemberGameStats:
    match_id: str
    champion_name: str
    champion_id: int | None
    placement: int | None
    subteam_id: int | None
    augments: list[int]
    damage_to_champions: int | None
    physical_damage_to_champions: int | None
    magic_damage_to_champions: int | None
    true_damage_to_champions: int | None
    largest_crit: int | None
    damage_taken: int | None
    damage_mitigated: int | None
    total_heal: int | None
    heals_on_teammates: int | None
    shields_on_teammates: int | None
    cc_time: int | None
    largest_multikill: int | None
    penta_kills: int | None
    gold_earned: int | None
    damage_per_minute: float | None
    final_ap: float | None
    peak_ap: float | None
    final_ad: float | None
    peak_ad: float | None
    final_health_max: float | None
    peak_health_max: float | None
    final_armor: float | None
    final_mr: float | None
    final_attack_speed: float | None
    peak_attack_speed: float | None
    game_end_ms: int | None
    duration_s: int | None


def _duration_s(info: dict) -> int | None:
    raw = info.get("gameDuration")
    if raw is None:
        return None
    # Pre-11.20 matches reported milliseconds; modern ones report seconds.
    return raw // 1000 if raw > 100000 else raw


def parse_match_summary(match: dict, *, min_duration_s: int) -> MatchSummary:
    info = match.get("info") or {}
    metadata = match.get("metadata") or {}
    duration_s = _duration_s(info)
    early_surrender = any(
        bool(p.get("gameEndedInEarlySurrender")) for p in info.get("participants") or []
    )
    is_valid = not early_surrender and duration_s is not None and duration_s >= min_duration_s
    return MatchSummary(
        match_id=str(metadata.get("matchId") or ""),
        platform=str(info.get("platformId") or "").lower(),
        queue_id=info.get("queueId"),
        game_mode=info.get("gameMode"),
        game_start_ms=info.get("gameStartTimestamp"),
        game_end_ms=info.get("gameEndTimestamp"),
        duration_s=duration_s,
        is_arena=info.get("gameMode") == "CHERRY",
        is_valid=is_valid,
    )


def _find_participant(match: dict, puuid: str) -> dict | None:
    participants = (match.get("info") or {}).get("participants") or []
    return next((p for p in participants if p.get("puuid") == puuid), None)


def _augments(participant: dict) -> list[int]:
    return [
        int(participant[key])
        for key in (f"playerAugment{i}" for i in range(1, 7))
        if participant.get(key)
    ]


def _timeline_stats(
    timeline: dict | None, participant_id: int | None
) -> tuple[dict[str, float], dict[str, float]]:
    """Return (final, peak) championStats for one participant, empty if absent."""
    if timeline is None or participant_id is None:
        return {}, {}
    frames = (timeline.get("info") or {}).get("frames") or []
    pid = str(participant_id)
    final: dict[str, float] = {}
    peak: dict[str, float] = {}
    for frame in frames:
        stats = ((frame.get("participantFrames") or {}).get(pid) or {}).get("championStats") or {}
        for stat in CHAMP_STATS:
            value = stats.get(stat)
            if value is not None:
                peak[stat] = max(peak.get(stat, value), value)
        if stats:
            final = stats
    return final, peak


def parse_member_game(match: dict, timeline: dict | None, puuid: str) -> MemberGameStats | None:
    """Parse one participant's stats; `None` if the PUUID is not in the match."""
    participant = _find_participant(match, puuid)
    if participant is None:
        return None
    info = match.get("info") or {}
    metadata = match.get("metadata") or {}
    final, peak = _timeline_stats(timeline, participant.get("participantId"))
    challenges = participant.get("challenges")
    damage_per_minute = challenges.get("damagePerMinute") if isinstance(challenges, dict) else None
    return MemberGameStats(
        match_id=str(metadata.get("matchId") or ""),
        champion_name=str(participant.get("championName") or ""),
        champion_id=participant.get("championId"),
        placement=participant.get("placement"),
        subteam_id=participant.get("playerSubteamId"),
        augments=_augments(participant),
        damage_per_minute=damage_per_minute,
        final_ap=final.get("abilityPower"),
        peak_ap=peak.get("abilityPower"),
        final_ad=final.get("attackDamage"),
        peak_ad=peak.get("attackDamage"),
        final_health_max=final.get("healthMax"),
        peak_health_max=peak.get("healthMax"),
        final_armor=final.get("armor"),
        final_mr=final.get("magicResist"),
        final_attack_speed=final.get("attackSpeed"),
        peak_attack_speed=peak.get("attackSpeed"),
        game_end_ms=info.get("gameEndTimestamp"),
        duration_s=_duration_s(info),
        **{name: participant.get(json_key) for name, json_key in MATCH_STAT_MAP.items()},
    )
