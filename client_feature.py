"""In-game metin radius scanner for Lirin's embedded Python 2.7 runtime."""

import __main__
import gc
import json
import math
import os
import random
import sys
import time
import traceback

import app
import background
import chr
import net
import nonplayer
import player
import ui
import wndMgr

try:
    INTEGER_TYPES = (int, long)
except NameError:
    INTEGER_TYPES = (int,)


# execfile preserves the real script filename on the executing frame even
# when the embedded __main__ module has no reliable __file__ value.
DIRECTORY = os.path.dirname(os.path.abspath(sys._getframe().f_code.co_filename))
_MANUAL_QUEUE_MODULE_PATH = os.path.join(DIRECTORY, "manual_queue_logging.py")
_MANUAL_QUEUE_BOOTSTRAP_ERROR = os.path.join(
    DIRECTORY, "manual_queue_bootstrap_error.log")
try:
    if not os.path.isfile(_MANUAL_QUEUE_MODULE_PATH):
        import manual_queue_logging as _manual_queue_logging
        ManualQueueLogger = _manual_queue_logging.ManualQueueLogger
    else:
        _manual_queue_namespace = {
            "__file__": _MANUAL_QUEUE_MODULE_PATH,
            "__name__": "_lirin_manual_queue_logging",
        }
        try:
            execfile
        except NameError:
            _manual_queue_source = open(_MANUAL_QUEUE_MODULE_PATH, "rb").read()
            exec(compile(_manual_queue_source, _MANUAL_QUEUE_MODULE_PATH, "exec"),
                 _manual_queue_namespace)
        else:
            execfile(_MANUAL_QUEUE_MODULE_PATH, _manual_queue_namespace)
        ManualQueueLogger = _manual_queue_namespace["ManualQueueLogger"]
except Exception:
    # This path runs before the ordinary feature logger exists. Keep bootstrap
    # failures visible beside the staged script, then preserve the exception so
    # the loader correctly reports Python-call failure.
    try:
        _bootstrap_handle = open(_MANUAL_QUEUE_BOOTSTRAP_ERROR, "a")
        try:
            _bootstrap_handle.write("%s\n" % traceback.format_exc())
        finally:
            _bootstrap_handle.close()
    except Exception:
        pass
    raise
SNAPSHOT = os.path.join(DIRECTORY, "client_feature_vids.txt")
LOG = os.path.join(DIRECTORY, "metin_scanner.log")
CONFIG = os.path.join(DIRECTORY, "client_feature_config.txt")
MANUAL_QUEUE_LOG = os.path.join(DIRECTORY, "manual_metin_queue.jsonl")
MANUAL_QUEUE_ENABLE = os.path.join(DIRECTORY, "manual_queue_logging.enabled")
MANUAL_QUEUE_METADATA = os.path.join(DIRECTORY, "manual_queue_runtime_metadata.json")
RECORDER_PAIR_MODE = os.path.join(DIRECTORY, "hunter_recorder_pair.mode.txt")
MIN_RADIUS = 100
MAX_RADIUS = 10000
DEFAULT_RADIUS = 2500
FEATURE_VERSION = 52
HUNTER_LIMIT = 5
PRIORITY_EVENT_METIN_NAME = "legendary metinstone"
REACTION_POLL_SECONDS = 0.05
REACTION_DISCOVERY_SECONDS = 5.0
REACTION_SAFETY_POLL_SECONDS = 0.25
REACTION_SAFETY_DISCOVERY_SECONDS = 1.0
REACTION_CLICK_DELAY_MIN = 0.30
REACTION_CLICK_DELAY_MAX = 0.99
REACTION_CLICK_DELAY_JITTER = 0.025
# Thirty-seven clean manual samples from four local recorder rounds. Samples
# with a wrong click were excluded because this solver never clicks a wrong
# slot; a small jitter prevents exact replay of a recorded millisecond value.
REACTION_CLICK_DELAY_SAMPLES = (
    0.305, 0.404, 0.414, 0.421, 0.429, 0.430, 0.444, 0.451, 0.455,
    0.479, 0.480, 0.482, 0.484, 0.498, 0.505, 0.506, 0.507, 0.513,
    0.522, 0.530, 0.537, 0.538, 0.538, 0.546, 0.548, 0.567, 0.588,
    0.591, 0.597, 0.600, 0.601, 0.626, 0.656, 0.660, 0.756, 0.760,
    0.984,
)
PLAYER_POLL_SECONDS = 0.1
BOSS_TIMER_POLL_SECONDS = 0.5
BOSS_ACTIVE_POLL_SECONDS = 0.2
BOSS_LOAD_SETTLE_SECONDS = 1.0
BOSS_ABSENCE_GRACE_SECONDS = 3.0
BOSS_SPAWN_GRACE_SECONDS = 30.0
BOSS_KILL_CONFIRM_SECONDS = 1.5
BOSS_COMBAT_TIMEOUT_SECONDS = 90.0
BOSS_CHANNEL_TIMEOUT_SECONDS = 35.0
BOSS_RETURN_DISTANCE = 120
BOSS_RETURN_STALL_SECONDS = 3.0
BOSS_RETURN_PROGRESS_DISTANCE = 25
YINYANG_DUEL_POLL_SECONDS = 1.0
YINYANG_DUEL_RESULT_CLOSE_DELAY = 1.5
YINYANG_DUEL_ATTEMPTS_PER_DAY = 8
# Reverse-engineered candidates for the end-of-duel result-screen continue
# handler. The real member name is unverified against the current game build;
# `duel_result_continue_member` also discovers any callable result/continue
# member as a fallback, and `_DuelCloseResult` falls back to `Close()`.
YINYANG_DUEL_RESULT_CONTINUE_MEMBERS = (
    "_YinYangDuelWindow__OnResultContinue",
    "_YinYangDuelWindow__OnResultClicked",
    "_YinYangDuelWindow__OnClickResult",
    "_YinYangDuelWindow__OnConfirm",
    "_YinYangDuelWindow__OnOk",
)
YINYANG_DUEL_HISTORY_JSONL = os.path.join(DIRECTORY, "yin_yang_duel_history.jsonl")
YINYANG_DUEL_HISTORY_SCHEMA = 1

# --- Twin Souls (YinYangMemory / Pexeso) ---
# The client module `uiyinyangmemory` exposes YinYangMemoryWindow and MemoryCard.
# The winning tactic is deterministic perfect memory: remember every
# server-confirmed face, complete known pairs, otherwise reveal an unseen cell.
# The client is authoritative; the controller only learns faces the client
# reveals and waits for server/animation transitions before acting again.
TWIN_SOULS_IDLE_POLL_SECONDS = 1.0
TWIN_SOULS_ACTIVE_POLL_SECONDS = 0.15
TWIN_SOULS_DISCOVERY_SECONDS = 1.0
TWIN_SOULS_MIN_ACTION_GAP = 0.05
TWIN_SOULS_ACK_TIMEOUT = 3.0
TWIN_SOULS_ERROR_RETRY_SECONDS = 10.0
TWIN_SOULS_HISTORY_JSONL = os.path.join(DIRECTORY, "twin_souls_history.jsonl")
TWIN_SOULS_HISTORY_SCHEMA = 1

TWIN_SOULS_STATE_IDLE = "idle"
TWIN_SOULS_STATE_PLAYING = "playing"
TWIN_SOULS_STATE_FINISHING = "finishing"
TWIN_SOULS_STATE_UNKNOWN = "unknown"

TWIN_SOULS_MODE_KNOWN_MATE = "known_mate"
TWIN_SOULS_MODE_COMPLETE_PAIR = "complete_pair"
TWIN_SOULS_MODE_EXPLORE = "explore"
TWIN_SOULS_MODE_WAIT = "wait"

BOSS_IDLE = "idle"
BOSS_WAIT_TIMER = "wait_timer"
BOSS_WAIT_SPAWN = "wait_spawn"
BOSS_FIND = "find"
BOSS_ATTACK = "attack"
BOSS_CHANGE_CHANNEL = "change_channel"
BOSS_WAIT_CHANNEL = "wait_channel"
BOSS_SETTLE_CHANNEL = "settle_channel"
BOSS_RETURN_POSITION = "return_position"
BOSS_SWEEP_BUSY_STATES = (BOSS_WAIT_SPAWN, BOSS_FIND, BOSS_ATTACK,
                          BOSS_CHANGE_CHANNEL, BOSS_WAIT_CHANNEL,
                          BOSS_SETTLE_CHANNEL, BOSS_RETURN_POSITION)

PHASE_LOADING = 4
PHASE_GAME = 5


def ascii_text(value):
    if not isinstance(value, (str, unicode)):
        value = repr(value)
    return "".join("%c" % ord(ch) if 32 <= ord(ch) < 127 else "?" for ch in value)


def next_reaction_click_delay():
    delay = (random.choice(REACTION_CLICK_DELAY_SAMPLES) +
             random.uniform(-REACTION_CLICK_DELAY_JITTER,
                            REACTION_CLICK_DELAY_JITTER))
    return max(REACTION_CLICK_DELAY_MIN,
               min(REACTION_CLICK_DELAY_MAX, delay))


def get_hunter_observer():
    """Return the read-only native observer module, or None when unavailable.

    The loader registers `_lirin_hunter_native` (API version 1) before running
    this script.  Its absence is not a silent empty queue: the gateway reports
    `valid=False` and Hunter stays unavailable."""
    try:
        import _lirin_hunter_native
    except ImportError:
        return None
    return _lirin_hunter_native


def hunter_now_ms():
    """Monotonic clock backed by the observer's GetTickCount64.  None when the
    observer (and therefore the monotonic clock) is unavailable."""
    observer = get_hunter_observer()
    if observer is None:
        return None
    try:
        return int(observer.now_ms())
    except Exception:
        return None


def recorder_pair_experiment_enabled():
    """Explicit startup-only opt-in. Missing/invalid mode is OFF."""
    try:
        with open(RECORDER_PAIR_MODE, "rb") as source:
            return source.read(32).strip() == b"on"
    except IOError:
        return False


def get_recorder_pair_experiment():
    """Separate writer module; the native observer remains read-only."""
    try:
        import _lirin_recorder_pair_experiment
    except ImportError:
        return None
    return _lirin_recorder_pair_experiment


class HunterQueueGateway(object):
    """Synchronous facade over the read-only observer and the stock `player`
    bindings.  Every mutation runs synchronously on the update thread; deadlines
    bound subsequent observation, never the duration of a native call.  No
    background threads or blocking sleeps live here."""

    ALREADY_PRESENT = "ALREADY_PRESENT"
    ADDED = "ADDED"
    REJECTED_PRECALL = "REJECTED_PRECALL"
    REJECTED_NATIVE = "REJECTED_NATIVE"
    REMOVED = "REMOVED"
    ALREADY_ABSENT = "ALREADY_ABSENT"
    UNKNOWN = "UNKNOWN"
    CANCELLED_PRECALL = "CANCELLED_PRECALL"

    def __init__(self, observer, player_module, clock=None,
                 recorder_pair_enabled=False, recorder_pair=None, log=None):
        self._observer = observer
        self._player = player_module
        self._clock = clock if clock is not None else hunter_now_ms
        self._recorder_pair_enabled = bool(recorder_pair_enabled)
        self._recorder_pair = recorder_pair
        self._experiment_log = log or (lambda message: None)
        self.input_experiment_error = None

    def _pair_log(self, message):
        # Logging must not interrupt the stock call or its finally block.
        try:
            self._experiment_log(message)
        except Exception:
            pass

    def _pair_failure(self, request, message):
        self.input_experiment_error = message
        request["recorder_pair_error"] = message
        self._pair_log("recorder pair experiment HALTED: %s; no automatic retry" %
                       message)

    def _pair_begin(self, request, vid):
        # Mark BEFORE calling: an exception can follow an uncertain append.
        request["recorder_pair_attempted"] = True
        try:
            status = self._recorder_pair.begin_queue_add(vid)
        except Exception as exc:
            self._pair_failure(request, "down outcome unknown: %s" % ascii_text(exc))
            return None
        request["recorder_pair_begin_status"] = status
        self._pair_log("recorder pair VID %d down status=%s (0=disabled, 1=producer returned)" %
                       (vid, status))
        if status not in (0, 1):
            self._pair_failure(request, "down rejected/unknown status=%s" % status)
            return None
        return status == 1

    def _pair_end(self, request, vid):
        try:
            status = self._recorder_pair.end_queue_add(vid)
        except Exception as exc:
            self._pair_failure(request, "up outcome unknown: %s" % ascii_text(exc))
            return
        request["recorder_pair_end_status"] = status
        self._pair_log("recorder pair VID %d up status=%s (1=producer returned)" %
                       (vid, status))
        if status != 1:
            self._pair_failure(request, "up rejected/unknown status=%s" % status)

    def observer_available(self):
        return self._observer is not None

    def now_ms(self):
        clock = self._clock
        if clock is None:
            return None
        try:
            return int(clock())
        except Exception:
            return None

    def snapshot(self):
        """Validated authoritative snapshot dict (see section 3.2)."""
        base = {
            "api_version": 1,
            "valid": False,
            "error": "observer unavailable",
            "player_cookie": None,
            "vids": (),
            "enabled": False,
            "max_size": 0,
            "observed_tick_ms": None,
            "stock_binding_ok": False,
        }
        if self._observer is None:
            return base
        try:
            snap = self._observer.snapshot()
        except Exception as exc:
            base["error"] = "observer raised: %s" % ascii_text(exc)
            return base
        for key in base:
            if key in snap:
                base[key] = snap[key]
        base["vids"] = tuple(int(v) for v in (snap.get("vids") or ()))
        try:
            stock_max = int(self._player.MetinQueueGetMaxSize())
            if stock_max > 0:
                base["max_size"] = stock_max
        except Exception:
            pass
        if base.get("max_size") is None or int(base["max_size"] or 0) <= 0:
            base["max_size"] = 0
        return base

    def admission(self, vid):
        """Full native queue eligibility for a VID (read-only)."""
        if self._observer is None:
            return {"valid": False, "eligible": False,
                    "reason": "observer unavailable", "player_cookie": None}
        try:
            return self._observer.admission(int(vid))
        except Exception as exc:
            return {"valid": False, "eligible": False,
                    "reason": "admission raised: %s" % ascii_text(exc),
                    "player_cookie": None}

    def audit_status(self):
        """Read-only effective recorder/app-active status (section 3.3)."""
        if self._observer is None:
            return {"valid": False, "error": "observer unavailable",
                    "observed_tick_ms": None, "recorder_enabled": 0,
                    "sample_ms": 0, "flush_ms": 0, "app_active": 0}
        try:
            return self._observer.audit_status()
        except Exception as exc:
            return {"valid": False, "error": "audit raised: %s" % ascii_text(exc),
                    "observed_tick_ms": None, "recorder_enabled": 0,
                    "sample_ms": 0, "flush_ms": 0, "app_active": 0}

    def _dispatch_precheck(self, request):
        """Fresh dispatch-time safety contract shared by add/remove.

        Returns (pre, problem) where problem is None when safe to dispatch, or an
        outcome string to return without mutating.  Always uses a fresh
        authoritative snapshot; a cached pre-snapshot is never trusted."""
        if request.get("dispatched"):
            return None, self.CANCELLED_PRECALL
        pre = self.snapshot()
        request["pre_snapshot"] = pre
        if not pre.get("valid"):
            return pre, self.UNKNOWN
        if not pre.get("stock_binding_ok"):
            return pre, self.REJECTED_PRECALL
        if pre.get("player_cookie") != request.get("player_cookie"):
            return pre, self.CANCELLED_PRECALL
        return pre, None

    def add_once(self, request):
        """One stock `player.MetinQueueAdd(vid)` under the full dispatch-time
        contract.  Outcome is derived from authoritative membership, never a
        truthy return alone.  A request already dispatched never executes again."""
        vid = int(request["vid"])
        if request.get("recorder_pair_attempted"):
            return self.CANCELLED_PRECALL
        if self.input_experiment_error:
            return self.REJECTED_PRECALL
        pre, problem = self._dispatch_precheck(request)
        if problem is not None:
            return problem
        if vid in pre["vids"]:
            return self.ALREADY_PRESENT
        admission = self.admission(vid)
        if not admission.get("valid"):
            return self.UNKNOWN
        if not admission.get("eligible"):
            return self.REJECTED_PRECALL
        pair_started = False
        if self._recorder_pair_enabled:
            if self._recorder_pair is None:
                self._pair_failure(request, "native experiment module unavailable")
                return self.REJECTED_PRECALL
            pair_started = self._pair_begin(request, vid)
            if pair_started is None:
                return self.REJECTED_PRECALL
        raw = None
        try:
            if pair_started:
                # Recording can flush a full native sample buffer. Recheck
                # identity/membership before the one queue mutation afterward.
                checked = self.snapshot()
                if (not checked.get("valid") or
                        not checked.get("stock_binding_ok") or
                        checked.get("player_cookie") != pre.get("player_cookie")):
                    self._pair_failure(request, "identity unavailable/changed after down")
                    return self.REJECTED_PRECALL
                if vid in checked["vids"]:
                    return self.ALREADY_PRESENT
            request["dispatched"] = True
            request["dispatched_ms"] = self.now_ms()
            try:
                raw = self._player.MetinQueueAdd(vid)
            except Exception:
                raw = None
        finally:
            if pair_started:
                # A recorder up snapshot does not change OS/player button state.
                # Never retry a failed/uncertain recorder call.
                self._pair_end(request, vid)
        request["raw_return"] = raw
        post = self.snapshot()
        request["last_snapshot"] = post
        if not post.get("valid"):
            return self.UNKNOWN
        if post.get("player_cookie") != pre.get("player_cookie"):
            return self.UNKNOWN
        if vid in post["vids"]:
            # Truthy stock return alone never means ADDED; membership is decisive.
            # add returned falsy yet the VID is present -> invariant error, not a
            # safe rejection.
            return self.ADDED if raw else self.UNKNOWN
        if raw == 0:
            return self.REJECTED_NATIVE
        return self.UNKNOWN

    def remove_once(self, request):
        """One verified `player.MetinQueueRemove(vid)` under the dispatch-time
        contract."""
        vid = int(request["vid"])
        pre, problem = self._dispatch_precheck(request)
        if problem is not None:
            return problem
        if vid not in pre["vids"]:
            return self.ALREADY_ABSENT
        request["dispatched"] = True
        request["dispatched_ms"] = self.now_ms()
        raw = None
        try:
            raw = self._player.MetinQueueRemove(vid)
        except Exception:
            raw = None
        request["raw_return"] = raw
        post = self.snapshot()
        request["last_snapshot"] = post
        if not post.get("valid"):
            return self.UNKNOWN
        if post.get("player_cookie") != pre.get("player_cookie"):
            return self.UNKNOWN
        if vid not in post["vids"]:
            return self.REMOVED
        return self.UNKNOWN

    def set_enabled_once(self, value, lease=None):
        """One `player.MetinQueueSetEnabled(value)` with post verification."""
        pre = self.snapshot()
        if not pre.get("valid") or not pre.get("stock_binding_ok"):
            return "UNKNOWN", pre, pre
        try:
            self._player.MetinQueueSetEnabled(1 if value else 0)
        except Exception:
            return "UNKNOWN", self.snapshot(), pre
        post = self.snapshot()
        if post.get("valid") and bool(post["enabled"]) == bool(value):
            return ("ENABLED" if value else "DISABLED"), post, pre
        return "UNKNOWN", post, pre


class HunterCandidateSelector(object):
    """Publishes one immutable candidate snapshot per scan and selects one
    candidate with deterministic nearest-then-VID ordering.  Names are for
    display/priority only."""

    def __init__(self, player_module, chr_module, nonplayer_module):
        self._player = player_module
        self._chr = chr_module
        self._nonplayer = nonplayer_module

    def publish(self, scan_vids, player_position, anchor_position, radius,
                epoch, now_ms):
        px, py = player_position[:2]
        radius2 = float(radius) ** 2
        candidates = []
        for vid in scan_vids:
            vid = int(vid)
            if vid <= 0:
                continue
            try:
                vnum = int(self._chr.GetVirtualNumber(vid))
                name = ascii_text(self._chr.GetNameByVID(vid))
                gx, gy = self._chr.GetPixelPosition(vid)[:2]
            except Exception:
                continue
            if not self._nonplayer.IsMonsterStone(vnum):
                continue
            # squared-distance comparisons, no integer rounding
            player_d2 = (gx - px) ** 2 + (gy - py) ** 2
            if player_d2 > radius2:
                continue
            if anchor_position is not None:
                ax, ay = anchor_position[:2]
                if (gx - ax) ** 2 + (gy - ay) ** 2 > radius2:
                    continue
            candidates.append((player_d2, vid, name, vnum, gx, gy))
        candidates.sort(key=lambda c: (c[0], c[1]))
        return {
            "epoch": epoch,
            "created_ms": now_ms,
            "radius": int(radius),
            "player_position": (px, py),
            "anchor_position": (tuple(anchor_position[:2])
                                if anchor_position is not None else None),
            "candidates": tuple(
                {"vid": c[1], "name": c[2], "vnum": c[3],
                 "x": c[4], "y": c[5], "distance2": c[0]}
                for c in candidates),
        }

    @staticmethod
    def _candidate_angle(snapshot, candidate):
        px, py = snapshot.get("player_position") or (0, 0)
        angle = math.degrees(math.atan2(candidate["y"] - py,
                                        candidate["x"] - px))
        return angle % 360.0

    def select(self, snapshot, now_ms, queue_vids, excluded_vids, backoff,
               priority=False, sweep_angle=None, sweep_direction=-1):
        """Deterministic candidate selection: fresh snapshot (<=2000ms), not in
        the authoritative queue, not excluded/pending, not in backoff; nearest
        then VID.  Returns a candidate dict or None."""
        if snapshot is None or now_ms is None:
            return None
        created = snapshot.get("created_ms")
        if created is None or now_ms - created > 2000:
            return None
        eligible = []
        for cand in snapshot["candidates"]:
            vid = cand["vid"]
            if vid in queue_vids or vid in excluded_vids:
                continue
            if now_ms < backoff.get(vid, 0):
                continue
            if priority and PRIORITY_EVENT_METIN_NAME not in cand["name"].lower():
                continue
            eligible.append(cand)
        if not eligible:
            return None
        if priority or sweep_angle is None:
            return eligible[0]

        def sweep_key(candidate):
            angle = self._candidate_angle(snapshot, candidate)
            if sweep_direction < 0:
                turn = (float(sweep_angle) - angle) % 360.0
            else:
                turn = (angle - float(sweep_angle)) % 360.0
            return (turn, candidate.get("distance2", 0), candidate["vid"])

        return min(eligible, key=sweep_key)


class ManualQueueRefillProfile(object):
    """Cadence measured from the 2026-10-17 manual queue control.

    The long samples are measured from the first observed vacancy until the
    first addition in a refill burst.  The short samples are the observed gaps
    between additions inside a burst.  Sampling the measured values preserves
    the manual session's distribution without replaying a fixed timeline.
    """

    REFILL_START_DELAY_SAMPLES_MS = (
        12984, 7688, 12297, 35531, 52547, 31718, 44922,
        66266, 63000, 8156, 41781, 33282, 44156, 31500,
        17281, 4406, 35781, 45500, 26625, 35016, 32281,
    )
    BURST_ADD_DELAY_SAMPLES_MS = (
        437, 438, 453, 546, 547, 547, 547, 594, 656, 656,
        656, 672, 688, 703, 704, 765, 765, 765, 765, 766,
        766, 812, 891, 984, 984, 985, 1093, 1203, 1203,
        1203, 1219, 1219, 1313, 1453, 1453, 1547, 1922,
        2031, 2906,
    )
    # Of 16 multi-add manual bursts, 12 were purely clockwise, two were purely
    # counter-clockwise and two contained a reversal.  Choose one stable sweep
    # direction per burst using the observed pure-burst weighting.
    SWEEP_DIRECTION_SAMPLES = (-1, -1, -1, -1, -1, -1,
                               -1, -1, -1, -1, -1, -1,
                               1, 1)

    def __init__(self, chooser=None):
        self._chooser = chooser or random.choice

    def refill_start_delay_ms(self):
        return int(self._chooser(self.REFILL_START_DELAY_SAMPLES_MS))

    def burst_add_delay_ms(self):
        return int(self._chooser(self.BURST_ADD_DELAY_SAMPLES_MS))

    def sweep_direction(self):
        return int(self._chooser(self.SWEEP_DIRECTION_SAMPLES))


