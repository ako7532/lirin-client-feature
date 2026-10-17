#!/usr/bin/env python3
"""Offline analysis for manual_metin_queue.jsonl.

The report describes observed queue membership.  It intentionally does not
reinterpret observations as physical clicks, add attempts, spawns, kills, or
manual removals.
"""

import argparse
import json
import math
import statistics
from collections import Counter
from pathlib import Path


def percentile(values, percent):
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = (len(ordered) - 1) * (percent / 100.0)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return float(ordered[lower])
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def distribution(values):
    values = [float(value) for value in values]
    if not values:
        return {key: None for key in
                ("count", "min", "median", "mean", "p90", "p95", "p99", "max")}
    return {
        "count": len(values),
        "min": min(values),
        "median": statistics.median(values),
        "mean": statistics.mean(values),
        "p90": percentile(values, 90),
        "p95": percentile(values, 95),
        "p99": percentile(values, 99),
        "max": max(values),
    }


def read_jsonl(path):
    records = []
    parse_errors = []
    with Path(path).open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except Exception as exc:
                parse_errors.append({"line": line_number, "error": str(exc)})
    return records, parse_errors


def recorder_bucket(record):
    recorder = record.get("recorder") or {}
    if not recorder.get("valid"):
        return "unknown"
    enabled = "enabled" if recorder.get("recorder_enabled") else "disabled"
    foreground = "foreground" if recorder.get("app_active") else "background"
    return f"{enabled}_{foreground}"


def analyze(records, parse_errors=None):
    observations = [record for record in records
                    if record.get("event") == "queue_observation"]
    valid = [record for record in observations
             if (record.get("observer") or {}).get("valid")]
    changes = [record for record in records if record.get("event") == "queue_change"]
    starts = [record for record in records if record.get("event") == "session_start"]
    baselines = [record for record in records if record.get("event") == "queue_baseline"]

    intervals = [record.get("observation_interval_ms", 0) for record in observations
                 if record.get("observation_interval_ms", 0) > 0]
    coverage_gaps = [record.get("coverage_gap_ms", 0) for record in observations
                     if record.get("coverage_gap_ms", 0) > 0]
    additions = []
    departures = []
    batches = []
    reorder_count = 0
    simultaneous_count = 0
    for change in changes:
        added = list(change.get("newly_observed_queue_members") or [])
        removed = list(change.get("no_longer_observed_queue_members") or [])
        additions.extend(added)
        departures.extend(removed)
        if added:
            batches.append({
                "size": len(added),
                "vids": added,
                "bounded_after_tick_ms": change.get("bounded_after_tick_ms"),
                "bounded_at_or_before_tick_ms": change.get("bounded_at_or_before_tick_ms"),
                "session_id": change.get("session_id"),
            })
        if change.get("change_kind") == "reorder_only":
            reorder_count += 1
        if added and removed:
            simultaneous_count += 1

    by_session = {}
    occupancy_ms = Counter()
    occupancy_timeline = []
    vacancy_delays = []
    initial_additions = 0
    replenishment_additions = 0
    for record in valid:
        by_session.setdefault(record.get("session_id"), []).append(record)
        queue = record.get("queue") or {}
        occupancy_timeline.append({
            "session_id": record.get("session_id"),
            "observed_tick_ms": record.get("observed_tick_ms"),
            "utc": record.get("utc"),
            "count": queue.get("count"),
            "capacity": queue.get("capacity"),
        })
    for session_records in by_session.values():
        session_records.sort(key=lambda item: item.get("observed_tick_ms") or 0)
        reached_full = False
        vacancy_started = None
        previous = None
        for record in session_records:
            queue = record.get("queue") or {}
            count = int(queue.get("count") or 0)
            capacity = int(queue.get("capacity") or 0)
            now = record.get("observed_tick_ms")
            if previous is not None and now is not None:
                previous_queue = previous.get("queue") or {}
                previous_tick = previous.get("observed_tick_ms")
                duration = (max(0, now - previous_tick)
                            if previous_tick is not None else 0)
                previous_count = int(previous_queue.get("count") or 0)
                previous_capacity = int(previous_queue.get("capacity") or 0)
                occupancy_ms[str(previous_count)] += duration
                if previous_count == 0:
                    occupancy_ms["empty"] += duration
                if previous_capacity > 0 and previous_count >= previous_capacity:
                    occupancy_ms["full"] += duration
            added_count = len(record.get("newly_observed_queue_members") or [])
            if added_count:
                if reached_full:
                    replenishment_additions += added_count
                else:
                    initial_additions += added_count
                if vacancy_started is not None and now is not None:
                    vacancy_delays.append(max(0, now - vacancy_started))
                    vacancy_started = None
            if capacity > 0 and count >= capacity:
                reached_full = True
                vacancy_started = None
            elif reached_full and vacancy_started is None and now is not None:
                vacancy_started = now
            previous = record

    target_distances = []
    anchor_distances = []
    selected_match_count = 0
    enriched_additions = 0
    for change in changes:
        added = set(change.get("newly_observed_queue_members") or [])
        context = change.get("context") or {}
        selected = ((context.get("player") or {}).get("current_target_vid"))
        actors = context.get("actors") or []
        for actor in actors:
            if actor.get("vid") not in added:
                continue
            enriched_additions += 1
            if actor.get("player_distance") is not None:
                target_distances.append(actor["player_distance"])
            if actor.get("anchor_distance") is not None:
                anchor_distances.append(actor["anchor_distance"])
            if selected == actor.get("vid"):
                selected_match_count += 1

    recorder = {}
    for bucket in ("enabled_foreground", "enabled_background",
                   "disabled_foreground", "disabled_background", "unknown"):
        bucket_records = [record for record in valid if recorder_bucket(record) == bucket]
        bucket_additions = sum(len(record.get("newly_observed_queue_members") or [])
                               for record in bucket_records)
        elapsed_ms = sum(max(0, record.get("observation_interval_ms") or 0)
                         for record in bucket_records)
        recorder[bucket] = {
            "observations": len(bucket_records),
            "elapsed_ms": elapsed_ms,
            "newly_observed_members": bucket_additions,
            "rate_per_minute": (bucket_additions * 60000.0 / elapsed_ms
                                if elapsed_ms else None),
        }

    elapsed_ms = 0
    if valid:
        ticks = [record.get("observed_tick_ms") for record in valid
                 if record.get("observed_tick_ms") is not None]
        elapsed_ms = max(ticks) - min(ticks) if ticks else 0
    return {
        "interpretation": {
            "additions": "newly observed queue members, not add attempts or exact physical clicks",
            "departures": "no-longer-observed members, not proven kills or manual removals",
            "batches": "all members appearing between two valid observations share one bounded interval",
        },
        "runs": len(starts),
        "sessions": len({record.get("session_id") for record in baselines}),
        "observations": len(observations),
        "valid_observations": len(valid),
        "invalid_observations": len(observations) - len(valid),
        "elapsed_ms_between_valid_observations": elapsed_ms,
        "newly_observed_member_count": len(additions),
        "newly_observed_rate_per_minute": (len(additions) * 60000.0 / elapsed_ms
                                           if elapsed_ms else None),
        "departure_count": len(departures),
        "initial_filling_additions": initial_additions,
        "subsequent_replenishment_additions": replenishment_additions,
        "observed_batches": batches,
        "batch_size_distribution": distribution([item["size"] for item in batches]),
        "observation_interval_ms": distribution(intervals),
        "coverage_gap_ms": distribution(coverage_gaps),
        "reorder_only_changes": reorder_count,
        "simultaneous_addition_departure_changes": simultaneous_count,
        "occupancy_estimated_ms": dict(occupancy_ms),
        "occupancy_timeline": occupancy_timeline,
        "vacancy_to_next_observed_addition_ms": distribution(vacancy_delays),
        "target_selection": {
            "enriched_new_members": enriched_additions,
            "selected_target_matches_new_member": selected_match_count,
            "player_distance": distribution(target_distances),
            "anchor_distance": distribution(anchor_distances),
        },
        "recorder_app_comparison": recorder,
        "quality": {
            "parse_errors": parse_errors or [],
            "ambiguous_rebaseline_observations": sum(
                1 for record in valid if record.get("ambiguous_across_gap")),
            "reported_dropped_records": max(
                [record.get("dropped_records", 0) for record in records] or [0]),
            "older_failed_run_limitations": [
                "Compare timestamped Hunter additions with newly observed membership only.",
                "Older logs lacking raw authoritative snapshots cannot supply occupancy, removals, reorderings, bounded batches, or recorder state for every interval.",
                "Neither dataset proves a physical click time, an add attempt, a kill, or logout causality.",
            ],
        },
    }


