"""Focused local checks for passive manual queue logging and analysis."""

import importlib.util
import json
import tempfile
from pathlib import Path

from manual_queue_logging import ManualQueueLogger


class FakeGateway:
    def __init__(self, snapshots, audit=None):
        self.snapshots = list(snapshots)
        self.audit = audit or {
            "valid": True, "error": None, "observed_tick_ms": 0,
            "recorder_enabled": 0, "sample_ms": 40,
            "flush_ms": 1000, "app_active": 1,
        }
        self.snapshot_calls = 0
        self.audit_calls = 0
        self.mutation_calls = []

    def snapshot(self):
        self.snapshot_calls += 1
        if not self.snapshots:
            raise AssertionError("unexpected observer poll")
        return self.snapshots.pop(0)

    def audit_status(self):
        self.audit_calls += 1
        return dict(self.audit)

    def add_once(self, *args):
        self.mutation_calls.append(("add", args))
        raise AssertionError("logger called a gameplay mutation")

    def remove_once(self, *args):
        self.mutation_calls.append(("remove", args))
        raise AssertionError("logger called a gameplay mutation")

    def set_enabled_once(self, *args):
        self.mutation_calls.append(("set_enabled", args))
        raise AssertionError("logger called a gameplay mutation")


def snap(vids=(), valid=True, cookie=100, enabled=True, capacity=5,
         error=None):
    return {
        "api_version": 1,
        "valid": valid,
        "error": error,
        "player_cookie": cookie,
        "vids": tuple(vids),
        "enabled": enabled,
        "max_size": capacity,
        "observed_tick_ms": 0,
        "stock_binding_ok": True,
    }