class HunterController(object):
    """Hunter state machine: OFF/STARTING/RUNNING/WAITING/RECONCILING/PAUSED/
    STOPPING/ERROR, with session epochs, an exclusive lease, an ownership
    ledger, measured manual refill cadence, uncertainty reconciliation and
    Legendary priority (gated by `priority_enabled`)."""

    OFF = "OFF"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    RECONCILING = "RECONCILING"
    PAUSED = "PAUSED"
    STOPPING = "STOPPING"
    ERROR = "ERROR"

    PRIORITY_NONE = "NONE"
    PRIORITY_DRAINING_OWNED = "DRAINING_OWNED"
    PRIORITY_ADDING = "ADDING_PRIORITY"
    PRIORITY_ACTIVE = "ACTIVE_PRIORITY"
    PRIORITY_RETURNING = "RETURNING"

    ADD_INTERVAL_MS = 1000
    UNKNOWN_POLL_MS = 50
    UNKNOWN_DEADLINE_MS = 2000
    REJECT_BACKOFF_MS = 2000
    CANDIDATE_STALE_MS = 2000
    PRIORITY_ABSENCE_MS = 1500
    POLL_GAP_MS = 100

    def __init__(self, gateway, selector, clock, gameplay_available,
                 log=None, capacity_limit=5, priority_enabled=False,
                 radius_getter=None, anchor_getter=None, refill_profile=None):
        self._gateway = gateway
        self._selector = selector
        self._clock = clock
        self._gameplay_available = gameplay_available
        self._log = log or (lambda msg: None)
        self._capacity_limit = capacity_limit
        self.priority_enabled = priority_enabled
        self._radius_getter = radius_getter
        self._anchor_getter = anchor_getter
        self._refill_profile = refill_profile or ManualQueueRefillProfile()
        self._lease_counter = 0
        self._request_counter = 0
        self.reset()

    def reset(self):
        self.state = self.OFF
        self.user_requested_on = False
        self.pause_reason = None
        self.resume_token = None
        self.epoch = 0
        self.lease = None
        self.pending_request = None
        self.ledger = set()
        self.reject_backoff = {}
        self.quarantine = set()
        self.priority_state = self.PRIORITY_NONE
        self.priority_vid = 0
        self.priority_intent = None
        self.priority_target_absent_ms = None
        self.next_add_ms = 0
        self.refill_due_ms = None
        self.refill_burst_active = False
        self.refill_completed_count = None
        self.sweep_angle = None
        self.sweep_direction = -1
        self.last_scan = None
        self.last_snapshot = None
        self.last_poll_ms = 0
        self.error_reason = None
        self.status_text = "off"
        self.history = []

    # -- helpers -------------------------------------------------------------
    def _now(self):
        clock = self._clock
        if clock is None:
            return None
        try:
            return int(clock())
        except Exception:
            return None

    def _new_epoch(self):
        self.epoch += 1
        return self.epoch

    def _invalidate_session(self, reason):
        self._new_epoch()
        self.lease = None
        self.pending_request = None
        self.resume_token = None
        self.priority_intent = None
        self.priority_state = self.PRIORITY_NONE
        self.priority_vid = 0
        self.priority_target_absent_ms = None
        self.quarantine = set()
        self.next_add_ms = 0
        self.refill_due_ms = None
        self.refill_burst_active = False
        self.refill_completed_count = None
        self.sweep_angle = None
        self.sweep_direction = -1
        self._log("session invalidated: %s (epoch %d)" % (reason, self.epoch))

    def _set_state(self, state, status):
        if self.state != state:
            self._log("state %s -> %s" % (self.state, state))
        self.state = state
        self.status_text = status

    def _request(self, kind, vid, deadline_ms, priority=False):
        self._request_counter += 1
        snapshot = self._gateway.snapshot()
        return {
            "id": self._request_counter,
            "kind": kind,
            "vid": vid,
            "priority": priority,
            "epoch": self.epoch,
            "lease_id": self.lease["id"] if self.lease else None,
            "player_cookie": snapshot.get("player_cookie"),
            "created_ms": self._now(),
            "deadline_ms": deadline_ms,
            "dispatched": False,
            "raw_return": None,
            "last_snapshot": None,
            "pre_snapshot": None,
        }

    def _current_radius(self):
        if self._radius_getter is not None:
            try:
                return int(self._radius_getter())
            except Exception:
                pass
        return int((self.last_scan or {}).get("radius") or 0)

    def _current_anchor(self):
        if self._anchor_getter is not None:
            try:
                return self._anchor_getter()
            except Exception:
                pass
        return (self.last_scan or {}).get("anchor_position")

    # -- lifecycle -----------------------------------------------------------
    def start(self):
        if self.state not in (self.OFF, self.ERROR):
            return self.state
        now = self._now()
        if now is None:
            self._set_state(self.ERROR, "Queue: monotonic clock unavailable")
            self.error_reason = "clock unavailable"
            return self.state
        if not self._gameplay_available():
            self._set_state(self.ERROR, "Queue: not in playable world")
            self.error_reason = "gameplay unavailable"
            return self.state
        if self.pause_reason is not None:
            self._set_state(self.ERROR, "Queue: safety pause active")
            self.error_reason = "reaction pause active"
            return self.state
        snap = self._gateway.snapshot()
        if not snap.get("valid"):
            self._set_state(self.ERROR, "Queue: observer unavailable")
            self.error_reason = "observer invalid: %s" % snap.get("error")
            return self.state
        if not snap.get("stock_binding_ok"):
            self._set_state(self.ERROR, "Queue: stock binding changed")
            self.error_reason = "stock binding identity mismatch"
            return self.state
        if snap["vids"]:
            self._set_state(self.OFF, "Queue: busy - stop manual queue first")
            self._log("start blocked: queued=%d enabled=%d" %
                      (len(snap["vids"]), bool(snap["enabled"])))
            return self.state
        self.user_requested_on = True
        self._set_state(self.STARTING, "Queue: acquiring lease")
        self._lease_counter += 1
        self.lease = {"id": self._lease_counter, "epoch": self.epoch,
                      "cookie": snap.get("player_cookie")}
        outcome, post, _pre = self._gateway.set_enabled_once(True, self.lease)
        self._invalidate_snapshot()
        if outcome != "ENABLED" or not post.get("valid") or not post["enabled"]:
            self._set_state(self.ERROR, "Queue: enable failed")
            self.error_reason = "enable outcome %s" % outcome
            self.user_requested_on = False
            self.lease = None
            return self.state
        self.ledger = set()
        self.quarantine = set()
        self.next_add_ms = now
        self.refill_due_ms = None
        self.refill_burst_active = True
        self.refill_completed_count = None
        self.sweep_angle = None
        self.sweep_direction = self._refill_profile.sweep_direction()
        self._set_state(self.RUNNING, "Queue: running")
        return self.state

    def _cleanup_owned(self, reason):
        """Quiesce owned native state.  Returns "cleared", "foreign", or "error".
        Disables a still-owned enabled session even when empty; removes owned VIDs
        one at a time when foreign members are present.  Never clears a mixed/
        foreign queue and never mutates without a valid current lease."""
        if self.lease is None:
            return "cleared"
        snap = self._gateway.snapshot()
        if not snap.get("valid") or not snap.get("stock_binding_ok"):
            self.error_reason = "cleanup snapshot invalid"
            return "error"
        if snap.get("player_cookie") != self.lease.get("cookie"):
            self.error_reason = "cleanup cookie changed"
            return "error"
        remaining = [v for v in snap["vids"] if v in self.ledger]
        foreign = [v for v in snap["vids"] if v not in self.ledger]
        if not foreign:
            if snap["enabled"]:
                outcome, post, _pre = self._gateway.set_enabled_once(False, self.lease)
                self._invalidate_snapshot()
                if outcome != "DISABLED":
                    self.error_reason = "disable outcome %s" % outcome
                    return "error"
                if post.get("valid") and post["vids"]:
                    self.error_reason = "disable left queue populated"
                    return "error"
            self.ledger = set()
            return "cleared"
        for vid in remaining:
            request = self._request("remove", vid, self._now() + 2000)
            outcome = self._gateway.remove_once(request)
            self._invalidate_snapshot()
            if outcome in (HunterQueueGateway.REMOVED, HunterQueueGateway.ALREADY_ABSENT):
                self.ledger.discard(vid)
            else:
                self.error_reason = "remove %d %s" % (vid, outcome)
                return "error"
        if self.ledger:
            self.error_reason = "owned VIDs not removed"
            return "error"
        return "foreign"

    def stop(self, reason="stopped"):
        self.user_requested_on = False
        self.pause_reason = None
        self.resume_token = None
        self._set_state(self.STOPPING, "Queue: stopping")
        result = self._cleanup_owned(reason)
        self.pending_request = None
        self.priority_state = self.PRIORITY_NONE
        self.priority_vid = 0
        self.priority_intent = None
        if result == "error":
            self._set_state(self.ERROR, "Queue: native cleanup incomplete")
            self._log("stop unconfirmed: %s (%s)" % (reason, self.error_reason))
            return self.state
        self.lease = None
        self._set_state(self.OFF, "Queue: %s" % reason)
        return self.state

    def pause(self, reason):
        if self.state == self.OFF:
            return None
        self.pause_reason = reason
        token = {"epoch": self.epoch,
                 "lease_id": (self.lease or {}).get("id"),
                 "cookie": (self.lease or {}).get("cookie"),
                 "priority_intent": self.priority_intent}
        result = self._cleanup_owned(reason)
        self.pending_request = None
        if result == "error":
            self._set_state(self.ERROR, "Queue: pause cleanup incomplete")
            self._log("pause unconfirmed: %s (%s)" % (reason, self.error_reason))
            return None
        self._set_state(self.PAUSED, "Queue: paused (%s)" % reason)
        self.resume_token = token
        return token

    def resume(self, token):
        if not token or self.state != self.PAUSED:
            return self.state
        if not self.user_requested_on:
            self._set_state(self.OFF, "Queue: off")
            return self.state
        if (token.get("epoch") != self.epoch or
                token.get("lease_id") != (self.lease or {}).get("id")):
            self._log("resume token stale; staying paused")
            return self.state
        if not self._gameplay_available():
            return self.state
        snap = self._gateway.snapshot()
        if not snap.get("valid"):
            self._set_state(self.ERROR, "Queue: observer unavailable")
            return self.state
        if snap["vids"] or snap["enabled"]:
            self._log("resume blocked: queue busy")
            return self.state
        outcome, post, _pre = self._gateway.set_enabled_once(True, self.lease)
        self._invalidate_snapshot()
        if outcome != "ENABLED" or not post.get("valid") or not post["enabled"]:
            self._set_state(self.ERROR, "Queue: resume enable failed")
            self.error_reason = "resume enable %s" % outcome
            return self.state
        self.pause_reason = None
        self.resume_token = None
        self.next_add_ms = self._now()
        self.refill_due_ms = None
        self.refill_burst_active = True
        self.refill_completed_count = None
        self.sweep_angle = None
        self.sweep_direction = self._refill_profile.sweep_direction()
        self._set_state(self.RUNNING, "Queue: running")
        return self.state

    def on_session_change(self, reason):
        self._invalidate_session(reason)
        self.user_requested_on = False
        self.pause_reason = None
        self.resume_token = None
        self.ledger = set()
        self.reject_backoff = {}
        self.last_scan = None
        self._set_state(self.OFF, "Queue: stopped (%s)" % reason)

    def on_scan(self, snapshot):
        self.last_scan = snapshot

    def _invalidate_snapshot(self):
        """Drop the cached queue observation so the next read is fresh.  Ledger
        pruning and ownership checks must never run against an observation
        older than the most recent mutation."""
        self.last_snapshot = None

    # -- per-tick processing ------------------------------------------------
    def tick(self, now_ms):
        if now_ms is None:
            self._set_state(self.ERROR, "Queue: monotonic clock unavailable")
            return self.state

        # Throttle cheap queue observation to once per POLL_GAP_MS while active.
        if self.last_snapshot is None or now_ms - self.last_poll_ms >= self.POLL_GAP_MS:
            snap = self._gateway.snapshot()
            self.last_poll_ms = now_ms
            self.last_snapshot = snap
        snap = self.last_snapshot

        # session-safety: revalidate cookie against the current observation
        if self.lease is not None:
            if not snap.get("valid"):
                self._invalidate_session("observer invalid")
                self._set_state(self.ERROR, "Queue: observer unavailable")
                return self.state
            if snap.get("player_cookie") != self.lease.get("cookie"):
                self._invalidate_session("player singleton changed")
                self._set_state(self.ERROR, "Queue: session changed")
                return self.state

        # reconcile a dispatched-but-unresolved request regardless of state
        if self.pending_request is not None:
            return self._reconcile(now_ms)

        if self.state in (self.OFF, self.PAUSED, self.STOPPING):
            return self.state

        if self.state == self.ERROR:
            return self.state

        # RUNNING and WAITING both re-evaluate the refill decision each tick.
        return self._run(now_ms)

    def _reconcile(self, now_ms):
        request = self.pending_request
        self._set_state(self.RECONCILING, "Queue: reconciling")
        snap = self._gateway.snapshot()
        if snap.get("valid") and request["kind"] == "add":
            if request["vid"] in snap["vids"]:
                self.ledger.add(request["vid"])
                if request.get("sweep_angle_after_add") is not None:
                    self.sweep_angle = request["sweep_angle_after_add"]
                if request.get("priority"):
                    self.priority_vid = request["vid"]
                    self.priority_target_absent_ms = None
                    self.priority_state = self.PRIORITY_ACTIVE
                self.pending_request = None
                self._set_state(self.RUNNING, "Queue: running")
                return self.state
            if now_ms - request["created_ms"] < self.UNKNOWN_DEADLINE_MS:
                return self.state  # keep observing until the deadline
        if request.get("dispatched") and now_ms - request["created_ms"] >= self.UNKNOWN_DEADLINE_MS:
            self.quarantine.add(request["vid"])
            self.history.append(dict(request))
            self.pending_request = None
            self._set_state(self.ERROR, "Queue: unresolved request")
            self.error_reason = ("request %d unresolved; VID %d quarantined for "
                                 "epoch %d" % (request["id"], request["vid"], self.epoch))
            self._cleanup_owned("unresolved request")
            return self.state
        return self.state

    def _run(self, now_ms):
        snap = self.last_snapshot or self._gateway.snapshot()
        self.last_snapshot = snap
        if not snap.get("valid"):
            self._set_state(self.ERROR, "Queue: observer unavailable")
            return self.state
        vids = snap["vids"]

        # exclusive-ownership invariants
        if self.lease is not None:
            if not snap.get("enabled"):
                self._invalidate_session("queue disabled externally")
                self._set_state(self.ERROR, "Queue: ownership lost (disabled)")
                self.error_reason = "queue disabled externally"
                return self.state
            foreign = [v for v in vids if v not in self.ledger]
            if foreign:
                self._invalidate_session("foreign queue membership")
                self._set_state(self.ERROR, "Queue: ownership conflict")
                self.error_reason = "foreign VIDs %s" % foreign
                return self.state
        # reconcile naturally-departed ledger VIDs
        current = set(vids)
        for v in list(self.ledger):
            if v not in current:
                self.ledger.discard(v)

        experiment_error = getattr(self._gateway, "input_experiment_error", None)
        if experiment_error:
            self.error_reason = experiment_error
            self._set_state(self.ERROR, "Queue: recorder experiment halted")
            return self.state

        max_size = int(snap.get("max_size") or 0)
        if max_size <= 0:
            self._set_state(self.ERROR, "Queue: invalid max size")
            return self.state
        capacity = min(self._capacity_limit, max_size)
        full = len(vids) >= capacity

        if self.priority_enabled and self.priority_state != self.PRIORITY_NONE:
            if self._advance_priority(now_ms, snap):
                return self.state

        if full:
            self.refill_due_ms = None
            self.refill_burst_active = False
            self.refill_completed_count = capacity
            self.sweep_angle = None
            self._set_state(self.WAITING, "Queue: full %d/%d" % (len(vids), capacity))
            return self.state

        # Full or exhausted bursts establish the achieved queue count.  Wait
        # for its first departure before scheduling one measured manual delay.
        # An empty exhausted queue schedules a delay without needing a departure.
        if not self.refill_burst_active:
            if self.refill_due_ms is None:
                if (self.refill_completed_count is not None and
                        self.refill_completed_count > 0 and
                        len(vids) >= self.refill_completed_count):
                    self._set_state(
                        self.WAITING,
                        "Queue: filled available %d/%d; waiting for departure" %
                        (len(vids), capacity))
                    return self.state
                delay_ms = self._refill_profile.refill_start_delay_ms()
                self.refill_due_ms = now_ms + delay_ms
                self._log("manual refill scheduled in %d ms (queue %d/%d)" %
                          (delay_ms, len(vids), capacity))
            if now_ms < self.refill_due_ms:
                self._set_state(
                    self.WAITING,
                    "Queue: manual refill in %d ms (%d/%d)" %
                    (self.refill_due_ms - now_ms, len(vids), capacity))
                return self.state
            self.refill_due_ms = None
            self.refill_burst_active = True
            self.refill_completed_count = None
            self.sweep_angle = None
            self.sweep_direction = self._refill_profile.sweep_direction()
            self.next_add_ms = now_ms
            self._log("manual refill burst started (queue %d/%d)" %
                      (len(vids), capacity))

        if now_ms < self.next_add_ms:
            self._set_state(self.WAITING, "Queue: next add in %d ms" % (self.next_add_ms - now_ms))
            return self.state

        if self.last_scan is None:
            self._set_state(self.WAITING, "Queue: waiting for scan")
            return self.state

        if self.last_scan.get("epoch") != self.epoch:
            self._set_state(self.WAITING, "Queue: stale scan")
            return self.state

        candidate = self._selector.select(
            self.last_scan, now_ms, set(vids), set(self.ledger) | set(self.quarantine),
            self.reject_backoff, priority=False,
            sweep_angle=self.sweep_angle,
            sweep_direction=self.sweep_direction)
        if candidate is None:
            # A missing/stale scan cannot prove that this burst is exhausted.
            created_ms = self.last_scan.get("created_ms")
            if (created_ms is None or now_ms < created_ms or
                    now_ms - created_ms > self.CANDIDATE_STALE_MS):
                self._set_state(self.WAITING, "Queue: stale scan")
                return self.state
            self.refill_burst_active = False
            self.refill_completed_count = len(vids)
            self.refill_due_ms = None
            self.sweep_angle = None
            self._log("manual refill burst complete: no eligible candidate "
                      "(queue %d/%d)" % (len(vids), capacity))
            self._set_state(
                self.WAITING,
                "Queue: filled available %d/%d; %s" %
                (len(vids), capacity,
                 "waiting for departure" if vids else "refill wait next"))
            return self.state

        if not self._revalidate(candidate, snap):
            return self.state

        request = self._request("add", candidate["vid"], now_ms + self.UNKNOWN_DEADLINE_MS)
        try:
            request["sweep_angle_after_add"] = (
                HunterCandidateSelector._candidate_angle(self.last_scan, candidate))
        except Exception:
            request["sweep_angle_after_add"] = None
        self.next_add_ms = now_ms + self._refill_profile.burst_add_delay_ms()
        outcome = self._gateway.add_once(request)
        self._invalidate_snapshot()
        if outcome == HunterQueueGateway.ADDED:
            self.ledger.add(candidate["vid"])
            if request.get("sweep_angle_after_add") is not None:
                self.sweep_angle = request["sweep_angle_after_add"]
            post = request.get("last_snapshot") or {}
            if (post.get("valid") and
                    len(post.get("vids") or ()) >= capacity):
                self.refill_due_ms = None
                self.refill_burst_active = False
                self.refill_completed_count = capacity
            self._log("added VID %d (queue %d/%d)" % (candidate["vid"], len(snap["vids"]) + 1, capacity))
        elif outcome == HunterQueueGateway.REJECTED_NATIVE:
            self.reject_backoff[candidate["vid"]] = now_ms + self.REJECT_BACKOFF_MS
        elif outcome == HunterQueueGateway.UNKNOWN:
            self.pending_request = request
            self._set_state(self.RECONCILING, "Queue: reconciling")
            return self.state
        self._set_state(self.RUNNING, "Queue: running")
        return self.state

    def _revalidate(self, candidate, snap):
        """Fresh actor race/position, fresh player/anchor/radius, and exact
        native admission for the one selected VID."""
        vid = candidate["vid"]
        try:
            vnum = int(self._selector._chr.GetVirtualNumber(vid))
            if vnum != int(candidate.get("vnum")):
                return False
            name = ascii_text(self._selector._chr.GetNameByVID(vid))
            gx, gy = self._selector._chr.GetPixelPosition(vid)[:2]
            is_stone = getattr(self._selector._chr, "IsStone", None)
            if not callable(is_stone) or not is_stone(vid):
                return False
            if not self._selector._nonplayer.IsMonsterStone(vnum):
                return False
        except Exception:
            return False
        try:
            player_pos = self._selector._player.GetMainCharacterPosition()
            px, py = player_pos[:2]
        except Exception:
            return False
        radius = self._current_radius()
        if radius <= 0:
            return False
        anchor = self._current_anchor()
        if (gx - px) ** 2 + (gy - py) ** 2 > float(radius) ** 2:
            return False
        if anchor is not None:
            ax, ay = anchor[:2]
            if (gx - ax) ** 2 + (gy - ay) ** 2 > float(radius) ** 2:
                return False
        admission = self._gateway.admission(vid)
        if not admission.get("valid"):
            self._set_state(self.ERROR, "Queue: admission unavailable")
            self.error_reason = admission.get("reason")
            return False
        if not admission.get("eligible"):
            self.reject_backoff[vid] = self._now() + self.REJECT_BACKOFF_MS
            return False
        if admission.get("player_cookie") != snap.get("player_cookie"):
            self._invalidate_session("admission cookie changed")
            return False
        return True

    def _advance_priority(self, now_ms, snap):
        """Legendary priority state machine.  Returns True when it handled the
        tick (no ordinary refill this tick)."""
        vids = snap["vids"]
        if self.priority_state == self.PRIORITY_DRAINING_OWNED:
            owned = [v for v in vids if v in self.ledger]
            if not owned:
                self.priority_state = self.PRIORITY_ADDING
                self.next_add_ms = now_ms + self.ADD_INTERVAL_MS
            else:
                vid = owned[0]
                request = self._request("remove", vid, now_ms + 2000)
                outcome = self._gateway.remove_once(request)
                self._invalidate_snapshot()
                if outcome in (HunterQueueGateway.REMOVED, HunterQueueGateway.ALREADY_ABSENT):
                    self.ledger.discard(vid)
                elif outcome == HunterQueueGateway.UNKNOWN:
                    self._set_state(self.ERROR, "Queue: priority drain uncertain")
                    return True
            return True
        if self.priority_state == self.PRIORITY_ADDING:
            if now_ms < self.next_add_ms:
                return True
            cand = None
            intent_vid = (self.priority_intent or {}).get("vid")
            if intent_vid is not None:
                for c in (self.last_scan or {}).get("candidates", ()):
                    if c["vid"] == intent_vid:
                        cand = c
                        break
            if cand is None:
                cand = self._selector.select(self.last_scan, now_ms, set(), set(),
                                             {}, priority=True)
            if cand is None or not self._revalidate(cand, snap):
                self._set_state(self.ERROR, "Queue: priority target invalid")
                return True
            request = self._request("add", cand["vid"], now_ms + self.UNKNOWN_DEADLINE_MS,
                                    priority=True)
            self.next_add_ms = now_ms + self.ADD_INTERVAL_MS
            outcome = self._gateway.add_once(request)
            self._invalidate_snapshot()
            if outcome == HunterQueueGateway.ADDED:
                self.priority_vid = cand["vid"]
                self.ledger.add(cand["vid"])
                self.priority_target_absent_ms = None
                self.priority_state = self.PRIORITY_ACTIVE
                self._log("priority target added: VID %d" % cand["vid"])
            elif outcome == HunterQueueGateway.UNKNOWN:
                self.pending_request = request
                self._set_state(self.RECONCILING, "Queue: reconciling")
            else:
                self._set_state(self.ERROR, "Queue: priority add rejected")
            return True
        if self.priority_state == self.PRIORITY_ACTIVE:
            still_present = self.priority_vid in vids
            seen_live = any(c["vid"] == self.priority_vid
                            for c in (self.last_scan or {}).get("candidates", ()))
            if still_present:
                self.priority_target_absent_ms = None
                return True
            if seen_live:
                self._set_state(self.ERROR, "Queue: priority target lost from queue")
                return True
            if self.priority_target_absent_ms is None:
                self.priority_target_absent_ms = now_ms
                return True
            if now_ms - self.priority_target_absent_ms < self.PRIORITY_ABSENCE_MS:
                return True
            self._log("priority target gone: VID %d" % self.priority_vid)
            self.priority_vid = 0
            self.priority_state = self.PRIORITY_NONE
            self.priority_target_absent_ms = None
            self.priority_intent = None
            self.next_add_ms = now_ms
            self.refill_due_ms = None
            self.refill_burst_active = True
            self.refill_completed_count = None
            self.sweep_angle = None
            self.sweep_direction = self._refill_profile.sweep_direction()
            self._set_state(self.RUNNING, "Queue: running")
            return True
        return False

    def request_priority(self, vid=None):
        """Enter the Legendary priority flow (drains owned entries first)."""
        if not self.priority_enabled:
            return False
        if self.state not in (self.RUNNING, self.WAITING):
            return False
        if self.lease is None:
            return False
        self.priority_intent = {"vid": vid, "epoch": self.epoch}
        self.priority_vid = 0
        self.priority_target_absent_ms = None
        self.priority_state = self.PRIORITY_DRAINING_OWNED
        self.next_add_ms = self._now()
        return True


