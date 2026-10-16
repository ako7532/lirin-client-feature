"""Offline opponent-model trainer for the Yin-Yang Duel.

Reads the versioned JSON-lines history produced by the feature
(yin_yang_duel_history.jsonl) and derives a compact frequency table for the
opponent's leads and responses, keyed by a coarse state.  Output is written to
yin_yang_duel_model.json, which client_feature.py loads automatically when it
exists next to the script.

Run this outside the game (any Python 3):

    python train_yin_yang_duel.py
"""

import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(HERE, "yin_yang_duel_model.json")


def duel_card_color(value):
    return "black" if (int(value) % 2) == 0 else "white"


def round_bucket(round_num):
    if round_num <= 3:
        return "early"
    if round_num <= 6:
        return "mid"
    return "late"


def find_history_paths():
    """History may live in the repository root (older runs) or in a per-branch
    runtime directory (`.runtime/<branch>/yin_yang_duel_history.jsonl`)."""
    paths = []
    root = os.path.join(HERE, "yin_yang_duel_history.jsonl")
    if os.path.isfile(root):
        paths.append(root)
    runtime_root = os.path.join(HERE, ".runtime")
    if os.path.isdir(runtime_root):
        for branch in sorted(os.listdir(runtime_root)):
            candidate = os.path.join(runtime_root, branch,
                                     "yin_yang_duel_history.jsonl")
            if os.path.isfile(candidate):
                paths.append(candidate)
    return paths


def load_events(paths):
    events = []
    for path in paths:
        with open(path, "rb") as source:
            data = source.read()
        text = data.decode("utf-8", "replace") if isinstance(data, bytes) else data
        for raw in text.splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                events.append(json.loads(raw))
            except ValueError:
                continue
    return events


def main():
    paths = sys.argv[1:] if len(sys.argv) > 1 else find_history_paths()
    events = load_events(paths)
    if not events:
        print("No history found (searched: %s)" % (paths or find_history_paths()))
        return

    by_match = collections.defaultdict(list)
    for ev in events:
        by_match[ev.get("match_id", 0)].append(ev)

    lead_counts = collections.defaultdict(collections.Counter)
    response_counts = collections.defaultdict(collections.Counter)

    for match_id, match_events in by_match.items():
        # decision events by round: round -> decision dict
        decisions = {}
        for ev in match_events:
            if ev.get("event") == "decision":
                decisions[int(ev.get("round", 0))] = ev
        for ev in match_events:
            if ev.get("event") != "play" or ev.get("actor") != "them":
                continue
            round_num = int(ev.get("round", 0))
            if round_num <= 0:
                continue
            card = int(ev.get("card", -1))
            if card < 0:
                continue
            leads = int(ev.get("leads", 0))
            bucket = round_bucket(round_num)
            decision = decisions.get(round_num, {})
            opp_mask = int(decision.get("opponent_remaining_mask", 0) or 0)
            opp_count = sum(1 for v in range(9) if opp_mask & (1 << v))
            if opp_count <= 0:
                opp_count = 10 - round_num
            if leads == 0:
                # opponent led
                lead_counts["%d|%s" % (opp_count, bucket)][str(card)] += 1
            else:
                # opponent responded to our lead; key by our led colour.
                our_card = decision.get("chosen_card")
                color = duel_card_color(our_card) if our_card is not None else "unknown"
                response_counts["%s|%d|%s" % (color, opp_count, bucket)][str(card)] += 1

    model = {
        "model_version": "trained-v1",
        "opponent_response": {k: dict(v) for k, v in response_counts.items()},
        "opponent_lead": {k: dict(v) for k, v in lead_counts.items()},
    }
    with open(MODEL, "w", encoding="utf-8") as target:
        json.dump(model, target, sort_keys=True, indent=2)
    print("Wrote", MODEL)
    print("response buckets:", len(response_counts),
          "lead buckets:", len(lead_counts))


if __name__ == "__main__":
    main()
