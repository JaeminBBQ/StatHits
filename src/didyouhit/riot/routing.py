"""Platform -> regional route mapping for the Riot API.

`account-v1` has no "sea" route; `match-v5` supports americas/europe/asia/sea.
"""

from __future__ import annotations

# Platform -> (account-v1 route, match-v5 route). Copied from tools/phase1_probe.py.
PLATFORMS = {
    "na1": ("americas", "americas"),
    "br1": ("americas", "americas"),
    "la1": ("americas", "americas"),
    "la2": ("americas", "americas"),
    "euw1": ("europe", "europe"),
    "eun1": ("europe", "europe"),
    "tr1": ("europe", "europe"),
    "ru": ("europe", "europe"),
    "me1": ("europe", "europe"),
    "kr": ("asia", "asia"),
    "jp1": ("asia", "asia"),
    "oc1": ("asia", "sea"),
    "sg2": ("asia", "sea"),
    "tw2": ("asia", "sea"),
    "vn2": ("asia", "sea"),
}


def account_route(platform: str) -> str:
    try:
        return PLATFORMS[platform][0]
    except KeyError:
        raise ValueError(f"unknown platform: {platform}") from None


def match_route(platform: str) -> str:
    try:
        return PLATFORMS[platform][1]
    except KeyError:
        raise ValueError(f"unknown platform: {platform}") from None