def render_text(report):
    lines = [
        "Manual Metin queue observation report",
        f"Runs/sessions: {report['runs']}/{report['sessions']}",
        ("Observations: {observations} ({valid_observations} valid, "
         "{invalid_observations} invalid)").format(**report),
        ("Newly observed members: {0} ({1} initial filling, {2} subsequent replenishment)"
         .format(report["newly_observed_member_count"],
                 report["initial_filling_additions"],
                 report["subsequent_replenishment_additions"])),
        "Observed batches: {0}; departures: {1}; reorder-only: {2}".format(
            len(report["observed_batches"]), report["departure_count"],
            report["reorder_only_changes"]),
        "Observation gaps (ms): " + json.dumps(report["observation_interval_ms"], sort_keys=True),
        "Vacancy to next observed addition (ms): " + json.dumps(
            report["vacancy_to_next_observed_addition_ms"], sort_keys=True),
        "Estimated occupancy (ms): " + json.dumps(
            report["occupancy_estimated_ms"], sort_keys=True),
        "Recorder/app comparison: " + json.dumps(
            report["recorder_app_comparison"], sort_keys=True),
        "Limit: observations are bounded membership changes, not exact clicks/add attempts/kills.",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("jsonl", type=Path)
    parser.add_argument("--json", action="store_true", help="emit full JSON report")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    records, errors = read_jsonl(args.jsonl)
    report = analyze(records, errors)
    output = (json.dumps(report, indent=2, sort_keys=True) if args.json
              else render_text(report)) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