def read_records(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def make_logger(directory, gateway, switch, epoch, context_calls=None,
                report_errors=None, file_open=None):
    context_calls = context_calls if context_calls is not None else []
    report_errors = report_errors if report_errors is not None else []

    def context(enrich, observed):
        context_calls.append((enrich, observed))
        return {
            "gameplay_epoch": epoch[0],
            "automation": {
                "hunter_toggle_on": False,
                "hunter_automatic_additions_enabled": False,
                "hunter_state": "OFF",
            },
            "actors": ([{"vid": value, "player_distance": value * 10} for value in
                        ((observed or {}).get("vids") or ())]
                       if enrich else None),
        }

    return ManualQueueLogger(
        gateway=gateway,
        clock=lambda: 0,
        log_path=str(Path(directory) / "manual_metin_queue.jsonl"),
        enable_path=str(Path(directory) / "manual_queue_logging.enabled"),
        feature_version=47,
        context_provider=context,
        poll_ms=100,
        heartbeat_ms=1000,
        flush_ms=250,
        max_buffered_records=32,
        wall_clock=lambda: "2026-10-17T12:00:00.000000Z",
        pid=1234,
        report_error=report_errors.append,
        file_open=file_open,
        switch_reader=lambda path: switch[0],
    )


def test_change_semantics_and_safety():
    sequence = [
        snap([]),                    # empty baseline
        snap([1]),                   # one addition
        snap([1, 2, 3]),             # multiple additions, one observed batch
        snap([2, 3, 1]),             # reorder only
        snap([2, 3, 4]),             # add/remove, unchanged total size
        snap([2, 3]),                # removal
        snap(valid=False, error="unreadable"),
        snap([9]),                   # baseline after coverage gap
        snap([10], cookie=200),      # baseline after player/session change
        snap([10], cookie=200),      # baseline after epoch change
        snap([10], cookie=200),      # unchanged + heartbeat
    ]
    gateway = FakeGateway(sequence)
    switch = [True]
    epoch = [1]
    calls = []
    with tempfile.TemporaryDirectory() as directory:
        logger = make_logger(directory, gateway, switch, epoch, calls)
        for tick in (0, 50, 100, 200, 300, 400, 500, 800, 900):
            logger.tick(tick)
        logger.tick(1000)
        epoch[0] = 2
        logger.tick(1100)
        switch[0] = False
        logger.tick(2000)
        records = read_records(Path(directory) / "manual_metin_queue.jsonl")

    observations = [item for item in records if item["event"] == "queue_observation"]
    changes = [item for item in records if item["event"] == "queue_change"]
    baselines = [item for item in records if item["event"] == "queue_baseline"]
    assert gateway.snapshot_calls == 10  # tick 50 was throttled
    assert gateway.mutation_calls == []
    assert observations[0]["queue"]["ordered_vids"] == []
    assert observations[0]["newly_observed_queue_members"] == []
    assert baselines[0]["interpretation"] == "initial state; not newly added targets"
    assert [item["change_kind"] for item in changes[:5]] == [
        "addition", "addition", "reorder_only",
        "addition_and_departure", "departure",
    ]
    assert changes[1]["newly_observed_queue_members"] == [2, 3]
    assert changes[1]["bounded_after_tick_ms"] == 100
    assert changes[1]["bounded_at_or_before_tick_ms"] == 200
    simultaneous = changes[3]
    assert simultaneous["newly_observed_queue_members"] == [4]
    assert simultaneous["no_longer_observed_queue_members"] == [1]
    invalid = next(item for item in observations if item["change_kind"] == "invalid")
    assert invalid["queue"] is None  # invalid is never converted to empty
    rebaseline = [item for item in observations if item["change_kind"] == "baseline"]
    assert len(rebaseline) == 4  # initial, coverage, player token, epoch
    assert all(item["newly_observed_queue_members"] == [] for item in rebaseline)
    assert any(item["coverage_gap_ms"] == 200 for item in observations)
    assert all(not (item.get("context", {}).get("automation", {})
                    .get("hunter_automatic_additions_enabled"))
               for item in observations)
    assert any(item["event"] == "heartbeat" for item in records)
    assert records[-1]["event"] == "session_stop"
    assert records[-1]["reason"] == "enable_file_removed"
    # Enrichment only occurs at session start/baseline/change, not every poll.
    assert any(enrich for enrich, _ in calls)
    assert any(not enrich for enrich, _ in calls)


def test_populated_baseline_and_recorder_unknown():
    gateway = FakeGateway(
        [snap([7, 8])],
        audit={"valid": False, "error": "audit unavailable",
               "observed_tick_ms": 0},
    )
    switch = [True]
    with tempfile.TemporaryDirectory() as directory:
        logger = make_logger(directory, gateway, switch, [4])
        logger.tick(0)
        logger.stop(1, "test_complete")
        records = read_records(Path(directory) / "manual_metin_queue.jsonl")
    observation = next(item for item in records
                       if item["event"] == "queue_observation")
    assert observation["queue"]["ordered_vids"] == [7, 8]
    assert observation["newly_observed_queue_members"] == []
    assert observation["recorder"]["valid"] is False
    assert observation["recorder"]["recorder_enabled"] is None


def test_logging_failure_disables_logger_only():
    errors = []

    def broken_open(path, mode):
        raise OSError("disk unavailable")

    gateway = FakeGateway([snap([])])
    with tempfile.TemporaryDirectory() as directory:
        logger = make_logger(directory, gateway, [True], [1],
                             report_errors=errors, file_open=broken_open)
        logger.tick(0)
        logger.flush(300, force=True)
    assert not logger.active
    assert logger.disabled_after_error
    assert gateway.mutation_calls == []
    assert errors and "manual queue logger disabled" in errors[0]


def test_offline_analysis():
    analyzer_path = Path(__file__).with_name("scripts") / "analyze_manual_metin_queue.py"
    spec = importlib.util.spec_from_file_location("manual_queue_analyzer", analyzer_path)
    analyzer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(analyzer)
    records = [
        {"event": "session_start", "run_id": "r"},
        {"event": "queue_baseline", "session_id": "s"},
        {"event": "queue_observation", "session_id": "s",
         "observed_tick_ms": 0, "observation_interval_ms": 0,
         "coverage_gap_ms": 0, "observer": {"valid": True},
         "queue": {"count": 0, "capacity": 2},
         "newly_observed_queue_members": [],
         "recorder": {"valid": True, "recorder_enabled": False,
                      "app_active": True}},
        {"event": "queue_observation", "session_id": "s",
         "observed_tick_ms": 100, "observation_interval_ms": 100,
         "coverage_gap_ms": 0, "observer": {"valid": True},
         "queue": {"count": 2, "capacity": 2},
         "newly_observed_queue_members": [1, 2],
         "recorder": {"valid": True, "recorder_enabled": False,
                      "app_active": True}},
        {"event": "queue_change", "session_id": "s",
         "change_kind": "addition", "newly_observed_queue_members": [1, 2],
         "no_longer_observed_queue_members": [],
         "bounded_after_tick_ms": 0, "bounded_at_or_before_tick_ms": 100,
         "context": {"player": {"current_target_vid": 1},
                     "actors": [{"vid": 1, "player_distance": 50,
                                  "anchor_distance": 60},
                                 {"vid": 2, "player_distance": 70,
                                  "anchor_distance": 80}]}},
        {"event": "queue_observation", "session_id": "s",
         "observed_tick_ms": 200, "observation_interval_ms": 100,
         "coverage_gap_ms": 0, "observer": {"valid": True},
         "queue": {"count": 1, "capacity": 2},
         "newly_observed_queue_members": [],
         "recorder": {"valid": False}},
        {"event": "queue_observation", "session_id": "s",
         "observed_tick_ms": 300, "observation_interval_ms": 100,
         "coverage_gap_ms": 0, "observer": {"valid": True},
         "queue": {"count": 2, "capacity": 2},
         "newly_observed_queue_members": [3],
         "recorder": {"valid": True, "recorder_enabled": True,
                      "app_active": False}},
        {"event": "queue_change", "session_id": "s",
         "change_kind": "addition", "newly_observed_queue_members": [3],
         "no_longer_observed_queue_members": [],
         "bounded_after_tick_ms": 200, "bounded_at_or_before_tick_ms": 300,
         "context": {"player": {"current_target_vid": 0}, "actors": []}},
    ]
    report = analyzer.analyze(records)
    assert report["newly_observed_member_count"] == 3
    assert report["initial_filling_additions"] == 2
    assert report["subsequent_replenishment_additions"] == 1
    assert report["batch_size_distribution"]["median"] == 1.5
    assert report["occupancy_estimated_ms"]["empty"] == 100
    assert report["occupancy_estimated_ms"]["full"] == 100
    assert report["vacancy_to_next_observed_addition_ms"]["median"] == 100
    assert report["recorder_app_comparison"]["enabled_background"][
        "newly_observed_members"] == 1


if __name__ == "__main__":
    test_change_semantics_and_safety()
    test_populated_baseline_and_recorder_unknown()
    test_logging_failure_disables_logger_only()
    test_offline_analysis()
    print("Manual queue logging local checks: OK")