class HunterAuditObserver(object):
    """Explicitly-enabled, read-only audit-status observation (plan section 10.1).

    Independent of Hunter ON.  Polls the verified audit_status() query on the
    update thread (throttled), logging the first observation, state/interval
    changes, and a 1 Hz heartbeat with observation count and max sampling gap.
    It never writes, enables, disables or tunes the recorder, and it keeps an
    invalid/unknown status distinct from "recorder-disabled"."""

    POLL_GAP_MS = 100
    HEARTBEAT_MS = 1000

    def __init__(self, gateway, clock, log=None, enabled=False):
        self._gateway = gateway
        self._clock = clock
        self._log = log or (lambda msg: None)
        self.enabled = enabled
        self._last_obs = None
        self._last_poll_ms = 0
        self._last_heartbeat_ms = 0
        self._obs_count = 0
        self._max_gap_ms = 0

    def observe(self, now_ms):
        if not self.enabled or now_ms is None:
            return
        if self._last_poll_ms and now_ms - self._last_poll_ms < self.POLL_GAP_MS:
            return
        gap = (now_ms - self._last_poll_ms) if self._last_poll_ms else 0
        self._last_poll_ms = now_ms
        if gap > self._max_gap_ms:
            self._max_gap_ms = gap
        status = self._gateway.audit_status()
        self._obs_count += 1
        if not status.get("valid"):
            if self._last_obs is None or self._last_obs.get("valid"):
                self._log("audit status invalid: %s" % status.get("error"))
            self._last_obs = status
            return
        prev = self._last_obs
        if prev is None or not prev.get("valid"):
            self._log("audit first observation: recorder_enabled=%s sample_ms=%s "
                      "flush_ms=%s app_active=%s" %
                      (status.get("recorder_enabled"), status.get("sample_ms"),
                       status.get("flush_ms"), status.get("app_active")))
        elif (prev.get("recorder_enabled") != status.get("recorder_enabled") or
              prev.get("sample_ms") != status.get("sample_ms") or
              prev.get("flush_ms") != status.get("flush_ms") or
              prev.get("app_active") != status.get("app_active")):
            self._log("audit change: recorder_enabled=%s->%s sample_ms=%s->%s "
                      "flush_ms=%s->%s app_active=%s->%s" %
                      (prev.get("recorder_enabled"), status.get("recorder_enabled"),
                       prev.get("sample_ms"), status.get("sample_ms"),
                       prev.get("flush_ms"), status.get("flush_ms"),
                       prev.get("app_active"), status.get("app_active")))
        self._last_obs = status
        if (self._last_heartbeat_ms == 0 or
                now_ms - self._last_heartbeat_ms >= self.HEARTBEAT_MS):
            self._last_heartbeat_ms = now_ms
            self._log("audit heartbeat: observations=%d max_gap_ms=%d" %
                      (self._obs_count, self._max_gap_ms))


# --- Yin Yang Duel strategy (cards 0..8; even=black, odd=white) ---
# Both players hold the same 9-card hand (0..8).  Each round the higher card
# wins; ties score nothing.  You only ever see the colour of the opponent's
# card, so the opponent's exact remaining values are unknowable.

YINYANG_DUEL_BLACK = (0, 2, 4, 6, 8)
YINYANG_DUEL_WHITE = (1, 3, 5, 7)


def duel_card_color(value):
    return "black" if (int(value) % 2) == 0 else "white"


def duel_we_lead(lead_info):
    """Whether WE lead (play blind) this round, from the window's `leadInfo`.

    Live observation (round 1): when `leadInfo.leads` is True the opponent
    already has exactly one card marked `played`, so `leads=True` actually
    means the OPPONENT led and we are following.  (The `black` flag is their
    led card's colour.)
    """
    return not bool((lead_info or {}).get("leads", False))


