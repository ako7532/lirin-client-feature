"""Passive JSONL observation of the authoritative Metin queue.

This module is deliberately Python-2.7-compatible because it is imported by
the embedded game runtime.  It owns no gameplay controls: its collaborators
are read-only snapshot/context functions and its only writes are its JSONL
file plus bounded in-memory buffering.
"""

from __future__ import print_function

import json
import os
import time

try:
    import hashlib
except ImportError:
    hashlib = None


SCHEMA_VERSION = 1
LOGGER_VERSION = 1
DEFAULT_POLL_MS = 100
DEFAULT_HEARTBEAT_MS = 1000
DEFAULT_FLUSH_MS = 1000
DEFAULT_MAX_BUFFERED_RECORDS = 128

try:
    INTEGER_TYPES = (int, long)
except NameError:
    INTEGER_TYPES = (int,)


def _utc_now():
    now = time.time()
    whole = int(now)
    millis = int((now - whole) * 1000.0)
    return "%s.%03dZ" % (time.strftime("%Y-%m-%dT%H:%M:%S",
                                       time.gmtime(whole)), millis)


def _sha256_file(path):
    if hashlib is None or not path or not os.path.isfile(path):
        return None
    digest = hashlib.sha256()
    handle = open(path, "rb")
    try:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    finally:
        handle.close()
    return digest.hexdigest()


def _ordered_delta(previous, current):
    previous_set = set(previous)
    current_set = set(current)
    added = [vid for vid in current if vid not in previous_set]
    removed = [vid for vid in previous if vid not in current_set]
    return added, removed


def _safe_json_value(value):
    if (value is None or isinstance(value, (bool, float, str)) or
            isinstance(value, INTEGER_TYPES)):
        return value
    try:
        unicode_type = unicode
    except NameError:
        unicode_type = str
    if isinstance(value, unicode_type):
        return value
    if isinstance(value, (list, tuple)):
        return [_safe_json_value(item) for item in value]
    if isinstance(value, dict):
        return dict((str(key), _safe_json_value(item))
                    for key, item in value.items())
    return repr(value)


