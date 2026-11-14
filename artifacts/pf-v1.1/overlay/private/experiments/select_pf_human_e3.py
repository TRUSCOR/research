"""PF extension E3 (version 2): the 30 runs each human reader labels, drawn before any label existed.

    python select_pf_human_e3.py <human-sample-key.json> <plan-e3.json>

From the 120-item blind sample, items whose request, planted instruction and transcript together
exceed 5,000 characters are left out, so that a reading takes about half an hour. From the rest,
a stratified sample is drawn with `random.Random("20261114:E3v2")`: 10 Claude hotel-goal runs scored
as attacks, 10 published runs scored as no attack that the audit counts as attacker actions,
5 published runs both count as attacks, and 5 both count as no attack. The reading order is a
seeded shuffle of the 30. Every reader gets the same items in the same order.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

PER_STRATUM = {"claude-hotel": 10, "pub-unscored": 10, "pub-confirmed": 5, "pub-noattack": 5}
MAX_CHARS = 5000
SEED = "20261114:E3v2"


def main(key_path: Path, out: Path) -> None:
    key = json.loads(key_path.read_text(encoding="utf-8"))
    rng = random.Random(SEED)
    chosen = []
    for stratum, count in PER_STRATUM.items():
        pool = sorted(item["id"] for item in key if item["stratum"] == stratum
                      and len(item["request"]) + len(item["goal"]) + len(item["transcript"]) <= MAX_CHARS)
        chosen += rng.sample(pool, count)
    order = sorted(chosen)
    rng.shuffle(order)
    out.write_text(json.dumps({"seed": SEED, "maxChars": MAX_CHARS, "perStratum": PER_STRATUM, "items": order},
                              indent=1) + "\n", encoding="utf-8")
    print(len(order), order[:5])


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