def choose_duel_card(my_hand, opponent_color):
    """Minimal-winner heuristic for one Yin Yang Duel round.

    my_hand: remaining card values we still hold.
    opponent_color: 'black'/'white' when the opponent led and we can see their
    card colour, or None when we lead blind.

    - Follower: play the smallest card that beats the opponent's median card of
      that colour (win cheaply); if that is impossible, sacrifice our lowest.
    - Leader: play the median of our hand as a balanced blind move.
    """
    hand = sorted(int(value) for value in my_hand)
    if not hand:
        return None
    if opponent_color is None:
        return hand[len(hand) // 2]
    possible = YINYANG_DUEL_BLACK if opponent_color == "black" else YINYANG_DUEL_WHITE
    target = sorted(possible)[len(possible) // 2]
    winners = [value for value in hand if value > target]
    return winners[0] if winners else hand[0]


def choose_duel_card_follow(my_hand, opponent_led_value):
    """Follower with exact knowledge of the opponent's led card: beat it by the
    smallest margin, or sacrifice our lowest card if we cannot win."""
    hand = sorted(int(value) for value in my_hand)
    if not hand:
        return None
    winners = [value for value in hand if value > opponent_led_value]
    return winners[0] if winners else hand[0]


def choose_duel_card_lead(my_hand, opponent_remaining):
    """Lead blind with full knowledge of the opponent's remaining hand: play
    the smallest card that beats their median remaining card; otherwise
    sacrifice our lowest card."""
    hand = sorted(int(value) for value in my_hand)
    if not hand:
        return None
    remaining = sorted(opponent_remaining)
    if not remaining:
        return hand[0]
    target = remaining[len(remaining) // 2]
    winners = [value for value in hand if value > target]
    return winners[0] if winners else hand[0]


# --- Yin Yang Duel solver (round-safe, pure card-game logic) ---
# The controller reads the client and clicks; the solver is a pure function of
# an immutable snapshot and only reasons about the 9-card match.

DUEL_FULL_MASK = 0x1FF
DUEL_WORST_WEIGHT = 0.25
DUEL_SOLVER_BUDGET_SECONDS = 0.020
DUEL_WARM_BUDGET_SECONDS = 0.050


def duel_mask_cards(mask):
    return [value for value in range(9) if mask & (1 << value)]


def duel_mask_count(mask):
    count = 0
    while mask:
        count += mask & 1
        mask >>= 1
    return count


def duel_mask_remove(mask, value):
    return mask & ~(1 << value)


def duel_mask_color(mask, color):
    result = 0
    for value in duel_mask_cards(mask):
        if duel_card_color(value) == color:
            result |= 1 << value
    return result


def round_score_delta(our_card, opponent_card):
    if our_card > opponent_card:
        return 1
    if our_card < opponent_card:
        return -1
    return 0


def terminal_duel_value(score_delta):
    # (prob_win, -prob_loss, expected_score_delta, worst_case_utility)
    if score_delta > 0:
        return (1.0, 0.0, float(score_delta), 1.0)
    if score_delta < 0:
        return (0.0, -1.0, float(score_delta), -1.0)
    return (0.0, 0.0, 0.0, 0.0)


def _duel_add_scaled(base, scale, value):
    return (base[0] + scale * value[0],
            base[1] + scale * value[1],
            base[2] + scale * value[2],
            base[3] + scale * value[3])


def _duel_blend(expected, worst):
    weight = 1.0 - DUEL_WORST_WEIGHT
    return (weight * expected[0] + DUEL_WORST_WEIGHT * worst[0],
            weight * expected[1] + DUEL_WORST_WEIGHT * worst[1],
            weight * expected[2] + DUEL_WORST_WEIGHT * worst[2],
            weight * expected[3] + DUEL_WORST_WEIGHT * worst[3])


class _DuelDeadline(Exception):
    pass


class DuelSnapshot(object):
    __slots__ = ("match_id", "round_num", "state", "we_lead", "visible_color",
                 "exact_opponent_led_value", "exact_value_confident",
                 "our_remaining_mask", "opponent_remaining_mask",
                 "our_score", "opponent_score")

    def __init__(self, **kwargs):
        for key in self.__slots__:
            setattr(self, key, kwargs.get(key))

    @property
    def score_delta(self):
        return self.our_score - self.opponent_score

    @property
    def rounds_left(self):
        return duel_mask_count(self.our_remaining_mask)

    def decision_key(self):
        return (self.match_id, self.round_num, self.our_remaining_mask,
                self.opponent_remaining_mask, self.we_lead,
                self.exact_opponent_led_value, self.visible_color,
                self.our_score, self.opponent_score)


class DuelBaselineModels(object):
    """Deterministic baseline opponent models (versioned)."""

    def __init__(self, model_version="v1"):
        self.model_version = model_version

    def opponent_response(self, opponent_mask, our_color, score_delta, rounds_left):
        cards = duel_mask_cards(opponent_mask)
        if not cards:
            return []
        prob = 1.0 / len(cards)
        return [(b, prob) for b in cards]

    def opponent_lead(self, opponent_mask, score_delta, rounds_left):
        cards = duel_mask_cards(opponent_mask)
        if not cards:
            return []
        prob = 1.0 / len(cards)
        return [(b, prob) for b in cards]

    def next_leader(self, we_lead_now):
        return "them" if we_lead_now else "us"


class DuelTrainedModels(object):
    """Opponent models loaded from an offline-trained frequency table."""

    def __init__(self, data, model_version="trained-v1"):
        self.model_version = model_version
        self.response = data.get("opponent_response", {})
        self.lead = data.get("opponent_lead", {})

    @staticmethod
    def _round_bucket(rounds_left):
        if rounds_left >= 7:
            return "early"
        if rounds_left >= 4:
            return "mid"
        return "late"

    def _distribution(self, table, cards):
        legal = duel_mask_cards(cards)
        if not legal:
            return []
        total = 0
        counts = {}
        for card in legal:
            count = int(table.get(str(card), 0)) + 1  # Laplace smoothing
            counts[card] = count
            total += count
        return [(card, counts[card] / float(total)) for card in legal]

    def opponent_response(self, opponent_mask, our_color, score_delta, rounds_left):
        key = "%s|%d|%s" % (our_color, duel_mask_count(opponent_mask),
                            self._round_bucket(rounds_left))
        table = self.response.get(key, {})
        if not table:
            cards = duel_mask_cards(opponent_mask)
            if not cards:
                return []
            prob = 1.0 / len(cards)
            return [(b, prob) for b in cards]
        return self._distribution(table, opponent_mask)

    def opponent_lead(self, opponent_mask, score_delta, rounds_left):
        key = "%d|%s" % (duel_mask_count(opponent_mask),
                         self._round_bucket(rounds_left))
        table = self.lead.get(key, {})
        if not table:
            cards = duel_mask_cards(opponent_mask)
            if not cards:
                return []
            prob = 1.0 / len(cards)
            return [(b, prob) for b in cards]
        return self._distribution(table, opponent_mask)

    def next_leader(self, we_lead_now):
        return "them" if we_lead_now else "us"


def load_trained_duel_models():
    path = os.path.join(DIRECTORY, "yin_yang_duel_model.json")
    try:
        if not os.path.exists(path):
            return None
        with open(path, "rb") as source:
            data = source.read()
        if sys.version_info[0] != 2:
            data = data.decode("utf-8")
        return DuelTrainedModels(json.loads(data))
    except Exception:
        return None


class DuelSolver(object):
    def __init__(self, models=None):
        self.models = models or DuelBaselineModels()
        self.memo = {}

    def choose_move(self, snapshot, deadline):
        try:
            if snapshot.we_lead:
                value, card = self._choose_lead(snapshot, deadline)
                mode = "lead"
            elif (snapshot.exact_value_confident and
                  snapshot.exact_opponent_led_value is not None):
                value, card = self._choose_exact_follow(snapshot, deadline)
                mode = "exact_follow"
            else:
                value, card = self._choose_color_follow(snapshot, deadline)
                mode = "color_follow"
        except _DuelDeadline:
            return self._fallback(snapshot)
        if card is None or value is None:
            return self._fallback(snapshot)
        return {
            "card_value": card,
            "mode": mode,
            "win_probability": value[0],
            "loss_probability": -value[1],
            "expected_score_delta": value[2],
            "worst_case_utility": value[3],
            "model_version": self.models.model_version,
            "complete_search": True,
        }

    def warm(self, our_mask, opp_mask, score_delta, deadline):
        """Warm the memo by exploring the current match state (both leader
        cases) during non-pick states.  Does not return a decision."""
        rounds = duel_mask_count(our_mask)
        for leader in ("us", "them"):
            try:
                self._value((our_mask, opp_mask, score_delta, rounds, leader),
                            deadline)
            except _DuelDeadline:
                pass

    # --- recursion over the match ---

    def _value(self, state, deadline):
        our_mask, opp_mask, score_delta, rounds_left, leader = state
        if time.time() > deadline:
            raise _DuelDeadline()
        if rounds_left == 0:
            return terminal_duel_value(score_delta)
        key = (our_mask, opp_mask, score_delta, rounds_left, leader)
        cached = self.memo.get(key)
        if cached is not None:
            return cached
        if leader == "us":
            result = self._value_our_lead(state, deadline)
        else:
            result = self._value_their_lead(state, deadline)
        self.memo[key] = result
        return result

    def _value_our_lead(self, state, deadline):
        our_mask = state[0]
        best = None
        for a in duel_mask_cards(our_mask):
            value = self._value_our_lead_card(state, a, deadline)
            if best is None or value > best:
                best = value
        return best

    def _value_our_lead_card(self, state, a, deadline):
        our_mask, opp_mask, score_delta, rounds_left, _leader = state
        resp = self.models.opponent_response(opp_mask, duel_card_color(a),
                                             score_delta, rounds_left)
        expected = (0.0, 0.0, 0.0, 0.0)
        worst = None
        for b, prob in resp:
            value = self._advance(state, a, b, deadline)
            expected = _duel_add_scaled(expected, prob, value)
            if worst is None or value < worst:
                worst = value
        return _duel_blend(expected, worst)

    def _value_their_lead(self, state, deadline):
        our_mask, opp_mask, score_delta, rounds_left, _leader = state
        lead_dist = self.models.opponent_lead(opp_mask, score_delta, rounds_left)
        expected = (0.0, 0.0, 0.0, 0.0)
        worst = None
        for b, prob in lead_dist:
            value = self._value_their_lead_card(state, b, deadline)
            expected = _duel_add_scaled(expected, prob, value)
            if worst is None or value < worst:
                worst = value
        return _duel_blend(expected, worst)

    def _value_their_lead_card(self, state, b, deadline):
        our_mask = state[0]
        best = None
        for a in duel_mask_cards(our_mask):
            value = self._advance(state, a, b, deadline)
            if best is None or value > best:
                best = value
        return best

    def _advance(self, state, a, b, deadline):
        our_mask, opp_mask, score_delta, rounds_left, leader = state
        next_our = duel_mask_remove(our_mask, a)
        next_opp = duel_mask_remove(opp_mask, b)
        next_score = score_delta + round_score_delta(a, b)
        next_rounds = rounds_left - 1
        next_leader = self.models.next_leader(leader == "us")
        return self._value((next_our, next_opp, next_score, next_rounds, next_leader),
                           deadline)

    # --- decision entry points ---

    def _choose_lead(self, snapshot, deadline):
        best_value, best_card = None, None
        for a in duel_mask_cards(snapshot.our_remaining_mask):
            state = (snapshot.our_remaining_mask, snapshot.opponent_remaining_mask,
                     snapshot.score_delta, snapshot.rounds_left, "us")
            value = self._value_our_lead_card(state, a, deadline)
            if best_value is None or value > best_value or (
                    value == best_value and a < best_card):
                best_value, best_card = value, a
        return best_value, best_card

    def _choose_exact_follow(self, snapshot, deadline):
        b = snapshot.exact_opponent_led_value
        state = (snapshot.our_remaining_mask, snapshot.opponent_remaining_mask,
                 snapshot.score_delta, snapshot.rounds_left, "them")
        best_value, best_card = None, None
        for a in duel_mask_cards(snapshot.our_remaining_mask):
            value = self._advance(state, a, b, deadline)
            if best_value is None or value > best_value or (
                    value == best_value and a < best_card):
                best_value, best_card = value, a
        return best_value, best_card

    def _choose_color_follow(self, snapshot, deadline):
        color = snapshot.visible_color
        possible = duel_mask_cards(duel_mask_color(snapshot.opponent_remaining_mask, color))
        if not possible:
            raise _DuelDeadline()
        state = (snapshot.our_remaining_mask, snapshot.opponent_remaining_mask,
                 snapshot.score_delta, snapshot.rounds_left, "them")
        best_value, best_card = None, None
        for a in duel_mask_cards(snapshot.our_remaining_mask):
            expected = (0.0, 0.0, 0.0, 0.0)
            worst = None
            for b in possible:
                value = self._advance(state, a, b, deadline)
                expected = _duel_add_scaled(expected, 1.0 / len(possible), value)
                if worst is None or value < worst:
                    worst = value
            blended = _duel_blend(expected, worst)
            if best_value is None or blended > best_value or (
                    blended == best_value and a < best_card):
                best_value, best_card = blended, a
        return best_value, best_card

    # --- deterministic fallback ---

    def _fallback(self, snapshot):
        hand = duel_mask_cards(snapshot.our_remaining_mask)
        if not hand:
            return None
        if snapshot.we_lead:
            card = choose_duel_card_lead(hand, duel_mask_cards(snapshot.opponent_remaining_mask))
            mode = "fallback_lead"
        elif (snapshot.exact_value_confident and
              snapshot.exact_opponent_led_value is not None):
            card = choose_duel_card_follow(hand, snapshot.exact_opponent_led_value)
            mode = "fallback_exact"
        else:
            card = choose_duel_card(hand, snapshot.visible_color)
            mode = "fallback_color"
        return {
            "card_value": card,
            "mode": mode,
            "win_probability": None,
            "loss_probability": None,
            "expected_score_delta": None,
            "worst_case_utility": None,
            "model_version": self.models.model_version,
            "complete_search": False,
        }


class DuelRoundTracker(object):
    """Tracks mutable match state and converts client UI into a DuelSnapshot."""

    def __init__(self):
        self.match_id = 0
        self.window_identity = None
        self.last_state = None
        self.last_round = None
        self.opponent_played_mask = 0
        self.opponent_last = None
        self.opponent_round = None
        self.pending = None

    def on_window(self, window):
        if id(window) != self.window_identity:
            self.match_id += 1
            self.window_identity = id(window)
            self.last_state = None
            self.last_round = None
            self.opponent_played_mask = 0
            self.opponent_last = None
            self.opponent_round = None
            self.pending = None

    @staticmethod
    def read_mask(cards_dict, played):
        mask = 0
        valid = True
        for key, card in (cards_dict or {}).items():
            try:
                is_played = bool(getattr(card, "played", False))
                if is_played != played:
                    continue
                value = int(getattr(card, "value", key))
                if 0 <= value <= 8 and not (mask & (1 << value)):
                    mask |= 1 << value
                else:
                    valid = False
            except Exception:
                valid = False
        return mask, valid

    def observe_opponent(self, window):
        """Track the opponent's newly-played cards.  Returns (newly_values, exact)
        where exact is the led value when exactly one card appeared in an
        opponent-led, colour-matching state."""
        lead_info = getattr(window, "leadInfo", None) or {}
        we_lead = duel_we_lead(lead_info)
        round_num = lead_info.get("round", 0)
        if round_num != self.opponent_round:
            # A new round invalidates the previously-detected led card: a stale
            # value must never be reused as the exact led card of this round.
            self.opponent_round = round_num
            self.opponent_last = None
        played_mask, valid = self.read_mask(getattr(window, "opponentCards", None),
                                            played=True)
        if not valid:
            return [], None
        newly = played_mask & ~self.opponent_played_mask
        self.opponent_played_mask = played_mask
        newly_values = duel_mask_cards(newly)
        exact = None
        if len(newly_values) == 1 and not we_lead:
            value = newly_values[0]
            black = bool(lead_info.get("black", False))
            if (duel_card_color(value) == "black") == black:
                self.opponent_last = value
                exact = value
        return newly_values, exact

    def build_snapshot(self, window):
        lead_info = getattr(window, "leadInfo", None) or {}
        we_lead = duel_we_lead(lead_info)
        our_remaining, our_valid = self.read_mask(getattr(window, "playerCards", None),
                                                  played=False)
        opp_remaining, opp_valid = self.read_mask(getattr(window, "opponentCards", None),
                                                  played=False)
        if not (our_valid and opp_valid):
            return None
        our_count = duel_mask_count(our_remaining)
        opp_count = duel_mask_count(opp_remaining)
        if we_lead:
            if our_count != opp_count:
                return None
        else:
            # The opponent already led, so they hold one fewer unplayed card.
            if our_count != opp_count + 1:
                return None
        exact = None if we_lead else self.opponent_last
        return DuelSnapshot(
            match_id=self.match_id,
            round_num=lead_info.get("round", 0),
            state=getattr(window, "state", None),
            we_lead=we_lead,
            visible_color=(None if we_lead else
                           ("black" if lead_info.get("black", False) else "white")),
            exact_opponent_led_value=exact,
            exact_value_confident=(exact is not None),
            our_remaining_mask=our_remaining,
            opponent_remaining_mask=opp_remaining,
            our_score=int(getattr(window, "playerScore", 0) or 0),
            opponent_score=int(getattr(window, "opponentScore", 0) or 0),
        )

    def has_pending(self, key):
        return self.pending == key

    def mark_pending(self, key):
        self.pending = key

    def clear_pending(self):
        self.pending = None


# --- Twin Souls solver/tracker (pure, deterministic memory matching) ---
# The controller reads the client and clicks; the solver and tracker below are
# pure logic over primitive snapshots and fakeable window/card objects. No UI,
# disk, timing, or network access lives in these classes.

def enumerate_memory_cards(cards):
    """Normalize list/tuple/dict-shaped `cards` into sorted (index, card) pairs.

    Prefers a valid integer `card.index`; falls back to a numeric collection key
    or position. Returns (pairs, ok, reason).
    """
    if cards is None:
        return None, False, "no card collection"
    if isinstance(cards, dict):
        items = list(cards.items())
    elif isinstance(cards, (list, tuple)):
        items = list(enumerate(cards))
    else:
        return None, False, "unsupported card collection type"
    pairs = []
    seen = set()
    for key, card in items:
        index = None
        try:
            value = getattr(card, "index", None)
            if isinstance(value, INTEGER_TYPES) and not isinstance(value, bool):
                index = int(value)
        except Exception:
            index = None
        if index is None:
            if isinstance(key, INTEGER_TYPES) and not isinstance(key, bool):
                index = int(key)
        if index is None:
            return None, False, "card without an integer index"
        if index in seen:
            return None, False, "duplicate card index %d" % index
        seen.add(index)
        pairs.append((index, card))
    pairs.sort()
    return pairs, True, None


def normalize_memory_face(raw_face, visible):
    """Return the face value when a card is proven revealed/matched, else None.

    A face value of zero is preserved (it is not assumed to be the hidden
    sentinel); visibility comes from the card/open state, not the face value.
    """
    if not visible:
        return None
    try:
        return int(raw_face)
    except (TypeError, ValueError):
        return None


def classify_memory_state(raw_state):
    """Map a raw window.state value to a semantic Twin Souls state.

    The client's numeric idle/playing/finish constants are not yet verified by a
    diagnostic trace, so numeric states map to UNKNOWN instead of being guessed.
    String states are matched conservatively. Pin the numeric mapping only after
    a live observation establishes the constants (see DiagnosticTwinSouls).
    """
    if raw_state is None:
        return TWIN_SOULS_STATE_UNKNOWN
    if isinstance(raw_state, (str, unicode)):
        lowered = raw_state.lower()
        if "play" in lowered or "pick" in lowered or "turn" in lowered:
            return TWIN_SOULS_STATE_PLAYING
        if ("finish" in lowered or "result" in lowered or
                "end" in lowered or "win" in lowered):
            return TWIN_SOULS_STATE_FINISHING
        if "idle" in lowered or "cooldown" in lowered or "wait" in lowered:
            return TWIN_SOULS_STATE_IDLE
        return TWIN_SOULS_STATE_UNKNOWN
    return TWIN_SOULS_STATE_UNKNOWN


def resolve_minigame_owner(duel_enabled, duel_owns, duel_startable,
                           twin_souls_enabled, twin_souls_owns):
    """Return the single minigame allowed to act this update cycle.

    A controller with an active session or pending request (`*_owns`) keeps the
    slot until it becomes idle/disabled. An enabled duel additionally claims the
    slot while it is idle-but-startable (off cooldown and below its daily limit)
    so it can start a new duel. `duel_enabled` alone never claims the slot: a
    duel that is idle and cannot act (cooldown, daily limit, or already
    finished) yields to Twin Souls. When neither controller owns the slot the
    deterministic priority still favours Yin Yang Duel (a startable duel wins
    over an idle Twin Souls).
    """
    if duel_owns:
        return "duel"
    if twin_souls_owns:
        return "twin_souls"
    if duel_enabled and duel_startable:
        return "duel"
    if twin_souls_enabled:
        return "twin_souls"
    return None


def duel_result_continue_member(window):
    """Return (name, callable) for the duel result-screen continue handler.

    The exact handler is reverse-engineered and unverified against the current
    game build, so we try the known name-mangled candidates first and then any
    callable member whose name mentions a result/continue/confirm action. Used
    by `_DuelCloseResult` so a wrong guess degrades to a discovered member or a
    `Close()` fallback instead of leaving the result screen stuck open.
    """
    for name in YINYANG_DUEL_RESULT_CONTINUE_MEMBERS:
        member = getattr(window, name, None)
        if callable(member):
            return name, member
    for name in dir(window):
        if name.startswith("__") and name.endswith("__"):
            continue
        lowered = name.lower()
        if not any(token in lowered
                   for token in ("result", "continue", "confirm")):
            continue
        member = getattr(window, name, None)
        if callable(member):
            return name, member
    return None, None


def memory_known_closed_mate(knowledge, face, snapshot, excluding):
    """Return the lowest closed/selectable unmatched mate of `face`, else None."""
    if face is None:
        return None
    best = None
    for cell in knowledge.unmatched_cells_by_face.get(face, ()):
        if cell == excluding:
            continue
        if cell in snapshot.matched_cells:
            continue
        if cell in snapshot.open_cells:
            continue
        if cell not in snapshot.selectable_cells:
            continue
        if best is None or cell < best:
            best = cell
    return best


def memory_unknown_closed_selectable(snapshot, knowledge, excluding=None):
    """Return sorted unknown, unmatched, closed/selectable cell indices."""
    result = []
    for cell in snapshot.selectable_cells:
        if cell in snapshot.matched_cells:
            continue
        if cell in snapshot.open_cells:
            continue
        if cell in knowledge.known_face_by_cell:
            continue
        if excluding is not None and cell == excluding:
            continue
        result.append(cell)
    result.sort()
    return result


def memory_complete_known_pairs(knowledge, snapshot):
    """Return sorted (face, first, second) tuples for complete closed pairs."""
    pairs = []
    for face, cells in knowledge.unmatched_cells_by_face.items():
        closed = []
        for cell in cells:
            if cell in snapshot.matched_cells:
                continue
            if cell in snapshot.open_cells:
                continue
            if cell not in snapshot.selectable_cells:
                continue
            closed.append(cell)
        if len(closed) >= 2:
            closed.sort()
            pairs.append((face, closed[0], closed[1]))
    pairs.sort(key=lambda item: (item[1], item[2]))
    return pairs


class MemoryBoardSnapshot(object):
    """Immutable-by-convention view of one coherent YinYangMemoryWindow read."""

    __slots__ = ("board_id", "window_id", "state", "phase", "cell_count",
                 "pair_count", "pairs_found", "time_remaining",
                 "bonus_remaining", "awaiting_flip", "busy", "open_cells",
                 "matched_cells", "visible_faces", "selectable_cells",
                 "plays_used", "plays_max", "plays_used_hwid", "plays_max_hwid",
                 "generation_signature")

    def __init__(self, **kwargs):
        for key in self.__slots__:
            setattr(self, key, kwargs.get(key))

    def observation_key(self):
        return (self.state, self.phase, self.awaiting_flip, self.pairs_found,
                self.open_cells, tuple(sorted(self.matched_cells)),
                tuple(sorted(self.visible_faces.items())))


class MemoryKnowledge(object):
    """Primitive solver input: remembered faces and unmatched face indexes."""

    __slots__ = ("known_face_by_cell", "unmatched_cells_by_face")

    def __init__(self):
        self.known_face_by_cell = {}
        self.unmatched_cells_by_face = {}


class MemorySolver(object):
    """Deterministic perfect-memory card matcher. Pure function of snapshot."""

    def choose_cell(self, snapshot, knowledge):
        decision = {
            "cell_index": None,
            "mode": TWIN_SOULS_MODE_WAIT,
            "face": None,
            "mate_cell": None,
            "known_pair_count": 0,
            "unknown_cell_count": 0,
            "reason": "",
        }
        pairs = memory_complete_known_pairs(knowledge, snapshot)
        unknown = memory_unknown_closed_selectable(snapshot, knowledge)
        decision["known_pair_count"] = len(pairs)
        decision["unknown_cell_count"] = len(unknown)

        if snapshot.state != TWIN_SOULS_STATE_PLAYING:
            decision["reason"] = "not playing"
            return decision
        if snapshot.awaiting_flip or snapshot.busy:
            decision["reason"] = "client busy"
            return decision

        open_unmatched = [c for c in snapshot.open_cells
                          if c not in snapshot.matched_cells]
        if len(open_unmatched) > 1:
            decision["reason"] = "two cards resolving"
            return decision

        if len(open_unmatched) == 1:
            first = open_unmatched[0]
            face = knowledge.known_face_by_cell.get(first)
            mate = memory_known_closed_mate(knowledge, face, snapshot,
                                            excluding=first)
            if mate is not None:
                decision.update({"cell_index": mate,
                                 "mode": TWIN_SOULS_MODE_KNOWN_MATE,
                                 "face": face, "mate_cell": first,
                                 "reason": "known mate of open card"})
                return decision
            if unknown:
                decision.update({"cell_index": unknown[0],
                                 "mode": TWIN_SOULS_MODE_EXPLORE,
                                 "reason": "explore next to open card"})
                return decision
            decision["reason"] = "waiting for a legal second card"
            return decision

        if pairs:
            face, first, second = pairs[0]
            decision.update({"cell_index": first,
                             "mode": TWIN_SOULS_MODE_COMPLETE_PAIR,
                             "face": face, "mate_cell": second,
                             "reason": "complete a known pair"})
            return decision

        if unknown:
            decision.update({"cell_index": unknown[0],
                             "mode": TWIN_SOULS_MODE_EXPLORE,
                             "reason": "explore an unseen cell"})
            return decision

        decision["reason"] = "no stable selectable cell"
        return decision


class MemoryBoardTracker(object):
    """Owns one board generation's learned faces, matches, and pending requests.

    It converts the mutable runtime window into a MemoryBoardSnapshot, learns
    faces only from authoritative (revealed/matched) observations, retains
    mismatch faces after cards close, and clears knowledge on a confirmed new
    board or window.
    """

    def __init__(self):
        self.board_id = 0
        self.window_identity = None
        self.generation_signature = None
        self.known_face_by_cell = {}
        self.known_cells_by_face = {}
        self.matched_cells = set()
        self.last_open_cells = ()
        self.last_pairs_found = None
        self.last_state = None
        self.last_observation_key = None
        self.last_progress_time = 0.0
        self.last_error = None
        self.pending_flip = None
        self.pending_start = False

    def on_window(self, window):
        identity = id(window)
        if identity != self.window_identity:
            self.board_id += 1
            self.window_identity = identity
            self._clear_knowledge()

    def _clear_knowledge(self):
        self.generation_signature = None
        self.known_face_by_cell = {}
        self.known_cells_by_face = {}
        self.matched_cells = set()
        self.last_open_cells = ()
        self.last_pairs_found = None
        self.last_state = None
        self.last_observation_key = None
        self.last_progress_time = 0.0
        self.last_error = None
        self.pending_flip = None
        self.pending_start = False

    @staticmethod
    def _card_busy(card):
        is_busy = getattr(card, "IsBusy", None)
        if not callable(is_busy):
            return False
        try:
            return bool(is_busy())
        except Exception:
            return True  # exceptions are treated as busy

    @staticmethod
    def _call_float(window, method_name):
        method = getattr(window, method_name, None)
        if not callable(method):
            return None
        try:
            value = method()
        except Exception:
            return None
        if isinstance(value, (tuple, list)):
            value = value[0] if value else None
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _normalize_open_cells(window, pairs):
        open_cells = getattr(window, "openCells", None)
        if not open_cells:
            return ()
        card_by_id = dict((id(card), index) for index, card in pairs)
        result = set()
        if isinstance(open_cells, dict):
            items = list(open_cells.keys())
        else:
            items = list(open_cells)
        for item in items:
            if isinstance(item, INTEGER_TYPES) and not isinstance(item, bool):
                result.add(int(item))
            else:
                index = card_by_id.get(id(item))
                if index is not None:
                    result.add(index)
        return tuple(sorted(result))

    def build_snapshot(self, window, now):
        cards = getattr(window, "cards", None)
        pairs, ok, reason = enumerate_memory_cards(cards)
        if not ok:
            return None, reason
        raw_state = getattr(window, "state", None)
        state = classify_memory_state(raw_state)
        phase = getattr(window, "phase", None)
        cell_count = len(pairs)
        pair_count = int(getattr(window, "faceCount", 0) or 0)
        if pair_count <= 0:
            pair_count = cell_count // 2
        pairs_found = int(getattr(window, "pairsFound", 0) or 0)
        awaiting_flip = bool(getattr(window, "awaitingFlip", False))
        if state == TWIN_SOULS_STATE_UNKNOWN:
            state = self._resolve_unknown_state(window, raw_state,
                                                pair_count, pairs_found)

        open_cells = self._normalize_open_cells(window, pairs)
        open_set = set(open_cells)
        matched = set()
        visible_faces = {}
        busy_cells = []
        for index, card in pairs:
            card_matched = bool(getattr(card, "matched", False))
            if card_matched:
                matched.add(index)
            card_busy = self._card_busy(card)
            busy_cells.append(card_busy)
            face = normalize_memory_face(
                getattr(card, "face", None),
                (index in open_set) or card_matched)
            if face is not None:
                visible_faces[index] = face

        selectable = []
        for index, card in pairs:
            if index in matched or index in open_set:
                continue
            if self._card_busy(card):
                continue
            selectable.append(index)
        selectable.sort()

        busy = awaiting_flip or any(busy_cells)
        generation_signature = tuple(id(card) for _, card in pairs)

        return MemoryBoardSnapshot(
            board_id=self.board_id,
            window_id=self.window_identity,
            state=state,
            phase=phase,
            cell_count=cell_count,
            pair_count=pair_count,
            pairs_found=pairs_found,
            time_remaining=self._call_float(window, "GetTimeRemaining"),
            bonus_remaining=self._call_float(window, "GetBonusRemaining"),
            awaiting_flip=awaiting_flip,
            busy=busy,
            open_cells=open_cells,
            matched_cells=frozenset(matched),
            visible_faces=dict(visible_faces),
            selectable_cells=tuple(selectable),
            plays_used=int(getattr(window, "playsUsed", 0) or 0),
            plays_max=int(getattr(window, "playsMax", 0) or 0),
            plays_used_hwid=int(getattr(window, "playsUsedHwid", 0) or 0),
            plays_max_hwid=int(getattr(window, "playsMaxHwid", 0) or 0),
            generation_signature=generation_signature,
        ), None

    def _resolve_unknown_state(self, window, raw_state, pair_count, pairs_found):
        """Map an unverified numeric `state` to a semantic state.

        The client's integer idle/playing/finish constants are not pinned, so we
        infer the phase from signals that are observable and reliable: a
        completed board (all pairs found) is finishing, a nonzero cooldown is
        idle, an in-flight start (`openPending`) is still idle, and a nonzero
        state (or one of our own pending requests) is playing. Falls back to
        idle, which is the safe default for an unstarted board.
        """
        if pair_count > 0 and pairs_found >= pair_count:
            return TWIN_SOULS_STATE_FINISHING
        cooldown = self._call_float(window, "GetCooldownRemaining")
        if cooldown is not None and cooldown > 0:
            return TWIN_SOULS_STATE_IDLE
        if bool(getattr(window, "openPending", False)):
            return TWIN_SOULS_STATE_IDLE
        if isinstance(raw_state, INTEGER_TYPES) and raw_state != 0:
            return TWIN_SOULS_STATE_PLAYING
        if self.pending_start or self.pending_flip:
            return TWIN_SOULS_STATE_PLAYING
        return TWIN_SOULS_STATE_IDLE

    def _detect_reset(self, snapshot):
        if self.generation_signature is None:
            return False
        if snapshot.generation_signature != self.generation_signature:
            return True
        if (self.last_pairs_found is not None and
                snapshot.pairs_found < self.last_pairs_found):
            return True
        return False

    def _reset_board(self):
        self.board_id += 1
        self._clear_knowledge()

    def _learn(self, snapshot, now):
        if snapshot.observation_key() != self.last_observation_key:
            self.last_observation_key = snapshot.observation_key()
            self.last_progress_time = now
        for cell, face in snapshot.visible_faces.items():
            previous = self.known_face_by_cell.get(cell)
            if previous is not None and previous != face:
                self.last_error = ("contradictory face at cell %d (%s vs %s)" %
                                   (cell, previous, face))
                continue
            self.known_face_by_cell[cell] = face
            if cell not in snapshot.matched_cells:
                self.known_cells_by_face.setdefault(face, set()).add(cell)
        for cell in snapshot.matched_cells:
            self.matched_cells.add(cell)
            face = self.known_face_by_cell.get(cell)
            if face is not None:
                bucket = self.known_cells_by_face.get(face)
                if bucket is not None:
                    bucket.discard(cell)
        self.last_open_cells = snapshot.open_cells
        self.last_pairs_found = snapshot.pairs_found
        self.last_state = snapshot.state
        self.generation_signature = snapshot.generation_signature

    def observe(self, window, now):
        self.on_window(window)
        snapshot, error = self.build_snapshot(window, now)
        if snapshot is None:
            self.last_error = error
            return None, error
        if self._detect_reset(snapshot):
            self._reset_board()
            # Rebuild with the corrected board id/generation.
            snapshot, error = self.build_snapshot(window, now)
            if snapshot is None:
                self.last_error = error
                return None, error
        self._learn(snapshot, now)
        return snapshot, None

    def knowledge(self):
        result = MemoryKnowledge()
        result.known_face_by_cell = dict(self.known_face_by_cell)
        result.unmatched_cells_by_face = dict(
            (face, set(cells))
            for face, cells in self.known_cells_by_face.items())
        return result

    # --- pending flip / start ---

    def mark_pending_flip(self, cell, snapshot):
        self.pending_flip = {
            "board_id": snapshot.board_id,
            "cell": cell,
            "request_time": time.time(),
            "observation_key": snapshot.observation_key(),
        }

    def has_pending_flip(self):
        return self.pending_flip is not None

    def resolve_pending_flip(self, snapshot, now):
        pending = self.pending_flip
        if pending is None:
            return False
        if pending["board_id"] != snapshot.board_id:
            self.pending_flip = None
            return True
        cell = pending["cell"]
        if cell in snapshot.open_cells:
            self.pending_flip = None
            return True
        if snapshot.observation_key() != pending["observation_key"]:
            self.pending_flip = None
            return True
        if snapshot.state != TWIN_SOULS_STATE_PLAYING:
            self.pending_flip = None
            return True
        return False

    def mark_pending_start(self):
        self.pending_start = True

    def has_pending_start(self):
        return self.pending_start

    def clear_pending_start(self):
        self.pending_start = False

    def clear_pending_flip(self):
        self.pending_flip = None


class MemoryActionAdapter(object):
    """Dispatch boundary for Twin Souls UI actions.

    Twin Souls is a UI minigame, like Yin Yang Duel and the reaction game, so its
    start and flips go through the same proven route: record a synthetic click,
    then invoke the client's own UI handler directly (no world projection, no
    cursor move, no audited world-click path).
    """

    def dispatch_start(self, window):
        start = getattr(window, "_YinYangMemoryWindow__OnStartClicked", None)
        if not callable(start):
            return False
        try:
            start()
            return True
        except Exception:
            return False

    def dispatch_flip(self, card):
        if card is None:
            return False
        click = getattr(card, "OnMouseLeftButtonDown", None)
        if not callable(click):
            return False
        try:
            click()
            return True
        except Exception:
            return False


def disk_log(message):
    now = time.time()
    whole = int(now)
    milliseconds = int((now - whole) * 1000.0)
    line = "%s.%03d %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S",
                                             time.localtime(whole)),
                               milliseconds, ascii_text(message))
    data = line if sys.version_info[0] == 2 else line.encode("ascii")
    fd = os.open(LOG, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o644)
    try:
        offset = 0
        while offset < len(data):
            written = os.write(fd, data[offset:])
            if written <= 0:
                raise IOError("log write failed")
            offset += written
    finally:
        os.close(fd)


def read_config_file():
    values = {}
    try:
        with open(CONFIG, "rb") as source:
            data = source.read()
        if sys.version_info[0] != 2:
            data = data.decode("ascii")
        for raw_line in data.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    except IOError:
        pass
    return values


def write_config_file(values):
    keys = sorted(values)
    text = "\n".join("%s=%s" % (key, ascii_text(values[key])) for key in keys) + "\n"
    data = text if sys.version_info[0] == 2 else text.encode("ascii")
    fd = os.open(CONFIG, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o644)
    try:
        offset = 0
        while offset < len(data):
            written = os.write(fd, data[offset:])
            if written <= 0:
                raise IOError("config write failed")
            offset += written
    finally:
        os.close(fd)


def visible_vids():
    if time.time() - os.stat(SNAPSHOT).st_mtime > 3.0:
        raise IOError("entity snapshot is stale")
    with open(SNAPSHOT, "rb") as source:
        lines = source.readlines()
    if not lines:
        raise IOError("entity snapshot is empty")
    header = lines[0].strip()
    if sys.version_info[0] != 2:
        header = header.decode("ascii")
    if header != "PID %d" % os.getpid():
        raise IOError("entity snapshot belongs to another process")
    return [int(line) for line in lines[1:] if line.strip().isdigit()]


def make_text(parent, x, y, message):
    label = ui.TextLine()
    label.SetParent(parent)
    label.SetPosition(x, y)
    label.SetText(message)
    label.Show()
    return label


def limit_text(label, width):
    try:
        label.SetLimitWidth(width)
    except Exception:
        pass
    return label


def make_button(parent, x, text, callback, y=43):
    button = ui.Button()
    button.SetParent(parent)
    button.SetPosition(x, y)
    button.SetUpVisual("d:/ymir work/ui/public/middle_button_01.sub")
    button.SetOverVisual("d:/ymir work/ui/public/middle_button_02.sub")
    button.SetDownVisual("d:/ymir work/ui/public/middle_button_03.sub")
    button.SetText(text)
    button.SetEvent(callback)
    button.Show()
    return button


def make_bar(parent, x, y, width, height, color):
    bar = ui.Bar()
    bar.SetParent(parent)
    bar.SetPosition(x, y)
    bar.SetSize(width, height)
    bar.SetColor(color)
    bar.Show()
    return bar


def make_page(parent, x, y, width, height):
    page = ui.Window()
    page.SetParent(parent)
    page.SetPosition(x, y)
    page.SetSize(width, height)
    page.Show()
    return page


def make_radar_dot(parent, x, y, size, color, fallback):
    try:
        dot = ui.Bar()
        dot.SetParent(parent)
        dot.SetPosition(x, y)
        dot.SetSize(size, size)
        dot.SetColor(color)
    except Exception:
        dot = ui.TextLine()
        dot.SetParent(parent)
        dot.SetPosition(x, y)
        dot.SetText(fallback)
    dot.Show()
    return dot


def radar_player_reach_offsets(player_position, anchor_position, radius):
    """Drawing-only player-radius boundary clipped to the anchored circle."""
    if anchor_position is None or radius <= 0:
        return ()  # In following mode the existing blue ring is the same circle.
    dx = player_position[0] - anchor_position[0]
    dy = player_position[1] - anchor_position[1]
    radius2 = float(radius) ** 2
    offsets = []
    for index in range(96):
        angle = 2.0 * math.pi * index / 96.0
        x = dx + radius * math.cos(angle)
        y = dy + radius * math.sin(angle)
        # The tiny tolerance concerns outline rounding only, not selection.
        if x * x + y * y <= radius2 * (1.0 + 1e-12):
            offsets.append((x, y))
    return tuple(offsets)


class GameplayPhaseGuard(object):
    """Observe registrations of the client's existing phase UI windows."""

    observer_version = 3

    def __init__(self, original=None, original_disconnect=None):
        self.owner = None
        self.current_phase = None
        self.original = original or net.SetPhaseWindow
        self.original_disconnect = original_disconnect or net.Disconnect

        def phase_window(*args, **kwargs):
            result = self.original(*args, **kwargs)
            # SetPhaseWindow registers a UI object for a phase index; it does
            # not change the native network phase.  Ignore unregister calls.
            if len(args) >= 2 and args[1] is not None:
                try:
                    self.current_phase = int(args[0])
                    owner = self.owner
                    if owner is not None:
                        owner.OnGameplayPhaseWindowRegistered(
                            self.current_phase, args[1])
                except Exception:
                    # A phase observer must never break the client's own transition.
                    pass
            return result

        self.phase_window = phase_window
        net.SetPhaseWindow = self.phase_window

        def disconnect(*args, **kwargs):
            owner = self.owner
            if owner is not None:
                try:
                    owner.OnPythonNetDisconnect(args, kwargs,
                                                traceback.extract_stack()[:-1])
                except Exception:
                    pass
            return self.original_disconnect(*args, **kwargs)

        self.disconnect = disconnect
        net.Disconnect = self.disconnect

    def SetOwner(self, owner):
        self.owner = owner


def get_gameplay_phase_guard():
    guard = getattr(__main__, "_lirin_gameplay_phase_guard", None)
    if (guard is None or not hasattr(guard, "SetOwner") or
            getattr(guard, "observer_version", 0) != GameplayPhaseGuard.observer_version):
        original = getattr(guard, "original", net.SetPhaseWindow)
        original_disconnect = getattr(guard, "original_disconnect", net.Disconnect)
        guard = GameplayPhaseGuard(original, original_disconnect)
        __main__._lirin_gameplay_phase_guard = guard
    return guard


class ScannerWatcher(ui.Window):
    """Keep scanning and the hotkey alive while the panel is hidden."""

    def __init__(self, panel):
        ui.Window.__init__(self)
        self.panel = panel
        self.SetPosition(-100, -100)
        self.SetSize(1, 1)
        self.Show()

    def OnUpdate(self):
        self.panel.PollHotkey()
        self.panel.OnUpdate()


class MetinScanner(ui.BoardWithTitleBar):
    def __init__(self):
        ui.BoardWithTitleBar.__init__(self)
        self.feature_version = FEATURE_VERSION
        self.hunter_observer = get_hunter_observer()
        self.AddFlag("movable")
        self.AddFlag("float")
        self.SetSize(620, 555)
        try:
            panel_x = max(0, min(40, int(wndMgr.GetScreenWidth()) - 620))
            panel_y = max(0, min(80, int(wndMgr.GetScreenHeight()) - 555))
        except Exception:
            panel_x, panel_y = 40, 80
        self.SetPosition(panel_x, panel_y)
        self.SetTitleName("Lirin Feature Panel")
        self.SetCloseEvent(self.MinimizePanel)
        self.running = False
        self.anchor_position = None
        self.hotkey_down = False
        self.hunter_enabled = False
        self.anchor_channel = None
        self.anchor_map = None
        self.boss_vnum = None
        self.boss_name = None
        self.boss_position = None
        self.boss_map = None
        self.boss_mark_channel = None
        self.boss_enabled = False
        self.boss_state = BOSS_IDLE
        self.boss_timer = None
        self.boss_channels = []
        self.boss_channel_index = 0
        self.boss_target_channel = None
        self.boss_state_started = 0.0
        self.boss_deadline = 0.0
        self.boss_missing_since = None
        self.boss_target_vid = 0
        self.boss_target_missing_since = None
        self.boss_timer_armed = True
        self.boss_saved_hunter_enabled = False
        self.boss_saved_queue_enabled = False
        self.boss_modes_paused = False
        self.boss_saved_mouse_func = None
        self.boss_switch_dialog = None
        self.boss_returning = False
        self.boss_return_best_distance = None
        self.boss_return_last_progress = 0.0
        self.boss_return_move_sent = False
        self.boss_last_error = None
        self.boss_next_poll = 0.0
        self.reaction_enabled = True
        self.reaction_window = None
        self.reaction_next_poll = 0.0
        self.reaction_started = False
        self.reaction_last_ball = None
        self.reaction_pending_ball = None
        self.reaction_click_at = 0.0
        self.reaction_last_error = None
        self.reaction_pause_started = None
        self.reaction_native_paused = False
        self.reaction_resume_token = None
        self.reaction_saved_hunter_enabled = False
        self.reaction_saved_queue_enabled = False
        self.reaction_saved_boss_attack = False
        self.yinyang_duel_enabled = False
        self.yinyang_duel_window = None
        self.yinyang_duel_next_poll = 0.0
        self.yinyang_duel_last_error = None
        self.yinyang_duel_debug = None
        self.yinyang_duel_stall = None
        self.yinyang_duel_solver = DuelSolver(
            load_trained_duel_models() or DuelBaselineModels())
        self.yinyang_duel_tracker = DuelRoundTracker()
        self.yinyang_duel_last_scores = None
        self.yinyang_duel_last_state = None
        self.twin_souls_enabled = False
        self.twin_souls_window = None
        self.twin_souls_next_poll = 0.0
        self.twin_souls_discover_at = 0.0
        self.twin_souls_last_error = None
        self.twin_souls_last_status = None
        self.twin_souls_last_state = None
        self.twin_souls_last_board = None
        self.twin_souls_last_finished_board = None
        self.twin_souls_tracker = MemoryBoardTracker()
        self.twin_souls_solver = MemorySolver()
        self.twin_souls_adapter = MemoryActionAdapter()
        self.twin_souls_trace_key = None
        self.yinyang_duel_result_closed = True
        self.yinyang_duel_result_close_at = 0.0
        self.player_next_poll = 0.0
        self.last_player_position = None
        self.gameplay_phase = None
        self.gameplay_available = True
        self.gameplay_next_check = 0.0
        self.gameplay_stopped = False
        self._game_window = None
        pair_enabled = recorder_pair_experiment_enabled()
        self.hunter_gateway = HunterQueueGateway(
            self.hunter_observer, player,
            recorder_pair_enabled=pair_enabled,
            recorder_pair=(get_recorder_pair_experiment() if pair_enabled else None),
            log=self._hunter_log)
        self.hunter_selector = HunterCandidateSelector(player, chr, nonplayer)
        self.hunter_controller = HunterController(
            self.hunter_gateway, self.hunter_selector,
            clock=hunter_now_ms,
            gameplay_available=self.IsGameplayAvailable,
            log=self._hunter_log,
            capacity_limit=HUNTER_LIMIT,
            radius_getter=lambda: self.radius,
            anchor_getter=lambda: self.anchor_position,
        )
        self.hunter_audit = HunterAuditObserver(
            self.hunter_gateway, hunter_now_ms, log=self._hunter_log, enabled=True)
        self.config_autoload = False
        self.radius = DEFAULT_RADIUS
        self.manual_queue_logger = ManualQueueLogger(
            self.hunter_gateway,
            hunter_now_ms,
            MANUAL_QUEUE_LOG,
            MANUAL_QUEUE_ENABLE,
            FEATURE_VERSION,
            context_provider=self._manual_queue_context,
            metadata_path=MANUAL_QUEUE_METADATA,
            report_error=self._manual_queue_log_error,
        )
        self.next_scan = 0.0
        self.last_radius_error = None
        self.last_scan_error = None
        self.lines = []
        try:
            panel_color = ui.GenerateColor(0.13, 0.16, 0.20, 0.96)
            separator_color = ui.GenerateColor(0.21, 0.25, 0.30, 1.0)
            accent_color = ui.GenerateColor(0.51, 0.71, 0.87, 1.0)
        except Exception:
            panel_color = 0xF5222A34
            separator_color = 0xFF35404D
            accent_color = 0xFF82B6DE

        self.toolbar_separator = make_bar(self, 10, 73, 600, 1, separator_color)
        self.radius_label = make_text(self, 15, 47, "Radius:")
        self.radius_slot = ui.SlotBar()
        self.radius_slot.SetParent(self)
        self.radius_slot.SetPosition(70, 42)
        self.radius_slot.SetSize(90, 22)
        self.radius_slot.Show()
        self.radius_edit = ui.EditLine()
        self.radius_edit.SetParent(self.radius_slot)
        self.radius_edit.SetPosition(6, 3)
        self.radius_edit.SetSize(75, 18)
        self.radius_edit.SetMax(5)
        self.radius_edit.SetNumberMode()
        self.radius_edit.SetText(str(DEFAULT_RADIUS))
        self.radius_edit.Show()
        self.start_button = make_button(self, 178, "Start", self.Start)
        button_width, button_height = self.GetWidgetSize(self.start_button, 88, 21)
        self.native_button_size = (button_width, button_height)
        self.stop_button = make_button(
            self, 178 + button_width + 8, "Stop farming", self.Stop)
        state_x = 178 + (button_width + 8) * 2
        self.state_label = limit_text(
            make_text(self, state_x, 47, "Stopped. Set radius, then click Start."),
            max(40, 605 - state_x))

        self.farming_tab_button = make_button(
            self, 15, "Farming", self.ShowFarmingTab, 79)
        self.minigames_tab_button = make_button(
            self, 15 + button_width + 8, "Minigames", self.ShowMinigamesTab, 79)
        self.activity_tab_button = make_button(
            self, 15 + (button_width + 8) * 2, "Activity", self.ShowActivityTab, 79)
        self.tab_indicator = make_bar(self, 15, 102, button_width, 2, accent_color)
        self.tabs_separator = make_bar(self, 10, 105, 600, 1, separator_color)

        self.farming_page = make_page(self, 0, 106, 620, 410)
        self.minigames_page = make_page(self, 0, 106, 620, 410)
        self.activity_page = make_page(self, 0, 106, 620, 410)
        self.tab_pages = {
            "farming": self.farming_page,
            "minigames": self.minigames_page,
            "activity": self.activity_page,
        }
        self.tab_buttons = {
            "farming": self.farming_tab_button,
            "minigames": self.minigames_tab_button,
            "activity": self.activity_tab_button,
        }
        self.tab_positions = {
            "farming": 15,
            "minigames": 15 + button_width + 8,
            "activity": 15 + (button_width + 8) * 2,
        }
        self.active_tab = None

        self.farming_hunter_card = make_bar(
            self.farming_page, 12, 10, 300, 120, panel_color)
        self.farming_boss_card = make_bar(
            self.farming_page, 12, 142, 300, 242, panel_color)
        self.farming_radar_card = make_bar(
            self.farming_page, 324, 10, 282, 374, panel_color)
        self.hunter_section_title = make_text(
            self.farming_page, 22, 20, "METIN FARMING")
        self.hunter_title = make_text(self.farming_page, 22, 47, "Metin Hunter")
        self.hunter_button = make_button(
            self.farming_page, 302 - button_width, "OFF",
            self.ToggleMetinHunter, 42)
        self.hunter_label = limit_text(
            make_text(self.farming_page, 22, 75, "Queue: idle"), 280)
        self.boss_section_title = make_text(
            self.farming_page, 22, 154, "BOSS SWEEP")
        self.boss_title = make_text(self.farming_page, 22, 181, "Boss Sweep")
        self.boss_label = limit_text(
            make_text(self.farming_page, 22, 204,
                      "Select a boss, then mark its spot"), 280)
        self.boss_mark_button = make_button(
            self.farming_page, 22, "Mark Boss", self.MarkBoss, 232)
        self.boss_button = make_button(
            self.farming_page, 22 + button_width + 8, "OFF",
            self.ToggleBossSweep, 232)

        self.radar_label = limit_text(
            make_text(self.farming_page, 335, 20,
                      "Local map: radius %d units" % self.radius), 260)
        self.activity_card = make_bar(
            self.activity_page, 12, 10, 594, 374, panel_color)
        self.activity_title = make_text(
            self.activity_page, 22, 22, "RECENT ACTIVITY - LAST 8 EVENTS")
        self.log_labels = []
        for index in range(8):
            label = make_text(self.activity_page, 24, 57 + index * 38, "")
            self.log_labels.append(limit_text(label, 568))
        self.radar_center = (465, 173)
        self.radar_pixels = 112
        try:
            background_color = ui.GenerateColor(0.08, 0.14, 0.18, 0.92)
            grid_color = ui.GenerateColor(0.25, 0.34, 0.39, 0.7)
            ring_color = ui.GenerateColor(0.30, 0.72, 1.0, 1.0)
            player_color = ui.GenerateColor(1.0, 0.90, 0.20, 1.0)
            metin_color = ui.GenerateColor(1.0, 0.25, 0.20, 1.0)
            other_color = ui.GenerateColor(0.72, 0.85, 0.85, 1.0)
            outside_color = ui.GenerateColor(0.45, 0.45, 0.45, 1.0)
            reach_color = ui.GenerateColor(0.25, 1.0, 0.40, 1.0)
        except Exception:
            background_color, grid_color = 0xEE15242E, 0xAA405762
            ring_color, player_color = 0xFF55AAFF, 0xFFFFFF33
            metin_color, other_color = 0xFFFF4433, 0xFFBBDDDD
            outside_color, reach_color = 0xFF737373, 0xFF40FF66
        self.map_background = ui.Bar()
        self.map_background.SetParent(self.farming_page)
        self.map_background.SetPosition(335, 43)
        self.map_background.SetSize(260, 260)
        self.map_background.SetColor(background_color)
        self.map_background.Show()
        self.map_grid = []
        for x in (380, 422, 465, 508, 550):
            bar = ui.Bar()
            bar.SetParent(self.farming_page)
            bar.SetPosition(x, 43)
            bar.SetSize(1, 260)
            bar.SetColor(grid_color)
            bar.Show()
            self.map_grid.append(bar)
        for y in (88, 130, 173, 216, 258):
            bar = ui.Bar()
            bar.SetParent(self.farming_page)
            bar.SetPosition(335, y)
            bar.SetSize(260, 1)
            bar.SetColor(grid_color)
            bar.Show()
            self.map_grid.append(bar)
        self.map_compass = [
            make_text(self.farming_page, 461, 48, "N"),
            make_text(self.farming_page, 461, 285, "S"),
            make_text(self.farming_page, 576, 168, "E"),
            make_text(self.farming_page, 342, 168, "W"),
        ]
        self.map_ring = []
        for index in range(96):
            angle = 2.0 * math.pi * index / 96.0
            x = int(self.radar_center[0] + self.radar_pixels * math.cos(angle))
            y = int(self.radar_center[1] + self.radar_pixels * math.sin(angle))
            self.map_ring.append(make_radar_dot(
                self.farming_page, x, y, 3, ring_color, "."))
        self.map_reach = []
        for index in range(96):
            dot = make_radar_dot(self.farming_page, self.radar_center[0],
                                 self.radar_center[1], 2, reach_color, ".")
            dot.Hide()
            self.map_reach.append(dot)
        self.map_player = make_radar_dot(self.farming_page, self.radar_center[0] - 2,
                                         self.radar_center[1] - 2, 6, player_color, "P")
        self.map_metins = []
        self.map_outside_metins = []
        self.map_others = []
        for pool, count, color, symbol in (
                (self.map_metins, 32, metin_color, "M"),
                (self.map_outside_metins, 32, outside_color, "m"),
                (self.map_others, 64, other_color, ".")):
            for index in range(count):
                dot = make_radar_dot(self.farming_page, self.radar_center[0],
                                     self.radar_center[1], 5, color, symbol)
                dot.Hide()
                pool.append(dot)
        self.map_count_label = limit_text(
            make_text(self.farming_page, 335, 310,
                      "Red: 0 in range  Gray: 0 out  White: 0"), 260)
        self.map_reach_label = limit_text(
            make_text(self.farming_page, 335, 325,
                      "Yellow: you  Blue: anchor  Green: reach"), 260)
        self.anchor_button = make_button(
            self.farming_page, 335, "Anchor", self.ToggleAnchor, 341)
        self.anchor_label = limit_text(
            make_text(self.farming_page, 335 + button_width + 10, 346,
                      "Circle: following character"), 160)

        self.minigames_card = make_bar(
            self.minigames_page, 12, 10, 594, 374, panel_color)
        self.minigames_title = make_text(
            self.minigames_page, 22, 22, "MINIGAMES")
        self.minigame_separator_one = make_bar(
            self.minigames_page, 22, 126, 574, 1, separator_color)
        self.minigame_separator_two = make_bar(
            self.minigames_page, 22, 240, 574, 1, separator_color)
        self.reaction_title = make_text(
            self.minigames_page, 24, 61, "Auto Reaction")
        self.reaction_button = make_button(
            self.minigames_page, 596 - button_width, "ON",
            self.ToggleReaction, 56)
        self.reaction_label = limit_text(
            make_text(self.minigames_page, 24, 84,
                      "Watches the yin-yang reaction game"), 450)
        self.yinyang_duel_title = make_text(
            self.minigames_page, 24, 175, "Yin Yang Duel")
        self.yinyang_duel_button = make_button(
            self.minigames_page, 596 - button_width, "OFF",
            self.ToggleYinYangDuel, 170)
        self.yinyang_duel_label = limit_text(
            make_text(self.minigames_page, 24, 198,
                      "Plays the Yin Yang Duel minigame"), 450)
        self.twin_souls_title = make_text(
            self.minigames_page, 24, 289, "Twin Souls")
        self.twin_souls_button = make_button(
            self.minigames_page, 596 - button_width, "OFF",
            self.ToggleTwinSouls, 284)
        self.twin_souls_label = limit_text(
            make_text(self.minigames_page, 24, 312,
                      "Plays the Twin Souls memory minigame"), 450)

        self.footer_separator = make_bar(self, 10, 518, 600, 1, separator_color)
        self.config_save_button = make_button(self, 12, "Save", self.SaveConfig, 526)
        self.config_load_button = make_button(
            self, 12 + button_width + 8, "Load", self.LoadConfig, 526)
        self.config_auto_button = make_button(
            self, 12 + (button_width + 8) * 2, "Auto OFF",
            self.ToggleConfigAutoload, 526)
        self.footer_hint = make_text(self, 310, 531, "Ctrl+F8: hide / show")
        self.RecordLayoutMetrics()
        self.SwitchTab("farming")
        self.phase_guard = get_gameplay_phase_guard()
        self.phase_guard.SetOwner(self)
        self.gameplay_phase = self.phase_guard.current_phase
        self.AddLine("Ready. Log file: metin_scanner.log")
        self.AddLine("Native Hunter observer: %s" %
                     ("active" if self.hunter_observer is not None else "UNAVAILABLE"))
        try:
            saved_config = read_config_file()
            self.config_autoload = saved_config.get("autoload", "0") == "1"
            self.UpdateConfigAutoloadButton()
            if self.config_autoload:
                self.ApplyConfig(saved_config, True)
        except Exception as exc:
            self.AddLine("Configuration auto-load error: %s" % exc)
        self.Show()
        self.watcher = ScannerWatcher(self)

    def GetWidgetSize(self, widget, fallback_width, fallback_height):
        try:
            width = int(widget.GetWidth())
            height = int(widget.GetHeight())
            if width > 0 and height > 0:
                return width, height
        except Exception:
            pass
        return fallback_width, fallback_height

    def MeasureText(self, text):
        probe = ui.TextLine()
        probe.SetParent(self)
        probe.SetText(text)
        probe.Show()
        try:
            width, height = probe.GetTextSize()
            return int(width), int(height)
        except Exception:
            return 0, 0
        finally:
            probe.Hide()

    def RecordLayoutMetrics(self):
        stop_text_size = self.MeasureText("Stop farming")
        status_text_size = self.MeasureText("Stopped. Set radius, then click Start.")
        disk_log("Compact UI metrics: middle button=%dx%d; default font "
                 "Stop farming=%dx%d; status sample=%dx%d" %
                 (self.native_button_size[0], self.native_button_size[1],
                  stop_text_size[0], stop_text_size[1],
                  status_text_size[0], status_text_size[1]))

    def SwitchTab(self, name):
        if name not in self.tab_pages:
            return
        for tab_name, page in self.tab_pages.items():
            if tab_name == name:
                page.Show()
            else:
                page.Hide()
        self.tab_indicator.SetPosition(self.tab_positions[name], 102)
        self.active_tab = name

    def ShowFarmingTab(self):
        self.SwitchTab("farming")

    def ShowMinigamesTab(self):
        self.SwitchTab("minigames")

    def ShowActivityTab(self):
        self.SwitchTab("activity")

    def AddLine(self, message):
        clean = ascii_text(message)
        disk_log(clean)
        self.lines.append(clean)
        self.lines = self.lines[-8:]
        for index, label in enumerate(self.log_labels):
            row = self.lines[index] if index < len(self.lines) else ""
            label.SetText(row[:72])

    def _hunter_log(self, message):
        self.AddLine("Hunter: %s" % message)

    def _manual_queue_log_error(self, message):
        # Reporting only: a logger failure never changes queue/Hunter/gameplay.
        self.AddLine("Manual queue log: %s" % message)

    def _manual_queue_context(self, enrich, queue_snapshot):
        """Read-only context for ManualQueueLogger.

        Actor calls are limited to baselines/membership changes.  The method
        consumes an already-observed queue snapshot and never starts scanning,
        Hunter, the native queue, a solver, or an input/recorder routine.
        """
        context = {
            "valid": True,
            "gameplay_epoch": int(self.hunter_controller.epoch),
            "gameplay_available_cached": bool(self.gameplay_available),
            "map": None,
            "channel": None,
            "radius": int(self.radius),
            "anchor_position": (list(self.anchor_position[:2])
                                if self.anchor_position is not None else None),
            "automation": {
                "scanner_running": bool(self.running),
                "hunter_toggle_on": bool(self.hunter_enabled),
                "hunter_automatic_additions_enabled": bool(
                    self.hunter_enabled and
                    self.hunter_controller.user_requested_on and
                    self.hunter_controller.state not in
                    (HunterController.OFF, HunterController.ERROR,
                     HunterController.STOPPING, HunterController.PAUSED)),
                "hunter_state": self.hunter_controller.state,
                "hunter_user_requested_on": bool(
                    self.hunter_controller.user_requested_on),
                "boss_sweep_enabled": bool(self.boss_enabled),
                "reaction_solver_enabled": bool(self.reaction_enabled),
                "yin_yang_solver_enabled": bool(self.yinyang_duel_enabled),
                "twin_souls_solver_enabled": bool(self.twin_souls_enabled),
            },
            "player": {
                "main_character_vid": None,
                "position": None,
                "current_target_vid": None,
                "movement_state": None,
                "attack_state": None,
                "movement_attack_unavailable_reason":
                    "no verified read-only movement/attack-state getter",
            },
            "scanner_snapshot": None,
            "actors": None,
        }
        try:
            context["map"] = ascii_text(background.GetCurrentMapName())
        except Exception as exc:
            context["map_error"] = ascii_text(exc)
        try:
            context["channel"] = int(net.GetChannelNumber())
        except Exception as exc:
            context["channel_error"] = ascii_text(exc)
        try:
            context["player"]["main_character_vid"] = int(
                player.GetMainCharacterIndex())
        except Exception as exc:
            context["player"]["main_character_vid_error"] = ascii_text(exc)
        try:
            position = player.GetMainCharacterPosition()
            context["player"]["position"] = [position[0], position[1], position[2]]
        except Exception as exc:
            context["player"]["position_error"] = ascii_text(exc)
        try:
            context["player"]["current_target_vid"] = int(player.GetTargetVID())
        except Exception as exc:
            context["player"]["current_target_vid_error"] = ascii_text(exc)

        scanner = self.hunter_controller.last_scan
        candidate_by_vid = {}
        if scanner is not None:
            now_ms = hunter_now_ms()
            created_ms = scanner.get("created_ms")
            candidates = list(scanner.get("candidates") or ())
            candidate_by_vid = dict((int(item["vid"]), item)
                                    for item in candidates)
            ranked = sorted(candidates,
                            key=lambda item: (item.get("distance2", 0),
                                              item.get("vid", 0)))
            ranks = dict((int(item["vid"]), index + 1)
                         for index, item in enumerate(ranked))
            selected_vid = context["player"].get("current_target_vid")
            context["scanner_snapshot"] = {
                "created_tick_ms": created_ms,
                "age_ms": (None if now_ms is None or created_ms is None
                           else max(0, int(now_ms) - int(created_ms))),
                "epoch": scanner.get("epoch"),
                "candidate_count": len(candidates),
                "selected_target_distance_rank_among_scanner_candidates":
                    ranks.get(selected_vid),
                "selected_target_eligible_distance_rank": None,
                "eligible_rank_unavailable_reason":
                    "scanner snapshot does not retain native admission for every candidate",
                "candidate_first_observed_tick_ms": None,
                "first_observed_unavailable_reason":
                    "existing scanner snapshots retain latest observation only",
            }

        if enrich and queue_snapshot and queue_snapshot.get("valid"):
            queue_vids = [int(value) for value in
                          (queue_snapshot.get("vids") or ())]
            actors = []
            player_position = context["player"].get("position")
            anchor_position = context.get("anchor_position")
            for vid in queue_vids:
                actor = {
                    "vid": vid,
                    "name": None,
                    "race": None,
                    "position": None,
                    "is_stone": None,
                    "dead": None,
                    "hp": None,
                    "dead_hp_unavailable_reason":
                        "no verified read-only dead/HP getter",
                    "player_distance": None,
                    "anchor_distance": None,
                    "scanner_candidate": candidate_by_vid.get(vid),
                }
                try:
                    actor["race"] = int(chr.GetVirtualNumber(vid))
                    actor["name"] = ascii_text(chr.GetNameByVID(vid))
                    actor_position = chr.GetPixelPosition(vid)
                    actor["position"] = [actor_position[0], actor_position[1],
                                         actor_position[2]]
                    is_stone = getattr(chr, "IsStone", None)
                    if is_stone is not None:
                        actor["is_stone"] = bool(is_stone(vid))
                    if player_position is not None:
                        actor["player_distance"] = int(
                            ((actor_position[0] - player_position[0]) ** 2 +
                             (actor_position[1] - player_position[1]) ** 2) ** 0.5)
                    if anchor_position is not None:
                        actor["anchor_distance"] = int(
                            ((actor_position[0] - anchor_position[0]) ** 2 +
                             (actor_position[1] - anchor_position[1]) ** 2) ** 0.5)
                except Exception as exc:
                    actor["enrichment_error"] = ascii_text(exc)
                actors.append(actor)
            context["actors"] = actors
        return context

    def ClearMap(self):
        for dot in (self.map_metins + self.map_outside_metins +
                    self.map_others + self.map_reach):
            dot.Hide()
        self.map_count_label.SetText("Red: 0 in range  Gray: 0 out  White: 0")

    def UpdateConfigAutoloadButton(self):
        self.config_auto_button.SetText("Auto ON" if self.config_autoload else "Auto OFF")

    def ConfigValues(self):
        radius = self.ReadRadius()
        values = {
            "version": "1",
            "autoload": "1" if self.config_autoload else "0",
            "radius": str(radius),
            "reaction_enabled": "1" if self.reaction_enabled else "0",
            "anchor_enabled": "1" if self.anchor_position is not None else "0",
            "boss_marked": "1" if self.boss_vnum is not None and self.boss_position is not None else "0",
        }
        if self.anchor_position is not None:
            values.update({
                "anchor_x": str(int(self.anchor_position[0])),
                "anchor_y": str(int(self.anchor_position[1])),
                "anchor_channel": str(int(self.anchor_channel)),
                "anchor_map": ascii_text(self.anchor_map or ""),
            })
        if self.boss_vnum is not None and self.boss_position is not None:
            values.update({
                "boss_vnum": str(int(self.boss_vnum)),
                "boss_name": ascii_text(self.boss_name or "Boss"),
                "boss_x": str(int(self.boss_position[0])),
                "boss_y": str(int(self.boss_position[1])),
                "boss_channel": str(int(self.boss_mark_channel or self.anchor_channel)),
                "boss_map": ascii_text(self.boss_map or self.anchor_map or ""),
            })
        return values

    def SaveConfig(self, quiet=False):
        try:
            write_config_file(self.ConfigValues())
            if not quiet:
                self.AddLine("Configuration saved%s" %
                             (" with auto-load" if self.config_autoload else ""))
            return True
        except Exception as exc:
            self.AddLine("Configuration save error: %s" % exc)
            return False

    def ApplyConfig(self, values, automatic=False):
        try:
            if values.get("version") != "1":
                raise ValueError("unsupported or missing config version")
            radius = int(values["radius"])
            if radius < MIN_RADIUS or radius > MAX_RADIUS:
                raise ValueError("saved radius is outside %d-%d" % (MIN_RADIUS, MAX_RADIUS))
            if self.boss_enabled:
                self.StopBossSweep("Boss Sweep stopped for configuration load", False)
            self.radius = radius
            self.radius_edit.SetText(str(radius))
            self.reaction_enabled = values.get("reaction_enabled", "0") == "1"
            self.reaction_button.SetText("ON" if self.reaction_enabled else "OFF")
            self.reaction_label.SetText("Automatic solving unavailable; safety pause active"
                                        if self.reaction_enabled
                                        else "Manual reaction; combat safety remains active")
            if values.get("anchor_enabled", "0") == "1":
                anchor_channel = int(values["anchor_channel"])
                if anchor_channel <= 0 or anchor_channel > 20:
                    raise ValueError("saved anchor channel is invalid")
                self.anchor_position = (int(values["anchor_x"]), int(values["anchor_y"]))
                self.anchor_channel = anchor_channel
                self.anchor_map = ascii_text(values["anchor_map"])
                self.anchor_button.SetText("Unanchor")
                self.anchor_label.SetText("Circle: anchored at %d, %d on CH%d" %
                                          (self.anchor_position[0], self.anchor_position[1],
                                           self.anchor_channel))
            else:
                self.anchor_position = None
                self.anchor_channel = None
                self.anchor_map = None
                self.anchor_button.SetText("Anchor")
                self.anchor_label.SetText("Circle: following character")
            if values.get("boss_marked", "0") == "1":
                boss_vnum = int(values["boss_vnum"])
                boss_channel = int(values["boss_channel"])
                if boss_vnum <= 0 or boss_channel <= 0 or boss_channel > 20:
                    raise ValueError("saved boss identity is invalid")
                self.boss_vnum = boss_vnum
                self.boss_name = ascii_text(values.get("boss_name", "Boss")) or "Boss"
                self.boss_position = (int(values["boss_x"]), int(values["boss_y"]))
                self.boss_mark_channel = boss_channel
                self.boss_map = ascii_text(values["boss_map"])
                self.boss_label.SetText("%s [vnum %d], CH%d" %
                                        (self.boss_name, self.boss_vnum,
                                         self.boss_mark_channel))
            else:
                self.boss_vnum = None
                self.boss_name = None
                self.boss_position = None
                self.boss_mark_channel = None
                self.boss_map = None
                self.boss_label.SetText("Select a boss, then mark its spot")
            self.config_autoload = values.get("autoload", "0") == "1"
            self.UpdateConfigAutoloadButton()
            self.UpdateMapHeading()
            self.ClearMap()
            self.next_scan = 0.0
            self.AddLine("Configuration auto-loaded" if automatic else "Configuration loaded")
            return True
        except Exception as exc:
            self.AddLine("Configuration load error: %s" % exc)
            return False

    def LoadConfig(self):
        try:
            values = read_config_file()
        except Exception as exc:
            self.AddLine("Configuration load error: %s" % exc)
            return False
        if not values:
            self.AddLine("Configuration load error: no saved configuration")
            return False
        return self.ApplyConfig(values, False)

    def ToggleConfigAutoload(self):
        self.config_autoload = not self.config_autoload
        self.UpdateConfigAutoloadButton()
        if self.SaveConfig(True):
            self.AddLine("Configuration auto-load %s" %
                         ("ON" if self.config_autoload else "OFF"))

    def HasPlayableCharacter(self):
        try:
            return (int(player.GetMainCharacterIndex()) > 0 and
                    bool(ascii_text(player.GetMainCharacterName()).strip()))
        except Exception:
            return False

    def HasLiveConnection(self):
        try:
            return bool(net.IsConnect())
        except Exception:
            return False

    def DisableAndClearMetinQueue(self):
        """Disable/clear once; native true-to-false already performs a clear.
        Retained only for disabled-feature internals.  Hunter cleanup goes
        through the controller's ownership rules, never this broad clear."""
        try:
            enabled = bool(player.MetinQueueIsEnabled())
        except Exception:
            enabled = None
        if enabled:
            player.MetinQueueSetEnabled(0)
            return
        player.MetinQueueClear()
        if enabled is None:
            player.MetinQueueSetEnabled(0)

    def HasActiveNativeAutomation(self):
        return bool(self.hunter_enabled or self.boss_modes_paused or
                    self.reaction_native_paused or
                    (self.boss_enabled and self.boss_state == BOSS_ATTACK))

    def EmergencyStopForGameplayExit(self, reason):
        self.hunter_controller.on_session_change(reason)
        self.running = False
        self.hunter_enabled = False
        self.hunter_button.SetText("OFF")
        self.hunter_label.SetText("Queue: stopped outside game")
        self.boss_enabled = False
        self.boss_modes_paused = False
        self.boss_state = BOSS_IDLE
        self.boss_target_vid = 0
        self.boss_target_missing_since = None
        self.boss_button.SetText("OFF")
        self.boss_label.SetText("Boss Sweep stopped outside game")
        self.ClearMap()
        self.state_label.SetText("Stopped: not in the playable game world.")
        if not self.gameplay_stopped:
            self.AddLine("Automation stopped: %s" % reason)
        self.gameplay_stopped = True

    def OnGameplayPhaseWindowRegistered(self, phase, window):
        self.gameplay_phase = int(phase)
        self.gameplay_available = (self.gameplay_phase == PHASE_GAME)
        self.gameplay_next_check = 0.0
        window_name = ascii_text(getattr(type(window), "__name__", "unknown"))
        if self.gameplay_available:
            self.gameplay_stopped = False
            window_id = id(window)
            if self._game_window is not None and self._game_window != window_id:
                # A replacement phase-5 window is a new gameplay session: bump the
                # epoch and stay OFF; never auto-enable old state.
                self.hunter_controller.on_session_change("gameplay window replaced")
            self._game_window = window_id
            self.AddLine("Playable game window registered: %s" % window_name)
            return
        if self.gameplay_phase == PHASE_LOADING:
            self.hunter_controller.on_session_change("phase loading")
            self.state_label.SetText("Paused while the game is loading.")
            return
        self.EmergencyStopForGameplayExit(
            "phase window %d registered: %s" % (self.gameplay_phase, window_name))

    def OnPythonNetDisconnect(self, args, kwargs, stack):
        frames = []
        for filename, line, function, source in stack[-8:]:
            frames.append("%s:%d:%s" %
                          (os.path.basename(filename), int(line), function))
        self.AddLine("Python net.Disconnect called args=%r kwargs=%r stack=%s" %
                     (args, kwargs, " > ".join(frames)))

    def IsGameplayAvailable(self, now=None):
        if self.gameplay_phase is not None and self.gameplay_phase != PHASE_GAME:
            return False
        if now is None:
            now = time.time()
        if now < self.gameplay_next_check:
            return self.gameplay_available
        self.gameplay_next_check = now + PLAYER_POLL_SECONDS
        if not self.HasLiveConnection():
            self.gameplay_available = False
            if (self.boss_enabled and self.boss_state in
                    (BOSS_CHANGE_CHANNEL, BOSS_WAIT_CHANNEL, BOSS_SETTLE_CHANNEL)):
                self.hunter_controller.on_session_change("game connection closed")
                return False
            self.EmergencyStopForGameplayExit("game connection is closed")
            return False
        available = self.HasPlayableCharacter()
        self.gameplay_available = available
        if not available:
            self.EmergencyStopForGameplayExit("main character is unavailable")
        return available

    def UpdateMapPool(self, dots, offsets):
        for index, dot in enumerate(dots):
            if index < len(offsets):
                dx, dy = offsets[index]
                dot.SetPosition(int(self.radar_center[0] - dx * self.radar_pixels / self.radius),
                                int(self.radar_center[1] - dy * self.radar_pixels / self.radius))
                dot.Show()
            else:
                dot.Hide()

    def UpdateMap(self, metin_offsets, other_offsets, outside_offsets=()):
        self.UpdateMapPool(self.map_metins, metin_offsets)
        self.UpdateMapPool(self.map_outside_metins, outside_offsets)
        self.UpdateMapPool(self.map_others, other_offsets)
        self.map_count_label.SetText("Red: %d in range  Gray: %d out  White: %d" %
                                     (len(metin_offsets), len(outside_offsets),
                                      len(other_offsets)))

    def UpdatePlayerMarker(self, player_position):
        self.UpdateMapPool(self.map_reach, radar_player_reach_offsets(
            player_position, self.anchor_position, self.radius))
        center = self.anchor_position or player_position
        dx = player_position[0] - center[0]
        dy = player_position[1] - center[1]
        if abs(dx) > self.radius * 1.15 or abs(dy) > self.radius * 1.15:
            self.map_player.Hide()
            return
        self.map_player.SetPosition(int(self.radar_center[0] - dx * self.radar_pixels / self.radius) - 2,
                                    int(self.radar_center[1] - dy * self.radar_pixels / self.radius) - 2)
        self.map_player.Show()

    def UpdateMapHeading(self):
        mode = "anchored" if self.anchor_position is not None else "following"
        self.radar_label.SetText("Map: %s, radius %d" % (mode, self.radius))

    def ToggleAnchor(self):
        if self.anchor_position is None:
            try:
                self.anchor_position = tuple(player.GetMainCharacterPosition()[:2])
                self.anchor_channel = int(net.GetChannelNumber())
                self.anchor_map = ascii_text(background.GetCurrentMapName())
            except Exception as exc:
                self.AddLine("Anchor error: %s" % exc)
                return
            self.anchor_button.SetText("Unanchor")
            self.anchor_label.SetText("Circle: anchored at %d, %d on CH%d" %
                                      (self.anchor_position[0], self.anchor_position[1],
                                       self.anchor_channel))
            self.AddLine("Circle anchored at %d, %d on CH%d" %
                         (self.anchor_position[0], self.anchor_position[1],
                          self.anchor_channel))
        else:
            if self.boss_enabled:
                self.StopBossSweep("Boss Sweep stopped: anchor removed", False)
            self.anchor_position = None
            self.anchor_channel = None
            self.anchor_map = None
            self.anchor_button.SetText("Anchor")
            self.anchor_label.SetText("Circle: following character")
            self.AddLine("Circle follows character")
        self.UpdateMapHeading()
        self.ClearMap()
        self.next_scan = 0.0

    def FindRuntimeObject(self, class_name, required_methods):
        roots = []
        try:
            roots.extend(list(__main__.__dict__.values()))
        except Exception:
            pass
        queue = [(obj, 0) for obj in roots]
        seen = set()
        index = 0
        while index < len(queue) and index < 10000:
            obj, depth = queue[index]
            index += 1
            object_id = id(obj)
            if object_id in seen:
                continue
            seen.add(object_id)
            try:
                if (obj.__class__.__name__ == class_name and
                        all(callable(getattr(obj, name, None))
                            for name in required_methods)):
                    return obj
            except Exception:
                pass
            if depth >= 5:
                continue
            try:
                if isinstance(obj, dict):
                    children = list(obj.values())
                elif isinstance(obj, (list, tuple, set)):
                    children = list(obj)
                else:
                    children = list(getattr(obj, "__dict__", {}).values())
                for child in children[:250]:
                    queue.append((child, depth + 1))
            except Exception:
                continue
        for obj in gc.get_objects():
            try:
                if obj.__class__.__name__ != class_name:
                    continue
                if all(callable(getattr(obj, name, None)) for name in required_methods):
                    return obj
            except Exception:
                continue
        return None

    def FindBossRuntime(self):
        if self.boss_timer is None:
            self.boss_timer = self.FindRuntimeObject(
                "CursedBossAtlasPanel", ("GetTimeRemaining",))
        if self.boss_switch_dialog is None:
            self.boss_switch_dialog = self.FindRuntimeObject(
                "MoveChannelDialog",
                ("GetChannelCount", "GetChannelNumber", "AcceptButton"))
        return (self.boss_timer is not None and
                self.boss_switch_dialog is not None)

    def ToggleReaction(self):
        self.reaction_enabled = not self.reaction_enabled
        self.reaction_button.SetText("ON" if self.reaction_enabled else "OFF")
        # Automatic solving is unavailable in this Hunter-focused change; the
        # toggle remains, but no solver runs.
        self.reaction_label.SetText("Automatic solving unavailable; safety pause active"
                                    if self.reaction_enabled
                                    else "Manual reaction; combat safety remains active")
        self.reaction_next_poll = 0.0
        self.AddLine("Auto Reaction %s (solver unavailable)" %
                     ("ON" if self.reaction_enabled else "OFF"))

    def PauseNativeAutomationForReaction(self):
        if self.reaction_native_paused:
            return
        self.reaction_native_paused = True
        self.reaction_resume_token = self.hunter_controller.pause('reaction')
        self.hunter_label.SetText("Queue: paused for reaction")
        self.AddLine("Reaction safety: native automation paused")

    def PollReactionGame(self, now):
        if now < self.reaction_next_poll:
            return self.reaction_pause_started is not None
        if self.reaction_window is not None:
            interval = (REACTION_POLL_SECONDS if
                        (self.reaction_enabled or self.reaction_pause_started is not None)
                        else REACTION_SAFETY_POLL_SECONDS)
        else:
            interval = (REACTION_DISCOVERY_SECONDS if self.reaction_enabled
                        else REACTION_SAFETY_DISCOVERY_SECONDS)
        self.reaction_next_poll = now + interval
        try:
            window = self.reaction_window
            if window is None:
                window = self.FindRuntimeObject(
                    "ReactionGameWindow", ("IsShow", "_ReactionGameWindow__OnClickPlay",
                                           "_ReactionGameWindow__OnClickSlot"))
                self.reaction_window = window
            if window is None or not window.IsShow():
                if self.reaction_pause_started is not None:
                    self.AddLine("Reaction game closed")
                self.reaction_started = False
                self.reaction_last_ball = None
                self.reaction_pending_ball = None
                self.reaction_click_at = 0.0
                return False
            self.reaction_next_poll = now + REACTION_POLL_SECONDS
            if self.reaction_pause_started is None:
                self.reaction_pause_started = now
                self.PauseNativeAutomationForReaction()
                self.AddLine("Reaction game visible; native automation paused "
                             "(solver unavailable)")
            # Automatic solving is unavailable; no play/slot clicks are issued.
            return True
        except Exception as exc:
            problem = ascii_text(exc)
            if problem != self.reaction_last_error:
                self.AddLine("Reaction game error: %s" % problem)
                self.reaction_last_error = problem
            self.reaction_window = None
            return self.reaction_pause_started is not None

    def ResumeAfterReaction(self, now):
        if self.reaction_pause_started is None:
            return
        elapsed = max(0.0, now - self.reaction_pause_started)
        self.reaction_pause_started = None
        if self.boss_enabled:
            self.boss_state_started += elapsed
            if self.boss_deadline:
                self.boss_deadline += elapsed
            if self.boss_missing_since is not None:
                self.boss_missing_since += elapsed
            if self.boss_target_missing_since is not None:
                self.boss_target_missing_since += elapsed
        if self.reaction_native_paused:
            self.hunter_controller.resume(getattr(self, "reaction_resume_token", None))
            self.reaction_native_paused = False
            self.reaction_resume_token = None
            self.hunter_label.SetText(self.hunter_controller.status_text)
        self.AddLine("Reaction game pause ended after %.1fs" % elapsed)

    def ToggleYinYangDuel(self):
        self.yinyang_duel_enabled = False
        self.yinyang_duel_button.SetText("OFF")
        self.yinyang_duel_label.SetText(
            "Yin Yang Duel unavailable: temporarily disabled")
        self.AddLine("Yin Yang Duel unavailable: temporarily disabled")

    def DiagnosticYinYangDuel(self):
        """Dump the YinYangDuelWindow runtime API so the minigame can be driven."""
        window = self.FindRuntimeObject("YinYangDuelWindow", ())
        if window is None:
            self.AddLine("YinYangDuelWindow not found in runtime objects")
            return
        self.AddLine("YinYangDuelWindow type=%s" % ascii_text(type(window).__name__))
        for name in ("state", "round", "playerScore", "opponentScore",
                     "leadInfo", "leadActive", "hasState", "enabled", "reveal",
                     "duelsUsedHwid", "duelsMaxHwid", "duelsUsed", "duelsMax",
                     "cooldownEnd", "startPending", "openPending", "levelMin",
                     "costGold"):
            try:
                value = getattr(window, name, None)
                self.AddLine("  duel state %s = %s" %
                             (name, ascii_text(repr(value))[:140]))
            except Exception as exc:
                self.AddLine("  duel state %s error: %s" % (name, exc))
        try:
            self.AddLine("  duel cooldown remaining = %s" %
                         ascii_text(repr(window.GetCooldownRemaining())))
        except Exception as exc:
            self.AddLine("  duel cooldown remaining error: %s" % exc)
        for label, cards in (("player", getattr(window, "playerCards", None)),
                             ("opponent", getattr(window, "opponentCards", None))):
            if not cards:
                self.AddLine("  duel %s cards: (none)" % label)
                continue
            try:
                keys = list(cards.keys())
                self.AddLine("  duel %s card keys = %s" % (label, ascii_text(repr(keys))))
                sample = cards[keys[0]]
                self.AddLine("  duel %s card type=%s" % (label, ascii_text(type(sample).__name__)))
                self.AddLine("  duel %s card dict=%s" %
                             (label, ascii_text(repr(getattr(sample, "__dict__", {}))[:240])))
                for name in dir(sample):
                    if not name.startswith("__"):
                        self.AddLine("    card attr %s" % name)
            except Exception as exc:
                self.AddLine("  duel %s card dump error: %s" % (label, exc))

    def _DuelCooldownRemaining(self, window):
        get_cd = getattr(window, "GetCooldownRemaining", None)
        if callable(get_cd):
            try:
                value = get_cd()
                if isinstance(value, (tuple, list)):
                    value = value[0] if value else 0
                return float(value)
            except Exception:
                pass
        return 0.0

    def _DuelDebugLog(self, message):
        if message != self.yinyang_duel_debug:
            self.yinyang_duel_debug = message
            self.AddLine(message)

    def _DuelStallLog(self, reason, detail=""):
        """Throttled log of *why* a card was not played, to diagnose stalls."""
        message = "Yin Yang Duel: no play (%s)%s" % (reason, detail)
        if message != self.yinyang_duel_stall:
            self.yinyang_duel_stall = message
            self.AddLine(message)

    def _DuelFinishDiagnostic(self, window, state):
        """Log the post-finish state and the window's result/continue members.

        The post-match `state` and the result-screen continue handler are
        reverse-engineered and unverified. This one-shot log (throttled by
        `_DuelDebugLog`) captures the real values after a finish so the next
        live run can confirm the dismissal member and any dedicated result
        state.
        """
        self._DuelDebugLog("Yin Yang Duel: finish observed at state=%s" % state)
        try:
            members = [name for name in dir(window)
                       if name.startswith("_YinYangDuelWindow__") and
                       any(token in name.lower()
                           for token in ("result", "continue", "confirm",
                                         "close", "finish", "end"))]
            self._DuelDebugLog("Yin Yang Duel: result members = %s" %
                               ascii_text(repr(members)))
        except Exception:
            pass

    def _DuelRecordEvent(self, event):
        """Append one versioned JSON-lines event to the duel history."""
        try:
            event = dict(event)
            event.setdefault("schema", YINYANG_DUEL_HISTORY_SCHEMA)
            event.setdefault("ts", time.strftime("%Y-%m-%d %H:%M:%S",
                                                 time.localtime()))
            event.setdefault("feature_version", FEATURE_VERSION)
            line = json.dumps(event, sort_keys=True)
            if sys.version_info[0] == 2:
                data = line + "\n"
            else:
                data = line.encode("ascii") + b"\n"
            fd = os.open(YINYANG_DUEL_HISTORY_JSONL,
                         os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o644)
            try:
                offset = 0
                while offset < len(data):
                    written = os.write(fd, data[offset:])
                    if written <= 0:
                        break
                    offset += written
            finally:
                os.close(fd)
        except Exception as exc:
            self._DuelDebugLog("Yin Yang Duel: history write error %s" %
                               ascii_text(exc))

    def _DuelRecordPlay(self, actor, round_num, card_value, leads):
        self._DuelRecordEvent({
            "event": "play",
            "actor": actor,
            "round": int(round_num),
            "card": int(card_value),
            "leads": 1 if leads else 0,
        })

    def _DuelTryPlay(self, window):
        """If it is our turn, solve and play a card.  Returns True when played."""
        if getattr(window, "state", None) != 2:
            return False
        tracker = self.yinyang_duel_tracker
        snapshot = tracker.build_snapshot(window)
        if snapshot is None:
            our_rm, our_ok = tracker.read_mask(getattr(window, "playerCards", None),
                                               played=False)
            opp_rm, opp_ok = tracker.read_mask(getattr(window, "opponentCards", None),
                                               played=False)
            lead_info = getattr(window, "leadInfo", None) or {}
            self._DuelStallLog(
                "snapshot rejected",
                ": we_lead=%s round=%s our=%d(%s) opp=%d(%s)" % (
                    duel_we_lead(lead_info),
                    lead_info.get("round", 0),
                    duel_mask_count(our_rm), our_ok,
                    duel_mask_count(opp_rm), opp_ok))
            return False
        key = snapshot.decision_key()
        if tracker.has_pending(key):
            self._DuelStallLog(
                "pending click not cleared",
                ": round=%s we_lead=%s" % (snapshot.round_num, snapshot.we_lead))
            return False
        can_pick = getattr(window, "CanPickCard", None)
        if callable(can_pick):
            try:
                if not can_pick():
                    self._DuelStallLog(
                        "CanPickCard returned false",
                        ": round=%s we_lead=%s" % (snapshot.round_num, snapshot.we_lead))
                    return False
            except Exception:
                pass
        deadline = time.time() + DUEL_SOLVER_BUDGET_SECONDS
        solve_started = time.time()
        decision = self.yinyang_duel_solver.choose_move(snapshot, deadline)
        solver_elapsed_ms = (time.time() - solve_started) * 1000.0
        if decision is None or decision.get("card_value") is None:
            self._DuelStallLog(
                "solver produced no decision",
                ": round=%s we_lead=%s our=%d opp=%d" % (
                    snapshot.round_num, snapshot.we_lead,
                    duel_mask_count(snapshot.our_remaining_mask),
                    duel_mask_count(snapshot.opponent_remaining_mask)))
            return False
        value = int(decision["card_value"])
        cards = getattr(window, "playerCards", None) or {}
        card = cards.get(value)
        if card is None:
            for candidate in cards.values():
                try:
                    if int(getattr(candidate, "value", -1)) == value:
                        card = candidate
                        break
                except Exception:
                    continue
        if card is None or getattr(card, "played", False):
            self._DuelStallLog(
                "chosen card unavailable",
                ": card=%d played=%s" % (
                    value,
                    bool(getattr(card, "played", False)) if card is not None else None))
            return False
        tracker.mark_pending(key)
        try:
            card.OnMouseLeftButtonDown()
        except Exception as exc:
            tracker.clear_pending()
            self._DuelDebugLog("Yin Yang Duel: card click error %s" % ascii_text(exc))
            return False
        note = (" vs %d" % snapshot.exact_opponent_led_value
                if snapshot.exact_opponent_led_value is not None else "")
        self.AddLine("Yin Yang Duel: played %d (%s)%s" %
                     (value, decision.get("mode"), note))
        self._DuelRecordEvent({
            "event": "decision",
            "match_id": snapshot.match_id,
            "round": snapshot.round_num,
            "state": snapshot.state,
            "we_lead": 1 if snapshot.we_lead else 0,
            "visible_color": snapshot.visible_color,
            "exact_opponent_led_value": snapshot.exact_opponent_led_value,
            "exact_value_confident": 1 if snapshot.exact_value_confident else 0,
            "our_score_before": snapshot.our_score,
            "opponent_score_before": snapshot.opponent_score,
            "our_remaining_mask": snapshot.our_remaining_mask,
            "opponent_remaining_mask": snapshot.opponent_remaining_mask,
            "chosen_card": value,
            "decision_mode": decision.get("mode"),
            "win_probability": decision.get("win_probability"),
            "loss_probability": decision.get("loss_probability"),
            "expected_final_score_delta": decision.get("expected_score_delta"),
            "worst_case_utility": decision.get("worst_case_utility"),
            "complete_search": 1 if decision.get("complete_search") else 0,
            "solver_elapsed_ms": round(solver_elapsed_ms, 3),
            "model_version": decision.get("model_version"),
        })
        self.yinyang_duel_label.SetText("Yin Yang Duel: played %d" % value)
        return True

    def _DuelEnsureVisible(self, window):
        """Open the duel window if it is hidden; returns True when opened."""
        try:
            if not window.IsShow():
                window.Open()
                return True
        except Exception:
            pass
        return False

    def _DuelCloseResult(self, window):
        """Dismiss the end-of-duel result screen via its continue action.

        The result-screen handler name is reverse-engineered and may vary by
        build, so we try the known candidates, then any discovered
        result/continue callable, and finally close the window as a last resort.
        Each dispatch is preceded by a synthetic click so the handler sees the
        same input a real click would produce (matching the reaction game and
        the duel card click paths).
        """
        name, continue_action = duel_result_continue_member(window)
        if continue_action is not None:
            try:
                continue_action()
                self.yinyang_duel_label.SetText(
                    "Yin Yang Duel: result dismissed (%s)" % name)
                return True
            except Exception:
                return False
        close = getattr(window, "Close", None)
        if callable(close):
            try:
                close()
                self.yinyang_duel_label.SetText("Yin Yang Duel: result window closed")
                return True
            except Exception:
                return False
        return False

    def _DuelEnsureStarted(self, window, state):
        if self._DuelEnsureVisible(window):
            self.yinyang_duel_label.SetText("Yin Yang Duel: opening window")
            return
        if state == 0:
            start = getattr(window, "_YinYangDuelWindow__OnStartClicked", None)
            if callable(start):
                start()
                self.yinyang_duel_label.SetText("Yin Yang Duel: starting")
                return
        self.yinyang_duel_label.SetText("Yin Yang Duel: idle (state %s)" % state)

    def PollYinYangDuel(self, now):
        if not self.yinyang_duel_enabled:
            return
        if self.boss_enabled and self.boss_state in BOSS_SWEEP_BUSY_STATES:
            self.yinyang_duel_label.SetText("Yin Yang Duel: waiting for Boss Sweep")
            return
        if now < self.yinyang_duel_next_poll:
            return
        self.yinyang_duel_next_poll = now + YINYANG_DUEL_POLL_SECONDS
        try:
            window = self.FindRuntimeObject("YinYangDuelWindow", ())
            if window is None:
                self.yinyang_duel_label.SetText("Yin Yang Duel: window not found")
                return
            tracker = self.yinyang_duel_tracker
            tracker.on_window(window)
            used = int(getattr(window, "duelsUsedHwid", 0) or 0)
            maximum = int(getattr(window, "duelsMaxHwid", 0) or 0)
            if maximum > 0 and used >= maximum:
                self.yinyang_duel_enabled = False
                self.yinyang_duel_button.SetText("OFF")
                self.yinyang_duel_label.SetText(
                    "Yin Yang Duel: daily limit %d/%d" % (used, maximum))
                return
            state = getattr(window, "state", None)
            lead_info = getattr(window, "leadInfo", None) or {}
            round_num = lead_info.get("round", 0)
            we_lead = duel_we_lead(lead_info)
            # Keep the duel window visible while a duel is active, so the
            # automation isn't playing cards on a hidden window.
            if state in (2, 3, 4):
                self._DuelEnsureVisible(window)
            # Warm the solver cache during non-pick active states so the next
            # pick decision is fast and closer to exact.
            if state in (3, 4):
                warm_our, _ = tracker.read_mask(
                    getattr(window, "playerCards", None), played=False)
                warm_opp, _ = tracker.read_mask(
                    getattr(window, "opponentCards", None), played=False)
                self.yinyang_duel_solver.warm(
                    warm_our, warm_opp,
                    int(getattr(window, "playerScore", 0) or 0) -
                    int(getattr(window, "opponentScore", 0) or 0),
                    time.time() + DUEL_WARM_BUDGET_SECONDS)
            # Observe and record the opponent's plays (leads and responses).
            newly, _exact = tracker.observe_opponent(window)
            for value in newly:
                self._DuelRecordPlay("them", round_num, value, we_lead)
            # Correlate resolved rounds and the match finish from score/state
            # transitions.
            our_score = int(getattr(window, "playerScore", 0) or 0)
            opp_score = int(getattr(window, "opponentScore", 0) or 0)
            prev_state = self.yinyang_duel_last_state
            if state == 2 and prev_state in (0, None):
                # A new match started; reset score tracking.
                self.yinyang_duel_last_scores = (our_score, opp_score)
            else:
                last_scores = self.yinyang_duel_last_scores
                if last_scores is not None and last_scores != (our_score, opp_score):
                    our_delta = our_score - last_scores[0]
                    opp_delta = opp_score - last_scores[1]
                    outcome = ("win" if our_delta > 0 else
                               ("lose" if opp_delta > 0 else "tie"))
                    self._DuelRecordEvent({
                        "event": "result",
                        "match_id": tracker.match_id,
                        "round": round_num,
                        "round_outcome": outcome,
                        "our_score": our_score,
                        "opponent_score": opp_score,
                    })
                    self.yinyang_duel_last_scores = (our_score, opp_score)
                if prev_state in (2, 3, 4) and state not in (2, 3, 4):
                    final_outcome = ("win" if our_score > opp_score else
                                     ("lose" if our_score < opp_score else "tie"))
                    self._DuelRecordEvent({
                        "event": "finish",
                        "match_id": tracker.match_id,
                        "our_score": our_score,
                        "opponent_score": opp_score,
                        "outcome": final_outcome,
                    })
                    # Schedule dismissal of the end-of-duel result screen once
                    # its short reveal animation has had time to appear. The
                    # post-match state may be a dedicated result state rather
                    # than exactly 0, so the finish is detected on leaving the
                    # active states and the close is attempted regardless of the
                    # exact state below.
                    self.yinyang_duel_result_closed = False
                    self.yinyang_duel_result_close_at = (
                        now + YINYANG_DUEL_RESULT_CLOSE_DELAY)
                    self._DuelFinishDiagnostic(window, state)
            self.yinyang_duel_last_state = state
            # Clear the pending click once state leaves the pickable round.
            if state != 2 or round_num != tracker.last_round:
                tracker.clear_pending()
            tracker.last_round = round_num
            # Debug: report state and mask counts (throttled) to diagnose stalls.
            _our_rm, _our_ok = tracker.read_mask(getattr(window, "playerCards", None),
                                                 played=False)
            _opp_rm, _opp_ok = tracker.read_mask(getattr(window, "opponentCards", None),
                                                 played=False)
            self._DuelDebugLog(
                "Yin Yang Duel: state=%s round=%s we_lead=%s our=%d(%s) opp=%d(%s)" %
                (state, round_num, we_lead, duel_mask_count(_our_rm), _our_ok,
                 duel_mask_count(_opp_rm), _opp_ok))
            if self._DuelTryPlay(window):
                return
            # Dismiss the end-of-duel result screen once its reveal delay has
            # elapsed, regardless of the exact post-match state (the game may
            # present the result in a dedicated state instead of returning to
            # 0). Runs before the cooldown/start gating so the result screen
            # can never block the next duel or Twin Souls.
            if (not self.yinyang_duel_result_closed and
                    now >= self.yinyang_duel_result_close_at):
                if self._DuelCloseResult(window):
                    self.yinyang_duel_result_closed = True
            # Only treat the cooldown as a gate when the duel is idle.  During
            # an active duel (state 2/3/4) GetCooldownRemaining reports the
            # countdown to the next duel, which must not be shown as a stall.
            if state == 0:
                cooldown = self._DuelCooldownRemaining(window)
                if cooldown > 0:
                    self.yinyang_duel_label.SetText(
                        "Yin Yang Duel: cooldown %ds (%d/%d used)" %
                        (int(cooldown), used, maximum))
                    return
                self._DuelEnsureStarted(window, state)
            else:
                self.yinyang_duel_label.SetText("Yin Yang Duel: duel in progress")
        except Exception as exc:
            problem = ascii_text(exc)
            if problem != self.yinyang_duel_last_error:
                self.AddLine("Yin Yang Duel error: %s" % problem)
                self.yinyang_duel_last_error = problem

    # --- Twin Souls controller ---

    def ToggleTwinSouls(self):
        self.twin_souls_enabled = False
        self.twin_souls_button.SetText("OFF")
        self.twin_souls_label.SetText(
            "Twin Souls unavailable: temporarily disabled")
        self.AddLine("Twin Souls unavailable: temporarily disabled")

    def _TwinSoulsRelease(self):
        self.twin_souls_window = None
        self.twin_souls_trace_key = None
        tracker = self.twin_souls_tracker
        tracker.pending_flip = None
        tracker.pending_start = False

    def _TwinSoulsFromInterface(self):
        interface = getattr(__main__, "interface", None)
        getter = getattr(interface, "GetYinYangMemoryWnd", None)
        if not callable(getter):
            return None
        try:
            window = getter()
        except Exception:
            return None
        if window is not None and type(window).__name__ == "YinYangMemoryWindow":
            return window
        return None

    def _TwinSoulsDiscover(self, now):
        if now < self.twin_souls_discover_at and self.twin_souls_window is not None:
            return self.twin_souls_window
        self.twin_souls_discover_at = now + TWIN_SOULS_DISCOVERY_SECONDS
        window = self._TwinSoulsFromInterface()
        if window is None:
            window = self.FindRuntimeObject("YinYangMemoryWindow", ())
        if window is not None:
            self.twin_souls_window = window
        return window

    def DiagnosticTwinSouls(self):
        """Dump the YinYangMemoryWindow runtime API so the minigame can be
        driven once the runtime shapes are confirmed. Read-only and bounded."""
        window = self._TwinSoulsFromInterface()
        if window is None:
            window = self.FindRuntimeObject("YinYangMemoryWindow", ())
        if window is None:
            self.AddLine("YinYangMemoryWindow not found in runtime objects")
            return
        self.AddLine("YinYangMemoryWindow type=%s" % ascii_text(type(window).__name__))
        for name in ("state", "enabled", "opened", "hasState", "isLoaded",
                     "faceCount", "pairsFound", "awaitingFlip",
                     "playsUsed", "playsMax", "playsUsedHwid", "playsMaxHwid",
                     "timeLimitSec", "timeLeftSec", "cooldownSec",
                     "openPending", "openCells", "openFaces"):
            try:
                value = getattr(window, name, None)
                self.AddLine("  memory %s = %s" %
                             (name, ascii_text(repr(value))[:140]))
            except Exception as exc:
                self.AddLine("  memory %s error: %s" % (name, exc))
        for label, method in (("cooldown", "GetCooldownRemaining"),
                              ("time", "GetTimeRemaining"),
                              ("bonus", "GetBonusRemaining")):
            try:
                func = getattr(window, method, None)
                if callable(func):
                    self.AddLine("  memory %s remaining = %s" %
                                 (label, ascii_text(repr(func()))))
                else:
                    self.AddLine("  memory %s remaining: method missing" % label)
            except Exception as exc:
                self.AddLine("  memory %s remaining error: %s" % (label, exc))
        cards = getattr(window, "cards", None)
        if cards is None:
            self.AddLine("  memory cards: (none)")
        else:
            try:
                self.AddLine("  memory cards type=%s len=%s" %
                             (ascii_text(type(cards).__name__), len(cards)))
                if isinstance(cards, dict):
                    keys = list(cards.keys())[:12]
                    sample = cards[keys[0]] if keys else None
                    self.AddLine("  memory card keys = %s" % ascii_text(repr(keys)))
                else:
                    sample = cards[0] if len(cards) else None
                    self.AddLine("  memory card indices = %s" %
                                 ascii_text(repr(list(range(len(cards)))[:12])))
                if sample is not None:
                    self.AddLine("  memory card type=%s" %
                                 ascii_text(type(sample).__name__))
                    self.AddLine("  memory card dict=%s" %
                                 ascii_text(repr(getattr(sample, "__dict__", {}))[:240]))
                    for name in dir(sample):
                        if not name.startswith("__"):
                            self.AddLine("    card attr %s" % name)
            except Exception as exc:
                self.AddLine("  memory card dump error: %s" % exc)
        members = [n for n in dir(window)
                   if any(t in n.lower()
                          for t in ("start", "click", "open", "begin", "play",
                                    "result"))]
        self.AddLine("  memory window action members = %s" % ascii_text(repr(members)))

    def _TwinSoulsCooldownRemaining(self, window):
        get_cd = getattr(window, "GetCooldownRemaining", None)
        if callable(get_cd):
            try:
                value = get_cd()
                if isinstance(value, (tuple, list)):
                    value = value[0] if value else 0
                return float(value)
            except Exception:
                pass
        return 0.0

    def _TwinSoulsLimitReached(self, snapshot):
        if snapshot.plays_max > 0 and snapshot.plays_used >= snapshot.plays_max:
            return ("daily", snapshot.plays_used, snapshot.plays_max)
        if (snapshot.plays_max_hwid > 0 and
                snapshot.plays_used_hwid >= snapshot.plays_max_hwid):
            return ("HWID", snapshot.plays_used_hwid, snapshot.plays_max_hwid)
        return None

    def _TwinSoulsDisableForLimit(self, reached):
        kind, used, maximum = reached
        self.twin_souls_enabled = False
        self.twin_souls_button.SetText("OFF")
        self._TwinSoulsRelease()
        self.twin_souls_label.SetText("Twin Souls: %s limit %d/%d" %
                                      (kind, used, maximum))
        self.AddLine("Twin Souls stopped: %s limit reached (%d/%d)" %
                     (kind, used, maximum))
        self._TwinSoulsRecordEvent({"event": "controller_error",
                                    "reason": "%s_limit_reached" % kind.lower(),
                                    "used": used, "maximum": maximum})

    def _TwinSoulsStatus(self, message):
        text = "Twin Souls: %s" % message
        if text != self.twin_souls_last_status:
            self.twin_souls_last_status = text
            self.twin_souls_label.SetText(text)

    def _TwinSoulsDebugLog(self, message):
        if message != self.twin_souls_last_error:
            self.twin_souls_last_error = message
            self.AddLine(message)

    def _TwinSoulsRecordEvent(self, event):
        try:
            event = dict(event)
            event.setdefault("schema", TWIN_SOULS_HISTORY_SCHEMA)
            event.setdefault("ts", time.strftime("%Y-%m-%d %H:%M:%S",
                                                 time.localtime()))
            event.setdefault("feature_version", FEATURE_VERSION)
            line = json.dumps(event, sort_keys=True)
            if sys.version_info[0] == 2:
                data = line + "\n"
            else:
                data = line.encode("ascii") + b"\n"
            fd = os.open(TWIN_SOULS_HISTORY_JSONL,
                         os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o644)
            try:
                offset = 0
                while offset < len(data):
                    written = os.write(fd, data[offset:])
                    if written <= 0:
                        break
                    offset += written
            finally:
                os.close(fd)
        except Exception as exc:
            self._TwinSoulsDebugLog("Twin Souls: history write error %s" %
                                    ascii_text(exc))

    def _TwinSoulsTraceState(self, window, snapshot):
        raw_state = getattr(window, "state", None)
        cooldown = self._TwinSoulsCooldownRemaining(window)
        open_pending = bool(getattr(window, "openPending", False))
        key = (raw_state, snapshot.state, cooldown, open_pending,
               snapshot.pairs_found, snapshot.pair_count,
               snapshot.awaiting_flip, snapshot.busy)
        if key == self.twin_souls_trace_key:
            return
        self.twin_souls_trace_key = key
        self.AddLine(
            "Twin Souls trace: raw_state=%r state=%s cooldown=%s openPending=%s "
            "pairs=%d/%d awaiting=%s busy=%s" %
            (raw_state, snapshot.state, cooldown, open_pending,
             snapshot.pairs_found, snapshot.pair_count,
             snapshot.awaiting_flip, snapshot.busy))

    def _DuelWindow(self):
        """Return the duel window, or None when disabled or not yet discovered."""
        if not self.yinyang_duel_enabled:
            return None
        return self.FindRuntimeObject("YinYangDuelWindow", ())

    def _DuelOwnsSlot(self, window=None):
        """True while a duel is actively playing (state 2/3/4)."""
        if window is None:
            window = self._DuelWindow()
        return window is not None and getattr(window, "state", None) in (2, 3, 4)

    def _DuelStartable(self, window=None):
        """True when the duel is enabled, idle, off cooldown, and below its limit.

        This is the signal that lets the duel claim the slot to *start* a new
        duel; an enabled-but-idle duel on cooldown or at its daily limit is not
        startable and therefore yields the slot to Twin Souls.
        """
        if window is None:
            window = self._DuelWindow()
        if window is None:
            return False
        if getattr(window, "state", None) != 0:
            return False
        used = int(getattr(window, "duelsUsedHwid", 0) or 0)
        maximum = int(getattr(window, "duelsMaxHwid", 0) or 0)
        if maximum > 0 and used >= maximum:
            return False
        if self._DuelCooldownRemaining(window) > 0:
            return False
        return True

    def _TwinSoulsArbiterOwner(self):
        window = self._DuelWindow()
        duel_owns = self._DuelOwnsSlot(window)
        duel_startable = self._DuelStartable(window)
        twin_owns = (self.twin_souls_tracker.has_pending_flip() or
                     self.twin_souls_tracker.has_pending_start())
        return resolve_minigame_owner(self.yinyang_duel_enabled, duel_owns,
                                      duel_startable,
                                      self.twin_souls_enabled, twin_owns)

    def _TwinSoulsSummary(self, snapshot):
        if snapshot.time_remaining is not None:
            return "%d/%d pairs, %ds left" % (snapshot.pairs_found,
                                              snapshot.pair_count,
                                              int(snapshot.time_remaining))
        return "%d/%d pairs" % (snapshot.pairs_found, snapshot.pair_count)

    def _TwinSoulsDecisionEvent(self, snapshot, knowledge, decision):
        return {
            "event": "decision",
            "dispatched": 0,
            "board_id": snapshot.board_id,
            "state": snapshot.state,
            "phase": snapshot.phase,
            "pairs_found": snapshot.pairs_found,
            "cell_count": snapshot.cell_count,
            "open_cells": list(snapshot.open_cells),
            "matched_cells": sorted(snapshot.matched_cells),
            "known_face_count": len(knowledge.known_face_by_cell),
            "known_pair_count": decision["known_pair_count"],
            "unknown_count": decision["unknown_cell_count"],
            "selected_cell": decision["cell_index"],
            "selected_known_face": decision["face"],
            "expected_mate": decision["mate_cell"],
            "decision_mode": decision["mode"],
            "time_remaining": snapshot.time_remaining,
            "bonus_remaining": snapshot.bonus_remaining,
            "plays_used": snapshot.plays_used,
            "plays_max": snapshot.plays_max,
            "plays_used_hwid": snapshot.plays_used_hwid,
            "plays_max_hwid": snapshot.plays_max_hwid,
        }

    def _TwinSoulsHandlePlaying(self, window, snapshot, now):
        tracker = self.twin_souls_tracker
        if snapshot.board_id != self.twin_souls_last_board:
            self.twin_souls_last_board = snapshot.board_id
            self._TwinSoulsRecordEvent({"event": "board_start",
                                        "board_id": snapshot.board_id,
                                        "cell_count": snapshot.cell_count,
                                        "pair_count": snapshot.pair_count})
        tracker.resolve_pending_flip(snapshot, now)
        if tracker.has_pending_flip():
            self._TwinSoulsStatus("waiting for reveal")
            return
        if snapshot.awaiting_flip or snapshot.busy:
            self._TwinSoulsStatus("waiting for animation")
            return
        knowledge = tracker.knowledge()
        decision = self.twin_souls_solver.choose_cell(snapshot, knowledge)
        if decision["cell_index"] is None:
            self._TwinSoulsStatus("%s (%s)" % (self._TwinSoulsSummary(snapshot),
                                               decision["reason"]))
            return
        self._TwinSoulsRecordEvent(
            self._TwinSoulsDecisionEvent(snapshot, knowledge, decision))
        card = self._TwinSoulsResolveCell(window, snapshot,
                                          decision["cell_index"])
        if card is None:
            self._TwinSoulsStatus("chosen cell unavailable; revalidating")
            return
        if not self.twin_souls_adapter.dispatch_flip(card):
            self._TwinSoulsStatus(
                "%s; next cell %d (%s) - flip unavailable" %
                (self._TwinSoulsSummary(snapshot), decision["cell_index"],
                 decision["mode"]))
            return
        tracker.mark_pending_flip(decision["cell_index"], snapshot)

    def _TwinSoulsResolveCell(self, window, snapshot, cell):
        if window is None:
            return None
        cards = getattr(window, "cards", None)
        pairs, ok, _reason = enumerate_memory_cards(cards)
        if not ok:
            return None
        for index, card in pairs:
            if index == cell:
                return card
        return None

    def _TwinSoulsHandleFinishing(self, snapshot):
        self.twin_souls_tracker.clear_pending_start()
        self.twin_souls_tracker.clear_pending_flip()
        if (snapshot.board_id == self.twin_souls_last_board and
                self.twin_souls_last_board != self.twin_souls_last_finished_board):
            self.twin_souls_last_finished_board = snapshot.board_id
            self._TwinSoulsRecordEvent({"event": "board_finish",
                                        "board_id": snapshot.board_id,
                                        "pairs_found": snapshot.pairs_found,
                                        "pair_count": snapshot.pair_count})
            self.AddLine("Twin Souls: board finished (%d/%d pairs)" %
                         (snapshot.pairs_found, snapshot.pair_count))
        self._TwinSoulsStatus("finished; waiting for idle/cooldown")

    def _TwinSoulsHandleIdle(self, window, snapshot):
        cooldown = self._TwinSoulsCooldownRemaining(window)
        if cooldown > 0:
            self.twin_souls_tracker.clear_pending_start()
            self.twin_souls_tracker.clear_pending_flip()
            self._TwinSoulsStatus("cooldown %ds (%d/%d daily, %d/%d HWID)" %
                                  (int(cooldown), snapshot.plays_used,
                                   snapshot.plays_max, snapshot.plays_used_hwid,
                                   snapshot.plays_max_hwid))
            return
        if snapshot.plays_max <= 0 and snapshot.plays_max_hwid <= 0:
            self._TwinSoulsStatus("waiting for limits/state")
            return
        if (self.twin_souls_tracker.has_pending_start() or
                bool(getattr(window, "openPending", False))):
            self._TwinSoulsStatus("start pending")
            return
        if not self.twin_souls_adapter.dispatch_start(window):
            self._TwinSoulsStatus("idle; start unavailable")
            return
        self.twin_souls_tracker.mark_pending_start()
        self._TwinSoulsStatus("start dispatched")

    def PollTwinSouls(self, now):
        if not self.twin_souls_enabled:
            return
        if self.boss_enabled and self.boss_state in BOSS_SWEEP_BUSY_STATES:
            self._TwinSoulsStatus("waiting for Boss Sweep")
            return
        if now < self.twin_souls_next_poll:
            return
        if self.twin_souls_last_state in (TWIN_SOULS_STATE_PLAYING,
                                          TWIN_SOULS_STATE_FINISHING):
            interval = TWIN_SOULS_ACTIVE_POLL_SECONDS
        else:
            interval = TWIN_SOULS_IDLE_POLL_SECONDS
        self.twin_souls_next_poll = now + interval
        try:
            window = self._TwinSoulsDiscover(now)
            if window is None:
                self._TwinSoulsStatus("finding window")
                return
            snapshot, error = self.twin_souls_tracker.observe(window, now)
            if snapshot is None:
                self._TwinSoulsStatus("waiting for state: %s" % (error or "unreadable"))
                return
            self.twin_souls_last_state = snapshot.state
            self._TwinSoulsTraceState(window, snapshot)
            reached = self._TwinSoulsLimitReached(snapshot)
            if reached:
                self._TwinSoulsDisableForLimit(reached)
                return
            owner = self._TwinSoulsArbiterOwner()
            if owner != "twin_souls":
                if owner == "duel":
                    self._TwinSoulsStatus("waiting for Yin Yang Duel")
                else:
                    self._TwinSoulsStatus("waiting for minigame slot")
                return
            if snapshot.state == TWIN_SOULS_STATE_FINISHING:
                self._TwinSoulsHandleFinishing(snapshot)
                return
            if snapshot.state == TWIN_SOULS_STATE_PLAYING:
                self._TwinSoulsHandlePlaying(window, snapshot, now)
                return
            self._TwinSoulsHandleIdle(window, snapshot)
        except Exception as exc:
            problem = ascii_text(exc)
            if problem != self.twin_souls_last_error:
                self.AddLine("Twin Souls error: %s" % problem)
                self.twin_souls_last_error = problem
            self.twin_souls_next_poll = now + TWIN_SOULS_ERROR_RETRY_SECONDS
            self._TwinSoulsStatus("error; retrying")

    def ReadBossTimer(self):
        if self.boss_timer is None:
            return None
        value = self.boss_timer.GetTimeRemaining()
        if isinstance(value, (tuple, list)):
            if not value:
                return None
            value = value[0]
        return float(value)

    def MarkBoss(self):
        try:
            vid = int(player.GetTargetVID())
            if vid <= 0:
                raise ValueError("select the boss first")
            vnum = int(chr.GetVirtualNumber(vid))
            name = ascii_text(chr.GetNameByVID(vid))
            boss_position = tuple(chr.GetPixelPosition(vid)[:2])
            player_position = tuple(player.GetMainCharacterPosition()[:2])
            channel = int(net.GetChannelNumber())
            map_name = ascii_text(background.GetCurrentMapName())
            if channel <= 0:
                raise ValueError("current channel is unavailable")
            if self.anchor_position is not None and self.anchor_map != map_name:
                raise ValueError("boss and Metin anchor must be on the same map")
        except Exception as exc:
            self.AddLine("Mark Boss error: %s" % exc)
            return
        if self.boss_enabled:
            self.StopBossSweep("Boss Sweep stopped for new mark", False)
        if self.anchor_position is None:
            self.anchor_position = player_position
            self.anchor_channel = channel
            self.anchor_map = map_name
            self.anchor_button.SetText("Unanchor")
            self.anchor_label.SetText("Circle: anchored at %d, %d on CH%d" %
                                      (player_position[0], player_position[1], channel))
        self.boss_vnum = vnum
        self.boss_name = name or "Boss"
        self.boss_position = boss_position
        self.boss_map = map_name
        self.boss_mark_channel = channel
        self.boss_label.SetText("%s [vnum %d], CH%d" %
                                (self.boss_name, self.boss_vnum, channel))
        self.UpdateMapHeading()
        self.ClearMap()
        self.next_scan = 0.0
        self.AddLine("Boss marked: %s [vnum %d] at %d, %d on CH%d; return anchor %d, %d on CH%d" %
                     (self.boss_name, self.boss_vnum,
                      boss_position[0], boss_position[1], channel,
                      self.anchor_position[0], self.anchor_position[1],
                      self.anchor_channel))
        self.FindBossRuntime()
        try:
            channel_count = int(self.boss_switch_dialog.GetChannelCount())
        except Exception:
            channel_count = 0
        self.AddLine("Boss runtime check: timer=%s channels=%d" %
                     ("yes" if self.boss_timer is not None else "no",
                      channel_count))

    def GetBossChannels(self):
        count = int(self.boss_switch_dialog.GetChannelCount())
        if count <= 0 or count > 20:
            raise ValueError("invalid channel count %d" % count)
        original = int(self.anchor_channel)
        channels = [original]
        channels.extend(channel for channel in range(1, count + 1)
                        if channel != original)
        return channels

    def ToggleBossSweep(self):
        if self.boss_enabled:
            self.StopBossSweep("Boss Sweep OFF", False)
            return
        self.AddLine("Boss Sweep unavailable: temporarily disabled in this "
                     "Hunter-focused change")
        self.boss_label.SetText("Boss Sweep unavailable")

    def PauseMetinQueueForBoss(self):
        # Boss Sweep is unavailable; retained for later repair.
        self.boss_saved_hunter_enabled = bool(self.hunter_enabled)
        try:
            self.boss_saved_queue_enabled = bool(player.MetinQueueIsEnabled())
        except Exception:
            self.boss_saved_queue_enabled = False
        self.DisableAndClearMetinQueue()
        self.boss_modes_paused = True

    def RestoreAfterBoss(self):
        self.StopBossAttack()
        if self.boss_saved_mouse_func is not None:
            try:
                player.SetMouseFunc(player.MBT_LEFT, self.boss_saved_mouse_func)
            except Exception:
                pass
            self.boss_saved_mouse_func = None
        if self.boss_modes_paused:
            try:
                player.MetinQueueSetEnabled(1 if self.boss_saved_queue_enabled else 0)
            except Exception:
                pass
            self.hunter_enabled = bool(self.boss_saved_hunter_enabled)
            self.hunter_button.SetText("ON" if self.hunter_enabled else "OFF")
            self.hunter_label.SetText("Queue: boss sweep finished")
        self.boss_modes_paused = False
        self.boss_saved_hunter_enabled = False
        self.boss_saved_queue_enabled = False

    def StopBossSweep(self, message, keep_watching):
        self.RestoreAfterBoss()
        self.boss_target_vid = 0
        self.boss_target_missing_since = None
        self.boss_missing_since = None
        self.boss_target_channel = None
        self.boss_state = BOSS_WAIT_TIMER if keep_watching else BOSS_IDLE
        if not keep_watching:
            self.boss_enabled = False
            self.boss_button.SetText("OFF")
        self.boss_label.SetText(message)
        self.AddLine(message)

    def BeginBossSweep(self):
        try:
            self.PauseMetinQueueForBoss()
            self.boss_channels = self.GetBossChannels()
        except Exception as exc:
            self.StopBossSweep("Boss Sweep start error: %s" % exc, False)
            return
        self.boss_channel_index = 0
        self.boss_timer_armed = False
        current = int(net.GetChannelNumber())
        self.AddLine("Boss is up; starting channel sweep from CH%d" % current)
        if current != self.boss_channels[0]:
            self.RequestBossChannel(self.boss_channels[0])
        else:
            self.StartBossFind()

    def StartBossSpawnWait(self):
        now = time.time()
        self.boss_state = BOSS_WAIT_SPAWN
        self.boss_state_started = now
        self.boss_deadline = now + BOSS_SPAWN_GRACE_SECONDS
        self.boss_timer_armed = False
        self.boss_label.SetText("Waiting for %s to appear" % self.boss_name)
        self.AddLine("Boss timer reached zero; waiting %.0fs for %s to appear" %
                     (BOSS_SPAWN_GRACE_SECONDS, self.boss_name))

    def StartBossFind(self):
        now = time.time()
        self.boss_state = BOSS_FIND
        self.boss_state_started = now
        self.boss_deadline = now + BOSS_ABSENCE_GRACE_SECONDS
        self.boss_missing_since = now
        self.boss_target_vid = 0
        self.boss_target_missing_since = None
        channel = int(net.GetChannelNumber())
        self.boss_label.SetText("CH%d: looking for %s (3s)" %
                                (channel, self.boss_name))
        self.AddLine("CH%d: looking for boss for 3 seconds" % channel)

    def FindMarkedBoss(self):
        best = None
        center_x, center_y = self.boss_position
        for vid in visible_vids():
            try:
                if int(chr.GetVirtualNumber(vid)) != self.boss_vnum:
                    continue
                px, py = chr.GetPixelPosition(vid)[:2]
                distance = int(((px - center_x) ** 2 + (py - center_y) ** 2) ** 0.5)
                if distance > self.radius:
                    continue
                candidate = (distance, int(vid), px, py)
                if best is None or candidate < best:
                    best = candidate
            except Exception:
                continue
        return best

    def StartBossAttack(self, candidate):
        raise RuntimeError("Boss Sweep unavailable: temporarily disabled")

    def StopBossAttack(self):
        try:
            player.SetAttackKeyState(False)
        except Exception:
            pass
        if self.boss_modes_paused:
            try:
                self.DisableAndClearMetinQueue()
            except Exception:
                pass
        try:
            player.ClearTarget()
        except Exception:
            pass

    def SelectChannelInDialog(self, channel):
        select = getattr(self.boss_switch_dialog,
                         "_MoveChannelDialog__SelectChannel", None)
        if select is None:
            raise AttributeError("channel select method unavailable")
        try:
            self.boss_switch_dialog.Show()
        except Exception:
            pass
        selected = None
        for value in (channel, channel - 1):
            if value < 0:
                continue
            select(value)
            try:
                selected = int(self.boss_switch_dialog.GetChannelNumber())
            except Exception:
                selected = channel
            if selected == channel:
                break
        if selected != channel:
            raise ValueError("channel dialog selected %s, expected %d" %
                             (selected, channel))
        self.boss_switch_dialog.AcceptButton()

    def RequestBossChannel(self, channel, returning=False):
        self.StopBossAttack()
        self.boss_target_channel = int(channel)
        self.boss_returning = bool(returning)
        self.boss_state = BOSS_CHANGE_CHANNEL
        self.boss_state_started = time.time()
        self.boss_deadline = self.boss_state_started + BOSS_CHANNEL_TIMEOUT_SECONDS
        self.boss_label.SetText("Changing to CH%d" % channel)
        self.AddLine("Changing to CH%d%s" %
                     (channel, " to return" if returning else ""))
        self.SelectChannelInDialog(channel)
        self.boss_state = BOSS_WAIT_CHANNEL

    def AdvanceBossChannel(self):
        self.StopBossAttack()
        self.boss_channel_index += 1
        if self.boss_channel_index < len(self.boss_channels):
            self.RequestBossChannel(self.boss_channels[self.boss_channel_index])
            return
        current = int(net.GetChannelNumber())
        if current != self.anchor_channel:
            self.RequestBossChannel(self.anchor_channel, True)
        else:
            self.StartReturnToAnchor()

    def StartReturnToAnchor(self):
        self.boss_state = BOSS_RETURN_POSITION
        self.boss_state_started = time.time()
        self.boss_deadline = self.boss_state_started + 30.0
        self.boss_return_best_distance = None
        self.boss_return_last_progress = self.boss_state_started
        self.boss_return_move_sent = False
        self.boss_label.SetText("Returning to marked spot on CH%d" % self.anchor_channel)
        self.AddLine("Returning to Metin anchor %d, %d on CH%d" %
                     (self.anchor_position[0], self.anchor_position[1],
                      self.anchor_channel))

    def BossVIDVisible(self, vid):
        try:
            return int(vid) in visible_vids()
        except Exception:
            return True

    def SnapshotUpdatedSince(self, timestamp):
        try:
            if os.stat(SNAPSHOT).st_mtime + 0.05 < timestamp:
                return False
            visible_vids()
            return True
        except Exception:
            return False

    def UpdateBossSweep(self, now, player_position):
        if not self.boss_enabled:
            return
        if now < self.boss_next_poll:
            return
        if self.boss_state == BOSS_WAIT_TIMER:
            self.boss_next_poll = now + BOSS_TIMER_POLL_SECONDS
        else:
            self.boss_next_poll = now + BOSS_ACTIVE_POLL_SECONDS
        try:
            if self.boss_state == BOSS_WAIT_TIMER:
                candidate = self.FindMarkedBoss()
                if candidate is not None:
                    self.AddLine("Boss visible while waiting; starting sweep without timer edge")
                    self.BeginBossSweep()
                    return
                remaining = self.ReadBossTimer()
                if remaining is None:
                    return
                if remaining > 0:
                    self.boss_timer_armed = True
                    self.boss_label.SetText("%s in %ds" %
                                            (self.boss_name, int(remaining)))
                    return
                if self.boss_timer_armed:
                    self.StartBossSpawnWait()
                return

            if self.boss_state == BOSS_WAIT_SPAWN:
                candidate = self.FindMarkedBoss()
                if candidate is not None:
                    self.AddLine("%s appeared; starting sweep" % self.boss_name)
                    self.BeginBossSweep()
                    return
                if now >= self.boss_deadline:
                    self.AddLine("%s did not appear within %.0fs; waiting for next timer" %
                                 (self.boss_name, BOSS_SPAWN_GRACE_SECONDS))
                    self.boss_state = BOSS_WAIT_TIMER
                    self.boss_label.SetText("Waiting for %s timer" % self.boss_name)
                    return
                self.boss_label.SetText("Waiting for %s to appear (%.0fs)" %
                                        (self.boss_name,
                                         max(0.0, self.boss_deadline - now)))
                return

            if self.boss_state == BOSS_FIND:
                candidate = self.FindMarkedBoss()
                if candidate is not None:
                    self.StartBossAttack(candidate)
                elif now >= self.boss_deadline:
                    self.AddLine("CH%d: boss absent after 3-second scan" %
                                 int(net.GetChannelNumber()))
                    self.AdvanceBossChannel()
                return

            if self.boss_state == BOSS_ATTACK:
                if not self.BossVIDVisible(self.boss_target_vid):
                    if self.boss_target_missing_since is None:
                        self.boss_target_missing_since = now
                    if now - self.boss_target_missing_since >= BOSS_KILL_CONFIRM_SECONDS:
                        self.AddLine("CH%d: boss kill confirmed" %
                                     int(net.GetChannelNumber()))
                        self.AdvanceBossChannel()
                else:
                    self.boss_target_missing_since = None
                if now >= self.boss_deadline:
                    self.AddLine("CH%d: boss combat timed out; continuing" %
                                 int(net.GetChannelNumber()))
                    self.AdvanceBossChannel()
                return

            if self.boss_state == BOSS_WAIT_CHANNEL:
                channel_ready = (int(net.GetChannelNumber()) == self.boss_target_channel and
                                 player_position is not None and
                                 self.SnapshotUpdatedSince(self.boss_state_started))
                if channel_ready:
                    current_map = ascii_text(background.GetCurrentMapName())
                    if current_map != self.anchor_map:
                        raise RuntimeError("loaded unexpected map %s" % current_map)
                    self.boss_state = BOSS_SETTLE_CHANNEL
                    self.boss_state_started = now
                    self.boss_deadline = now + BOSS_LOAD_SETTLE_SECONDS
                    self.boss_label.SetText("CH%d loaded; waiting 1 second" %
                                            self.boss_target_channel)
                    self.AddLine("CH%d loaded; settling for 1 second" %
                                 self.boss_target_channel)
                elif now >= self.boss_deadline:
                    raise RuntimeError("channel %d load timeout" % self.boss_target_channel)
                return

            if self.boss_state == BOSS_SETTLE_CHANNEL:
                if now < self.boss_deadline:
                    return
                if self.boss_returning:
                    self.StartReturnToAnchor()
                else:
                    self.StartBossFind()
                return

            if self.boss_state == BOSS_RETURN_POSITION:
                fresh_position = tuple(player.GetMainCharacterPosition()[:2])
                dx = fresh_position[0] - self.anchor_position[0]
                dy = fresh_position[1] - self.anchor_position[1]
                distance = (dx * dx + dy * dy) ** 0.5
                if distance <= BOSS_RETURN_DISTANCE:
                    self.StopBossSweep("Sweep complete; back on CH%d at Metin anchor" %
                                       self.anchor_channel, True)
                    return
                if (self.boss_return_best_distance is None or
                        distance <= (self.boss_return_best_distance -
                                     BOSS_RETURN_PROGRESS_DISTANCE)):
                    self.boss_return_best_distance = distance
                    self.boss_return_last_progress = now
                if not self.boss_return_move_sent:
                    chr.MoveToDestPosition(player.GetMainCharacterIndex(),
                                           self.anchor_position[0], self.anchor_position[1])
                    self.boss_return_move_sent = True
                elif (now - self.boss_return_last_progress >=
                      BOSS_RETURN_STALL_SECONDS):
                    if distance <= self.radius:
                        self.StopBossSweep(
                            "Sweep complete on CH%d; return blocked inside Metin circle" %
                            self.anchor_channel, True)
                        return
                    chr.MoveToDestPosition(player.GetMainCharacterIndex(),
                                           self.anchor_position[0], self.anchor_position[1])
                    self.boss_return_best_distance = distance
                    self.boss_return_last_progress = now
                if now >= self.boss_deadline:
                    self.StopBossSweep("Sweep complete on CH%d; return movement timed out" %
                                       self.anchor_channel, True)
                return
        except Exception as exc:
            problem = ascii_text(exc)
            if problem != self.boss_last_error:
                self.AddLine("Boss Sweep error: %s" % problem)
                self.boss_last_error = problem
            self.StopBossSweep("Boss Sweep stopped after error", False)

    def TogglePanel(self):
        if self.IsShow():
            self.MinimizePanel()
        else:
            self.Show()
            disk_log("Panel opened with Left Ctrl+F8")

    def MinimizePanel(self):
        self.Hide()
        disk_log("Panel minimized; automation continues")

    def PollHotkey(self):
        try:
            down = bool(app.IsPressed(app.DIK_LCONTROL) and app.IsPressed(app.DIK_F8))
        except Exception:
            return
        if down and not self.hotkey_down:
            self.TogglePanel()
        self.hotkey_down = down

    def ReadRadius(self):
        text = self.radius_edit.GetText().strip()
        if not text.isdigit():
            raise ValueError("radius must be a whole number")
        radius = int(text)
        if radius < MIN_RADIUS or radius > MAX_RADIUS:
            raise ValueError("radius must be %d-%d" % (MIN_RADIUS, MAX_RADIUS))
        return radius

    def Start(self):
        if not self.IsGameplayAvailable():
            self.AddLine("Start blocked: enter the playable game world first")
            return
        try:
            new_radius = self.ReadRadius()
        except Exception as exc:
            self.AddLine("Radius error: %s" % exc)
            return
        if self.running:
            self.RefreshRadius()
            self.AddLine("Already running; radius now %d" % self.radius)
            return
        self.radius = new_radius
        self.running = True
        self.next_scan = 0.0
        self.last_radius_error = None
        self.last_scan_error = None
        self.state_label.SetText("Running. Radius: %d game units" % self.radius)
        self.UpdateMapHeading()
        self.AddLine("Started; radius=%d" % self.radius)

    def Stop(self):
        if self.boss_enabled:
            self.StopBossSweep("Boss Sweep stopped", False)
        self.hunter_controller.stop("stopped")
        self.running = False
        self.hunter_enabled = False
        self.hunter_button.SetText("OFF")
        self.hunter_label.SetText("Queue: stopped and cleared")
        self.ClearMap()
        self.state_label.SetText("Stopped. Set radius, then click Start.")
        self.AddLine("Stopped")

    def Dispose(self):
        if self.manual_queue_logger.active:
            self.manual_queue_logger.stop(hunter_now_ms(), "panel_disposed")
        self.watcher.Hide()
        self.Stop()
        self.Hide()

    def ToggleMetinHunter(self):
        if self.boss_modes_paused:
            self.AddLine("Metin Hunter unavailable during Boss Sweep")
            return
        if self.hunter_enabled:
            self.hunter_controller.stop("stopped")
            self.hunter_enabled = False
            self.hunter_button.SetText("OFF")
            self.hunter_label.SetText("Queue: stopped")
            self.AddLine("Metin Hunter OFF")
            return
        if self.hunter_observer is None:
            self.AddLine("Metin Hunter unavailable: native observer missing")
            return
        if not self.running:
            self.Start()
            if not self.running:
                return
        self.hunter_controller.user_requested_on = True
        state = self.hunter_controller.start()
        if state == self.hunter_controller.RUNNING:
            self.hunter_enabled = True
            self.hunter_button.SetText("ON")
        else:
            self.hunter_enabled = False
            self.hunter_button.SetText("OFF")
        self.hunter_label.SetText(self.hunter_controller.status_text)


    def Scan(self, player_position):
        vids = visible_vids()
        x, y = (self.anchor_position or player_position)[:2]
        try:
            snapshot = self.hunter_selector.publish(
                vids, player_position, self.anchor_position, self.radius,
                self.hunter_controller.epoch, hunter_now_ms())
        except Exception as exc:
            self.AddLine("Metin Hunter error: %s" % ascii_text(exc))
            self.ClearMap()
            return

        # Red dots/counts use the exact same immutable range snapshot as Hunter.
        # Native admission and queue ownership remain later, separate checks.
        candidates = snapshot["candidates"]
        candidate_vids = set(candidate["vid"] for candidate in candidates)
        found = {}
        metin_offsets = []
        for candidate in candidates:
            gx, gy = candidate["x"], candidate["y"]
            metin_offsets.append((gx - x, gy - y))
            key = (candidate["vnum"], candidate["name"])
            found.setdefault(key, []).append(int(((gx - x) ** 2 + (gy - y) ** 2) ** 0.5))
        outside_offsets = []
        other_offsets = []
        radius2 = float(self.radius) ** 2
        for vid in vids:
            if vid in candidate_vids:
                continue
            try:
                vnum = chr.GetVirtualNumber(vid)
                is_metin = nonplayer.IsMonsterStone(vnum)
                if not is_metin and len(other_offsets) >= len(self.map_others):
                    continue
                px, py = chr.GetPixelPosition(vid)[:2]
                circle_distance2 = (px - x) ** 2 + (py - y) ** 2
                if circle_distance2 > radius2:
                    continue
                if is_metin:
                    player_distance2 = ((px - player_position[0]) ** 2 +
                                        (py - player_position[1]) ** 2)
                    if player_distance2 > radius2:
                        outside_offsets.append((px - x, py - y))
                elif circle_distance2 > 1:
                    other_offsets.append((px - x, py - y))
            except Exception:
                continue  # Entity may have despawned after the native snapshot.
        mode = "anchored" if self.anchor_position is not None else "following"
        if found:
            parts = []
            for (vnum, name), distances in sorted(found.items()):
                parts.append("%s [vnum %d] x%d, nearest %d" %
                             (name or "Metin", vnum, len(distances), min(distances)))
            summary = "radius=%d %s: %s" % (self.radius, mode, "; ".join(parts))
        else:
            summary = "radius=%d %s: no metins visible in Hunter range" % (self.radius, mode)
        summary += "; outside player reach=%d" % len(outside_offsets)
        self.UpdateMap(metin_offsets, other_offsets, outside_offsets)
        self.AddLine(summary)
        try:
            self.hunter_controller.on_scan(snapshot)
            if (self.hunter_controller.priority_enabled and
                    self.hunter_controller.priority_state ==
                    HunterController.PRIORITY_NONE):
                priority_vid = None
                for cand in snapshot["candidates"]:
                    if PRIORITY_EVENT_METIN_NAME in cand["name"].lower():
                        priority_vid = cand["vid"]
                        break
                if priority_vid is not None:
                    self.hunter_controller.request_priority(priority_vid)
        except Exception as exc:
            self.AddLine("Metin Hunter error: %s" % ascii_text(exc))

    def RefreshRadius(self):
        try:
            new_radius = self.ReadRadius()
            self.last_radius_error = None
        except ValueError as exc:
            if self.last_radius_error != str(exc):
                self.AddLine("Radius input: %s; using %d" % (exc, self.radius))
                self.last_radius_error = str(exc)
            return
        if new_radius == self.radius:
            return
        self.radius = new_radius
        self.state_label.SetText("Running. Radius: %d game units" % self.radius)
        self.UpdateMapHeading()
        self.ClearMap()
        self.next_scan = 0.0
        self.AddLine("Radius changed to %d" % self.radius)

    def _tick_hunter(self, now_ms):
        """Run controller maintenance (reconciliation/cleanup) even when the
        additions toggle is OFF; candidate refill still needs a fresh scan."""
        if self.hunter_controller.state == HunterController.OFF:
            return
        try:
            self.hunter_controller.tick(now_ms)
            self.hunter_label.SetText(self.hunter_controller.status_text)
            if self.hunter_controller.state == HunterController.ERROR:
                self.hunter_enabled = False
                self.hunter_button.SetText("OFF")
        except Exception as exc:
            self.AddLine("Metin Hunter error: %s" % ascii_text(exc))

    def OnUpdate(self):
        now = time.time()
        now_ms = hunter_now_ms()
        # This opt-in observer is independent of scanner/Hunter/gameplay state.
        # It runs first so invalid/session transitions are recorded too.
        self.manual_queue_logger.tick(now_ms)
        if not self.IsGameplayAvailable(now):
            return
        # Maintenance and audit observation run before the Reaction early return
        # so pending reconciliation/cleanup and coverage logging are never
        # bypassed while a reaction window is visible.
        self._tick_hunter(now_ms)
        self.hunter_audit.observe(now_ms)
        if self.PollReactionGame(now):
            return
        self.ResumeAfterReaction(now)
        if not self.running:
            return
        player_position = self.last_player_position
        if now >= self.player_next_poll:
            self.player_next_poll = now + PLAYER_POLL_SECONDS
            try:
                player_position = player.GetMainCharacterPosition()
                self.last_player_position = player_position
                self.UpdatePlayerMarker(player_position)
            except Exception:
                player_position = None
                self.last_player_position = None
        try:
            self.RefreshRadius()
        except Exception:
            problem = ascii_text(traceback.format_exc().splitlines()[-1])
            if problem != self.last_radius_error:
                self.AddLine("Radius update error: %s" % problem)
                self.last_radius_error = problem
        self.UpdateBossSweep(now, player_position)
        self.PollYinYangDuel(now)
        self.PollTwinSouls(now)
        if now >= self.next_scan:
            try:
                if player_position is None:
                    player_position = player.GetMainCharacterPosition()
                self.Scan(player_position)
                self.last_scan_error = None
            except Exception:
                problem = ascii_text(traceback.format_exc().splitlines()[-1])
                if problem != self.last_scan_error:
                    self.AddLine("Scan error: %s" % problem)
                    self.last_scan_error = problem
                self.ClearMap()
            self.next_scan = now + random.uniform(0.85, 1.15)


try:
    existing = getattr(__main__, "_lirin_metin_scanner", None)
    if existing is not None and getattr(existing, "feature_version", 0) == FEATURE_VERSION:
        existing.Show()
        disk_log("Panel reopened in PID %d" % os.getpid())
    else:
        if existing is not None:
            if hasattr(existing, "Dispose"):
                existing.Dispose()
            else:
                existing.Stop()
                existing.Hide()
        __main__._lirin_metin_scanner = MetinScanner()
        disk_log("Panel created in PID %d" % os.getpid())
except:
    disk_log("Panel creation failed: %s" % ascii_text(traceback.format_exc()))
    raise