class ManualQueueLogger(object):
    """Opt-in, update-thread-only queue observer.

    ``tick`` must be called from the game's existing Python update callback.
    It never sleeps and throttles the observer to ``poll_ms``.  The enable file
    is checked at most once per second so it can stop cleanly if removed.
    """

    def __init__(self, gateway, clock, log_path, enable_path, feature_version,
                 context_provider=None, metadata_path=None, poll_ms=DEFAULT_POLL_MS,
                 heartbeat_ms=DEFAULT_HEARTBEAT_MS, flush_ms=DEFAULT_FLUSH_MS,
                 max_buffered_records=DEFAULT_MAX_BUFFERED_RECORDS,
                 wall_clock=None, pid=None, report_error=None, file_open=None,
                 switch_reader=None):
        self.gateway = gateway
        self.clock = clock
        self.log_path = log_path
        self.enable_path = enable_path
        self.feature_version = int(feature_version)
        self.context_provider = context_provider or (lambda enrich, snap: {})
        self.metadata_path = metadata_path
        self.poll_ms = max(DEFAULT_POLL_MS, int(poll_ms))
        self.heartbeat_ms = max(1000, int(heartbeat_ms))
        self.flush_ms = max(250, int(flush_ms))
        self.max_buffered_records = max(8, int(max_buffered_records))
        self.wall_clock = wall_clock or _utc_now
        self.pid = int(os.getpid() if pid is None else pid)
        self.report_error = report_error or (lambda message: None)
        self.file_open = file_open or open
        self.switch_reader = switch_reader or (
            lambda path: os.path.isfile(path))
        self.active = False
        self.disabled_after_error = False
        self.run_id = None
        self.session_id = None
        self.session_index = 0
        self.last_switch_check_ms = None
        self.last_scheduled_ms = None
        self.last_valid = None
        self.last_valid_ms = None
        self.last_observer_valid = None
        self.last_heartbeat_ms = None
        self.last_flush_ms = None
        self.coverage_open = True
        self.observation_count = 0
        self.invalid_count = 0
        self.max_gap_ms = 0
        self.dropped_records = 0
        self.buffer = []
        self._metadata = None

    def _read_switch(self):
        try:
            return bool(self.switch_reader(self.enable_path))
        except Exception:
            return False

    def _read_metadata(self):
        if self._metadata is not None:
            return self._metadata
        metadata = {}
        if self.metadata_path and os.path.isfile(self.metadata_path):
            try:
                handle = open(self.metadata_path, "rb")
                try:
                    metadata = json.loads(handle.read().decode("utf-8"))
                finally:
                    handle.close()
            except Exception as exc:
                metadata = {"metadata_error": repr(exc)}
        script_path = os.path.join(os.path.dirname(self.log_path),
                                   "client_feature.py")
        active_marker = os.path.join(os.path.dirname(self.log_path),
                                     "client_feature_active.txt")
        dll_path = None
        try:
            marker = open(active_marker, "rb")
            try:
                dll_name = marker.read().decode("ascii", "replace").strip()
            finally:
                marker.close()
            if dll_name:
                dll_path = os.path.join(os.path.dirname(self.log_path), dll_name)
        except Exception:
            pass
        metadata.setdefault("staged_python_sha256", _sha256_file(script_path))
        metadata.setdefault("staged_dll_sha256", _sha256_file(dll_path))
        metadata.setdefault("staged_dll_name",
                            os.path.basename(dll_path) if dll_path else None)
        self._metadata = metadata
        return metadata

    def _base(self, event_type, now_ms):
        return {
            "schema_version": SCHEMA_VERSION,
            "logger_version": LOGGER_VERSION,
            "event": event_type,
            "run_id": self.run_id,
            "session_id": self.session_id,
            "pid": self.pid,
            "feature_version": self.feature_version,
            "observed_tick_ms": now_ms,
            "utc": self.wall_clock(),
        }

    def _append(self, record):
        if len(self.buffer) >= self.max_buffered_records:
            self.buffer.pop(0)
            self.dropped_records += 1
        self.buffer.append(_safe_json_value(record))

    def _fail(self, problem):
        self.active = False
        self.disabled_after_error = True
        self.buffer = []
        try:
            self.report_error("manual queue logger disabled: %s" % problem)
        except Exception:
            pass

    def flush(self, now_ms=None, force=False):
        if not self.buffer:
            return True
        if (not force and self.last_flush_ms is not None and now_ms is not None
                and now_ms - self.last_flush_ms < self.flush_ms
                and len(self.buffer) < self.max_buffered_records):
            return True
        records = self.buffer
        self.buffer = []
        try:
            handle = self.file_open(self.log_path, "ab")
            try:
                for record in records:
                    line = json.dumps(record, sort_keys=True,
                                      separators=(",", ":")) + "\n"
                    if not isinstance(line, bytes):
                        line = line.encode("utf-8")
                    handle.write(line)
                handle.flush()
            finally:
                handle.close()
            self.last_flush_ms = now_ms
            return True
        except Exception as exc:
            # Dropped writes are reported through the existing feature log/UI.
            # No gameplay method is called in response.
            self._fail("write failed (%d buffered records): %r" %
                       (len(records), exc))
            return False

    def _new_session(self, now_ms, reason, snap, uncertain):
        self.session_index += 1
        self.session_id = "%s-%d" % (self.run_id, self.session_index)
        record = self._base("queue_baseline", now_ms)
        record.update({
            "reason": reason,
            "uncertain_since_previous": bool(uncertain),
            "observer": self._observer_fields(snap),
            "queue": self._queue_fields(snap),
            "previous_valid_observed_tick_ms": None,
            "previous_valid_vids": None,
            "newly_observed_queue_members": [],
            "no_longer_observed_queue_members": [],
            "interpretation": "initial state; not newly added targets",
            "context": self._context(True, snap),
        })
        self._append(record)

    def start(self, now_ms):
        if self.active or self.disabled_after_error:
            return
        self.active = True
        self.run_id = "%d-%d-%d" % (
            self.pid, int(now_ms), int(time.time() * 1000000.0))
        self.session_id = None
        self.session_index = 0
        self.last_scheduled_ms = None
        self.last_valid = None
        self.last_valid_ms = None
        self.last_observer_valid = None
        self.last_heartbeat_ms = now_ms
        self.last_flush_ms = now_ms
        self.coverage_open = True
        self.observation_count = 0
        self.invalid_count = 0
        self.max_gap_ms = 0
        self.dropped_records = 0
        self.buffer = []
        record = self._base("session_start", now_ms)
        record.update({
            "observer_api_version": 1,
            "configuration": {
                "poll_ms": self.poll_ms,
                "heartbeat_ms": self.heartbeat_ms,
                "flush_ms": self.flush_ms,
                "max_buffered_records": self.max_buffered_records,
                "enable_path": self.enable_path,
                "log_path": self.log_path,
            },
            "runtime_metadata": self._read_metadata(),
            "measurement_limitations": {
                "membership_changes": "bounded observations, not physical click timestamps or add attempts",
                "queue_departure": "does not prove a kill or manual removal",
                "first_observed": "does not mean spawned",
                "input_events": "unavailable; no input hook or recorder routine is called",
                "click_duration": "unavailable",
                "movement_attack_state": "unavailable without a verified read-only getter",
                "actor_hp_dead_state": "unavailable without a verified read-only getter",
                "eligible_distance_rank": "unavailable; scanner snapshots do not store native admission for every candidate",
            },
            "context": self._context(True),
        })
        self._append(record)

    def stop(self, now_ms, reason="opt_out"):
        if not self.active:
            return
        record = self._base("session_stop", now_ms)
        record.update({
            "reason": reason,
            "observation_count": self.observation_count,
            "invalid_observation_count": self.invalid_count,
            "max_observation_gap_ms": self.max_gap_ms,
            "dropped_records": self.dropped_records,
        })
        self._append(record)
        self.flush(now_ms, force=True)
        self.active = False

    def _context(self, enrich, snap=None):
        try:
            value = self.context_provider(bool(enrich), snap)
            return _safe_json_value(value if isinstance(value, dict) else {})
        except Exception as exc:
            return {"valid": False, "error": repr(exc)}

    @staticmethod
    def _observer_fields(snap):
        return {
            "valid": bool(snap.get("valid")),
            "error": snap.get("error"),
            "api_version": snap.get("api_version"),
            "stock_binding_ok": bool(snap.get("stock_binding_ok")),
            "stock_binding_identity": (
                "verified_stock_MetinQueueAdd"
                if snap.get("stock_binding_ok") else
                "mismatch_or_unavailable"),
            "player_cookie_token": (str(snap.get("player_cookie"))
                                    if snap.get("player_cookie") is not None
                                    else None),
        }

    @staticmethod
    def _queue_fields(snap):
        vids = [int(value) for value in (snap.get("vids") or ())]
        return {
            "enabled": bool(snap.get("enabled")),
            "capacity": int(snap.get("max_size") or 0),
            "count": len(vids),
            "ordered_vids": vids,
        }

    def _audit(self):
        status = self.gateway.audit_status()
        if not status.get("valid"):
            return {
                "valid": False,
                "error": status.get("error") or "audit status unavailable",
                "recorder_enabled": None,
                "sample_ms": None,
                "flush_ms": None,
                "app_active": None,
                "observed_tick_ms": status.get("observed_tick_ms"),
            }
        return {
            "valid": True,
            "error": None,
            "recorder_enabled": bool(status.get("recorder_enabled")),
            "sample_ms": int(status.get("sample_ms") or 0),
            "flush_ms": int(status.get("flush_ms") or 0),
            "app_active": bool(status.get("app_active")),
            "observed_tick_ms": status.get("observed_tick_ms"),
        }

    def _observe(self, now_ms, interval_ms):
        snap = self.gateway.snapshot()
        self.observation_count += 1
        coverage_gap_ms = max(0, interval_ms - self.poll_ms)
        if interval_ms > self.max_gap_ms:
            self.max_gap_ms = interval_ms
        record = self._base("queue_observation", now_ms)
        record.update({
            "observation_number": self.observation_count,
            "observation_interval_ms": interval_ms,
            "coverage_gap_ms": coverage_gap_ms,
            "coverage_contiguous": coverage_gap_ms <= self.poll_ms,
            "observer": self._observer_fields(snap),
            "recorder": self._audit(),
        })
        observer_valid = bool(snap.get("valid"))
        if (self.last_observer_valid is None or
                observer_valid != self.last_observer_valid):
            transition = self._base("observer_validity_transition", now_ms)
            transition.update({
                "previous_valid": self.last_observer_valid,
                "current_valid": observer_valid,
                "error": snap.get("error"),
                "observer": self._observer_fields(snap),
            })
            self._append(transition)
        self.last_observer_valid = observer_valid
        if not snap.get("valid"):
            self.invalid_count += 1
            self.coverage_open = True
            record.update({
                "queue": None,
                "previous_valid_observed_tick_ms": self.last_valid_ms,
                "previous_valid_vids": (list(self.last_valid.get("vids", ()))
                                        if self.last_valid else None),
                "newly_observed_queue_members": None,
                "no_longer_observed_queue_members": None,
                "change_kind": "invalid",
                "context": self._context(False, snap),
            })
            self._append(record)
            return

        current = tuple(int(value) for value in (snap.get("vids") or ()))
        context = self._context(False, snap)
        epoch = context.get("gameplay_epoch")
        previous_context = ((self.last_valid or {}).get("_context") or {})
        player_changed = bool(
            self.last_valid is not None and
            snap.get("player_cookie") != self.last_valid.get("player_cookie"))
        epoch_changed = bool(
            self.last_valid is not None and
            epoch != previous_context.get("gameplay_epoch"))
        needs_baseline = (self.last_valid is None or self.coverage_open or
                          player_changed or epoch_changed)
        if needs_baseline:
            reason = "initial_valid_observation"
            if player_changed:
                reason = "player_session_changed"
            elif epoch_changed:
                reason = "gameplay_epoch_changed"
            elif self.last_valid is not None and self.coverage_open:
                reason = "coverage_reestablished"
            self._new_session(now_ms, reason, snap,
                              self.last_valid is not None)
            added, removed = [], []
            change_kind = "baseline"
            enrich = True
        else:
            previous = tuple(self.last_valid.get("vids") or ())
            added, removed = _ordered_delta(previous, current)
            reorder = not added and not removed and previous != current
            if added and removed:
                change_kind = "addition_and_departure"
            elif added:
                change_kind = "addition"
            elif removed:
                change_kind = "departure"
            elif reorder:
                change_kind = "reorder_only"
            else:
                change_kind = "unchanged"
            enrich = change_kind != "unchanged"

        if enrich:
            context = self._context(True, snap)
        record.update({
            "session_id": self.session_id,
            "queue": self._queue_fields(snap),
            "previous_valid_observed_tick_ms": (None if needs_baseline
                                                else self.last_valid_ms),
            "previous_valid_vids": (None if needs_baseline
                                    else list(self.last_valid.get("vids") or ())),
            "change_interval_start_tick_ms": (None if needs_baseline
                                               else self.last_valid_ms),
            "change_interval_end_tick_ms": now_ms,
            "newly_observed_queue_members": added,
            "no_longer_observed_queue_members": removed,
            "change_kind": change_kind,
            "ambiguous_across_gap": bool(needs_baseline and
                                         self.last_valid is not None),
            "context": context,
        })
        self._append(record)
        if not needs_baseline and change_kind != "unchanged":
            summary = self._base("queue_change", now_ms)
            summary.update({
                "change_kind": change_kind,
                "bounded_after_tick_ms": self.last_valid_ms,
                "bounded_at_or_before_tick_ms": now_ms,
                "previous_ordered_vids": list(self.last_valid.get("vids") or ()),
                "current_ordered_vids": list(current),
                "newly_observed_queue_members": added,
                "no_longer_observed_queue_members": removed,
                "interpretation": "observed membership/order change; not an exact click, add attempt, kill, or manual removal",
                "context": context,
            })
            self._append(summary)
        saved = dict(snap)
        saved["vids"] = current
        saved["_context"] = context
        self.last_valid = saved
        self.last_valid_ms = now_ms
        self.coverage_open = False

    def tick(self, now_ms=None):
        if now_ms is None:
            try:
                now_ms = int(self.clock())
            except Exception:
                return
        now_ms = int(now_ms)
        if (self.last_switch_check_ms is None or
                now_ms - self.last_switch_check_ms >= 1000):
            self.last_switch_check_ms = now_ms
            enabled = self._read_switch()
            if enabled and not self.active and not self.disabled_after_error:
                self.start(now_ms)
            elif not enabled and self.active:
                self.stop(now_ms, "enable_file_removed")
                return
        if not self.active:
            return
        if (self.last_scheduled_ms is not None and
                now_ms - self.last_scheduled_ms < self.poll_ms):
            return
        interval_ms = (0 if self.last_scheduled_ms is None
                       else max(0, now_ms - self.last_scheduled_ms))
        self.last_scheduled_ms = now_ms
        self._observe(now_ms, interval_ms)
        if not self.active:
            return
        if (self.last_heartbeat_ms is None or
                now_ms - self.last_heartbeat_ms >= self.heartbeat_ms):
            heartbeat = self._base("heartbeat", now_ms)
            heartbeat.update({
                "observation_count": self.observation_count,
                "invalid_observation_count": self.invalid_count,
                "max_observation_gap_ms": self.max_gap_ms,
                "dropped_records": self.dropped_records,
                "last_valid_observed_tick_ms": self.last_valid_ms,
            })
            self._append(heartbeat)
            self.last_heartbeat_ms = now_ms
        self.flush(now_ms, force=False)
