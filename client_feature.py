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

try:
    INTEGER_TYPES = (int, long)
except NameError:
    INTEGER_TYPES = (int,)


# execfile preserves the real script filename on the executing frame even
# when the embedded __main__ module has no reliable __file__ value.
DIRECTORY = os.path.dirname(os.path.abspath(sys._getframe().f_code.co_filename))
SNAPSHOT = os.path.join(DIRECTORY, "client_feature_vids.txt")
LOG = os.path.join(DIRECTORY, "metin_scanner.log")
CONFIG = os.path.join(DIRECTORY, "client_feature_config.txt")
MIN_RADIUS = 100
MAX_RADIUS = 10000
DEFAULT_RADIUS = 2500
FEATURE_VERSION = 43
HUNTER_LIMIT = 5
HUNTER_BURST_DELAY_MIN = 0.70
HUNTER_BURST_DELAY_MAX = 2.50
# Time-driven refill: after the queue is full, wait this noisy interval before
# refilling again, matching the observed ~50s human rhythm instead of refilling
# the instant a slot frees.
HUNTER_REFILL_MIN = 35.0
HUNTER_REFILL_MAX = 70.0
PRIORITY_EVENT_METIN_NAME = "legendary metinstone"
PRIORITY_EVENT_MISSING_SECONDS = 1.5
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
YINYANG_DUEL_ATTEMPTS_PER_DAY = 8
YINYANG_DUEL_HISTORY_JSONL = os.path.join(DIRECTORY, "yin_yang_duel_history.jsonl")
YINYANG_DUEL_HISTORY_SCHEMA = 1

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
NATIVE_QUEUE_WRAPPER_ACTIVE = bool(
    getattr(__main__, "_lirin_native_queue_wrapper", False))


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


def emit_synthetic_click():
    """Record a bare synthetic left-click for UI automations (reaction game,
    channel dialog) that a human would click but that never pass through the
    Windows mouse handler.  Calls MetinQueueAdd with the VID 0 sentinel, which
    the native wrapper turns into a click-only record.  No-op without the
    wrapper or while the input recorder is disabled."""
    if not NATIVE_QUEUE_WRAPPER_ACTIVE:
        return
    try:
        player.MetinQueueAdd(0)
    except Exception:
        pass


# Vertical offset (game units) added to a target's world position when
# projecting it to client pixels for the full-dispatch click.  The entity's
# world position is its base, so this lifts the click point into its visible
# body and off the ground plane.  Tunable after a live test.
PROJECT_CLICK_HEIGHT = 100


def _queue_add(vid):
    """Add a VID through the native queue wrapper.  When the client exposes the
    forward projection (player.GetProjectPosition) and the target projects on
    screen, pass the projected client-pixel coordinates so the wrapper can
    reproduce the full WndProc mouse-down/up dispatch instead of forcing the
    picker.  Otherwise fall back to the single-argument binding."""
    if not NATIVE_QUEUE_WRAPPER_ACTIVE:
        return player.MetinQueueAdd(vid)
    project = getattr(player, "GetProjectPosition", None)
    if callable(project):
        try:
            projected = project(vid, PROJECT_CLICK_HEIGHT)
            x = int(projected[0])
            y = int(projected[1])
            if x >= 0 and y >= 0:
                return player.MetinQueueAdd(vid, x, y)
        except Exception:
            pass
    return player.MetinQueueAdd(vid)


def _ui_click(control):
    """Click a UI control through the full-dispatch path at its screen center.

    Returns True when a click was actually dispatched (the control must not be
    re-clicked through its legacy callback), or False when the control lacks
    position/size APIs or the wrapper is inactive (in which case the caller may
    fall back to its legacy callback, since nothing was dispatched)."""
    if not NATIVE_QUEUE_WRAPPER_ACTIVE:
        return False
    try:
        get_pos = getattr(control, "GetGlobalPosition", None)
        get_w = getattr(control, "GetWidth", None)
        get_h = getattr(control, "GetHeight", None)
        if not callable(get_pos) or not callable(get_w) or not callable(get_h):
            return False
        pos = get_pos()
        x = int(pos[0])
        y = int(pos[1])
        cx = x + int(get_w()) // 2
        cy = y + int(get_h()) // 2
        return bool(player.MetinQueueAdd(0, cx, cy))
    except Exception:
        return False


class NativeActionCoordinator(object):
    """Tracks in-flight native actions through an explicit state machine.

    Normal flow: requested -> validated -> dispatched -> awaiting -> completed.
    Any non-terminal state may also become cancelled (phase change or explicit
    cancel), rejected (validation failure), or unknown (deadline or ambiguous
    outcome).  Each action records the phase generation it was requested under
    and a wall-clock deadline."""

    REQUESTED = "requested"
    VALIDATED = "validated"
    DISPATCHED = "dispatched"
    AWAITING = "awaiting"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    UNKNOWN = "unknown"

    _TERMINAL = (COMPLETED, CANCELLED, REJECTED, UNKNOWN)
    _PENDING = (REQUESTED, VALIDATED, DISPATCHED, AWAITING)

    def __init__(self, phase_getter, clock=time.time):
        self._phase_getter = phase_getter
        self._clock = clock
        self._next_id = 1
        self._actions = {}

    def request(self, action_type, target, timeout):
        """Open a request.  Returns a fresh action id."""
        action_id = self._next_id
        self._next_id += 1
        self._actions[action_id] = {
            "type": action_type,
            "target": target,
            "state": self.REQUESTED,
            "phase": self._phase_getter(),
            "deadline": self._clock() + timeout,
            "detail": None,
        }
        return action_id

    def state(self, action_id):
        action = self._actions.get(action_id)
        return action["state"] if action is not None else None

    def _transition(self, action_id, state, detail=None):
        action = self._actions[action_id]
        action["state"] = state
        action["detail"] = detail
        return action

    def validate(self, action_id, ok):
        """REQUESTED -> VALIDATED, or REJECTED when validation fails."""
        action = self._actions[action_id]
        if action["state"] == self.REQUESTED:
            if ok:
                self._transition(action_id, self.VALIDATED)
            else:
                self._transition(action_id, self.REJECTED, "invalid")
        return action["state"]

    def dispatch(self, action_id):
        """VALIDATED -> DISPATCHED -> AWAITING."""
        action = self._actions[action_id]
        if action["state"] == self.VALIDATED:
            self._transition(action_id, self.DISPATCHED)
            self._transition(action_id, self.AWAITING)
        return action["state"]

    def acknowledge(self, action_id, outcome):
        """AWAITING -> COMPLETED/UNKNOWN/REJECTED by the reported outcome."""
        action = self._actions[action_id]
        if action["state"] in (self.DISPATCHED, self.AWAITING):
            terminal = {
                self.COMPLETED: self.COMPLETED,
                self.UNKNOWN: self.UNKNOWN,
                self.REJECTED: self.REJECTED,
            }.get(outcome, self.UNKNOWN)
            self._transition(action_id, terminal, outcome)
        return action["state"]

    def cancel(self, action_id, reason="cancelled"):
        action = self._actions[action_id]
        if action["state"] not in self._TERMINAL:
            self._transition(action_id, self.CANCELLED, reason)
        return action["state"]

    def on_phase_change(self):
        """Cancel every pending action whose phase generation is now stale."""
        current = self._phase_getter()
        for action_id, action in list(self._actions.items()):
            if action["state"] in self._PENDING and action["phase"] != current:
                self._transition(action_id, self.CANCELLED, "phase change")

    def poll(self):
        """Move pending actions past their deadline to UNKNOWN."""
        now = self._clock()
        for action_id, action in list(self._actions.items()):
            if action["state"] in self._PENDING and now >= action["deadline"]:
                self._transition(action_id, self.UNKNOWN, "deadline")

    def has_pending(self):
        return any(a["state"] in self._PENDING for a in self._actions.values())

    def finish(self, action_id):
        """Drop a terminal action so the tracker does not grow unbounded."""
        action = self._actions.get(action_id)
        if action is not None and action["state"] in self._TERMINAL:
            self._actions.pop(action_id, None)


# Map the native wrapper's integer result to a coordinator outcome.
_ADD_RESULT_OUTCOME = {
    1: NativeActionCoordinator.COMPLETED,
    2: NativeActionCoordinator.COMPLETED,
    3: NativeActionCoordinator.UNKNOWN,
    0: NativeActionCoordinator.REJECTED,
}


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


class MetinQueueAdmissionGuard(object):
    """Mirror native per-VID exclusions set through the player bindings."""

    observer_version = 1

    def __init__(self, original_immune=None, original_untargetable=None):
        self.owner = None
        self.immune_vids = set()
        self.untargetable_vids = set()
        self.original_immune = (original_immune or
                                player.SetMetinQueueVIDImmune)
        self.original_untargetable = (original_untargetable or
                                      player.SetMetinQueueVIDUntargetable)

        def set_immune(vid, enabled):
            result = self.original_immune(vid, enabled)
            self._Update(self.immune_vids, "immune", vid, enabled)
            return result

        def set_untargetable(vid, enabled):
            result = self.original_untargetable(vid, enabled)
            self._Update(self.untargetable_vids, "untargetable", vid, enabled)
            return result

        self.set_immune = set_immune
        self.set_untargetable = set_untargetable
        player.SetMetinQueueVIDImmune = self.set_immune
        player.SetMetinQueueVIDUntargetable = self.set_untargetable

    def _Update(self, values, kind, vid, enabled):
        vid = int(vid)
        enabled = bool(enabled)
        if vid == 0:
            changed = bool(values)
            values.clear()
        elif enabled:
            changed = vid not in values
            values.add(vid)
        else:
            changed = vid in values
            values.discard(vid)
        owner = self.owner
        if owner is not None and changed:
            owner.OnNativeQueueVIDState(kind, vid, enabled)

    def SetOwner(self, owner):
        self.owner = owner

    def RejectionReason(self, vid):
        if int(vid) in self.untargetable_vids:
            return "native untargetable VID"
        if int(vid) in self.immune_vids:
            return "native immune VID"
        return None

def get_metin_queue_admission_guard():
    guard = getattr(__main__, "_lirin_metin_queue_admission_guard", None)
    if (guard is None or not hasattr(guard, "SetOwner") or
            getattr(guard, "observer_version", 0) !=
            MetinQueueAdmissionGuard.observer_version):
        original_immune = getattr(guard, "original_immune",
                                  player.SetMetinQueueVIDImmune)
        original_untargetable = getattr(
            guard, "original_untargetable", player.SetMetinQueueVIDUntargetable)
        guard = MetinQueueAdmissionGuard(original_immune, original_untargetable)
        __main__._lirin_metin_queue_admission_guard = guard
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
        self.native_queue_wrapper_active = NATIVE_QUEUE_WRAPPER_ACTIVE
        self.AddFlag("movable")
        self.AddFlag("float")
        self.SetSize(820, 520)
        self.SetPosition(40, 80)
        self.SetTitleName("Metin Radius Scanner")
        self.SetCloseEvent(self.MinimizePanel)
        self.running = False
        self.anchor_position = None
        self.hotkey_down = False
        self.hunter_enabled = False
        self.hunter_queued_vids = set()
        self.hunter_logged_rejections = set()
        self.hunter_initial_fill = True
        self.hunter_batch_add_count = 0
        self.hunter_refilling = False
        self.hunter_next_refill = 0.0
        self.hunter_next_add = 0.0
        self.priority_event_vid = 0
        self.priority_event_vnum = 0
        self.priority_event_name = None
        self.priority_event_missing_since = None
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
        self.player_next_poll = 0.0
        self.last_player_position = None
        self.gameplay_phase = None
        self.gameplay_available = True
        self.gameplay_next_check = 0.0
        self.gameplay_stopped = False
        self.action_coordinator = NativeActionCoordinator(
            lambda: self.gameplay_phase)
        self.config_autoload = False
        self.radius = DEFAULT_RADIUS
        self.next_scan = 0.0
        self.last_radius_error = None
        self.last_scan_error = None
        self.lines = []
        self.radius_label = make_text(self, 15, 47, "Radius:")
        self.radius_slot = ui.SlotBar()
        self.radius_slot.SetParent(self)
        self.radius_slot.SetPosition(75, 42)
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
        self.start_button = make_button(self, 205, "Start", self.Start)
        self.stop_button = make_button(self, 315, "Stop", self.Stop)
        self.anchor_button = make_button(self, 425, "Anchor", self.ToggleAnchor)
        self.config_save_button = make_button(self, 535, "Save", self.SaveConfig)
        self.config_load_button = make_button(self, 625, "Load", self.LoadConfig)
        self.config_auto_button = make_button(self, 715, "Auto OFF", self.ToggleConfigAutoload)
        self.hunter_title = make_text(self, 15, 327, "Metin Hunter")
        self.hunter_button = make_button(self, 110, "OFF", self.ToggleMetinHunter, 322)
        self.hunter_label = make_text(self, 205, 327, "Queue: idle")
        self.anchor_label = make_text(self, 15, 291, "Circle: following character")
        self.state_label = make_text(self, 15, 81, "Stopped. Set radius, then click Start.")
        self.log_labels = []
        for index in range(8):
            self.log_labels.append(make_text(self, 15, 110 + index * 21, ""))
        self.radar_center = (650, 221)
        self.radar_pixels = 112
        self.radar_label = make_text(self, 525, 66, "Local map: radius %d units" % self.radius)
        try:
            background_color = ui.GenerateColor(0.08, 0.14, 0.18, 0.92)
            grid_color = ui.GenerateColor(0.25, 0.34, 0.39, 0.7)
            ring_color = ui.GenerateColor(0.30, 0.72, 1.0, 1.0)
            player_color = ui.GenerateColor(1.0, 0.90, 0.20, 1.0)
            metin_color = ui.GenerateColor(1.0, 0.25, 0.20, 1.0)
            other_color = ui.GenerateColor(0.72, 0.85, 0.85, 1.0)
        except Exception:
            background_color, grid_color = 0xEE15242E, 0xAA405762
            ring_color, player_color = 0xFF55AAFF, 0xFFFFFF33
            metin_color, other_color = 0xFFFF4433, 0xFFBBDDDD
        self.map_background = ui.Bar()
        self.map_background.SetParent(self)
        self.map_background.SetPosition(520, 91)
        self.map_background.SetSize(260, 260)
        self.map_background.SetColor(background_color)
        self.map_background.Show()
        self.map_grid = []
        for x in (565, 607, 650, 693, 735):
            bar = ui.Bar()
            bar.SetParent(self)
            bar.SetPosition(x, 91)
            bar.SetSize(1, 260)
            bar.SetColor(grid_color)
            bar.Show()
            self.map_grid.append(bar)
        for y in (136, 178, 221, 264, 306):
            bar = ui.Bar()
            bar.SetParent(self)
            bar.SetPosition(520, y)
            bar.SetSize(260, 1)
            bar.SetColor(grid_color)
            bar.Show()
            self.map_grid.append(bar)
        self.map_compass = [
            make_text(self, 646, 96, "N"),
            make_text(self, 646, 333, "S"),
            make_text(self, 761, 216, "E"),
            make_text(self, 527, 216, "W"),
        ]
        self.map_ring = []
        for index in range(96):
            angle = 2.0 * math.pi * index / 96.0
            x = int(self.radar_center[0] + self.radar_pixels * math.cos(angle))
            y = int(self.radar_center[1] + self.radar_pixels * math.sin(angle))
            self.map_ring.append(make_radar_dot(self, x, y, 3, ring_color, "."))
        self.map_player = make_radar_dot(self, self.radar_center[0] - 2,
                                         self.radar_center[1] - 2, 6, player_color, "P")
        self.map_metins = []
        self.map_others = []
        for pool, count, color, symbol in (
                (self.map_metins, 32, metin_color, "M"),
                (self.map_others, 64, other_color, ".")):
            for index in range(count):
                dot = make_radar_dot(self, self.radar_center[0],
                                     self.radar_center[1], 5, color, symbol)
                dot.Hide()
                pool.append(dot)
        self.map_count_label = make_text(self, 525, 360,
                                         "Yellow: you  Red: metin  White: other")
        self.boss_title = make_text(self, 15, 399, "Boss Sweep")
        self.boss_mark_button = make_button(self, 110, "Mark Boss", self.MarkBoss, 394)
        self.boss_button = make_button(self, 220, "OFF", self.ToggleBossSweep, 394)
        self.boss_label = make_text(self, 315, 399, "Select a boss, then mark its spot")
        self.reaction_title = make_text(self, 15, 432, "Auto Reaction")
        self.reaction_button = make_button(self, 110, "ON", self.ToggleReaction, 427)
        self.reaction_label = make_text(self, 205, 432, "Watches the yin-yang reaction game")
        self.yinyang_duel_title = make_text(self, 15, 466, "Yin Yang Duel")
        self.yinyang_duel_button = make_button(self, 110, "OFF", self.ToggleYinYangDuel, 461)
        self.yinyang_duel_label = make_text(self, 205, 466, "Plays the Yin Yang Duel minigame")
        self.phase_guard = get_gameplay_phase_guard()
        self.phase_guard.SetOwner(self)
        self.queue_admission_guard = get_metin_queue_admission_guard()
        self.queue_admission_guard.SetOwner(self)
        self.gameplay_phase = self.phase_guard.current_phase
        self.AddLine("Ready. Log file: metin_scanner.log")
        self.AddLine("Native full-input queue wrapper: %s" %
                     ("active" if self.native_queue_wrapper_active else "UNAVAILABLE"))
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

    def AddLine(self, message):
        clean = ascii_text(message)
        disk_log(clean)
        self.lines.append(clean)
        self.lines = self.lines[-8:]
        for index, label in enumerate(self.log_labels):
            row = self.lines[index] if index < len(self.lines) else ""
            label.SetText(row[:60])

    def ClearMap(self):
        for dot in self.map_metins + self.map_others:
            dot.Hide()
        self.map_count_label.SetText("Yellow: you  Red: metin  White: other")

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
            self.reaction_label.SetText("Watches and solves the reaction game" if self.reaction_enabled
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
        """Disable/clear once; native true-to-false already performs a clear."""
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

    def ClearNativeAutomation(self):
        try:
            player.SetAttackKeyState(False)
        except Exception:
            pass
        try:
            self.DisableAndClearMetinQueue()
        except Exception:
            pass
        try:
            player.ClearTarget()
        except Exception:
            pass
        self.hunter_queued_vids.clear()
        self.hunter_logged_rejections.clear()
        self.hunter_initial_fill = True
        self.hunter_batch_add_count = 0
        self.hunter_next_add = 0.0
        self.hunter_refilling = False
        self.hunter_next_refill = 0.0
        self.ResetPriorityEventState()

    def ResetPriorityEventState(self):
        self.priority_event_vid = 0
        self.priority_event_vnum = 0
        self.priority_event_name = None
        self.priority_event_missing_since = None

    def HasActiveNativeAutomation(self):
        return bool(self.hunter_enabled or self.boss_modes_paused or
                    self.reaction_native_paused or
                    (self.boss_enabled and self.boss_state == BOSS_ATTACK))

    def EmergencyStopForGameplayExit(self, reason):
        if self.HasActiveNativeAutomation():
            self.ClearNativeAutomation()
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
        self.action_coordinator.on_phase_change()
        self.gameplay_available = (self.gameplay_phase == PHASE_GAME)
        self.gameplay_next_check = 0.0
        window_name = ascii_text(getattr(type(window), "__name__", "unknown"))
        if self.gameplay_available:
            self.gameplay_stopped = False
            self.AddLine("Playable game window registered: %s" % window_name)
            if self.running and self.hunter_enabled and not self.boss_modes_paused:
                try:
                    player.MetinQueueSetEnabled(1)
                except Exception:
                    pass
            return
        if self.gameplay_phase == PHASE_LOADING:
            if self.HasActiveNativeAutomation():
                self.ClearNativeAutomation()
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

    def OnNativeQueueVIDState(self, kind, vid, enabled):
        if int(vid) == 0:
            self.AddLine("Native queue %s VID set cleared" % kind)
        else:
            self.AddLine("Native queue %s VID %d: %s" %
                         (kind, int(vid), "ON" if enabled else "OFF"))

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
                if self.HasActiveNativeAutomation():
                    self.ClearNativeAutomation()
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

    def UpdateMap(self, metin_offsets, other_offsets):
        self.UpdateMapPool(self.map_metins, metin_offsets)
        self.UpdateMapPool(self.map_others, other_offsets)
        self.map_count_label.SetText("Yellow: you  Red: %d metins  White: %d others" %
                                     (len(metin_offsets), len(other_offsets)))

    def UpdatePlayerMarker(self, player_position):
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
        self.reaction_label.SetText("Watches and solves the reaction game" if self.reaction_enabled
                                    else "Manual reaction; combat safety remains active")
        self.reaction_next_poll = 0.0
        self.AddLine("Auto Reaction %s" % ("ON" if self.reaction_enabled else "OFF"))

    def PauseNativeAutomationForReaction(self):
        if self.reaction_native_paused:
            return
        self.reaction_saved_hunter_enabled = bool(self.hunter_enabled)
        try:
            self.reaction_saved_queue_enabled = bool(player.MetinQueueIsEnabled())
        except Exception:
            self.reaction_saved_queue_enabled = False
        self.reaction_saved_boss_attack = bool(
            self.boss_enabled and self.boss_state == BOSS_ATTACK)
        self.reaction_native_paused = True
        self.ClearNativeAutomation()
        if self.reaction_saved_hunter_enabled:
            self.hunter_label.SetText("Queue: paused for reaction")
        if self.reaction_saved_boss_attack:
            self.boss_label.SetText("Boss attack paused for reaction")

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
                if self.reaction_enabled:
                    self.AddLine("Reaction game visible; native automation paused")
                else:
                    self.AddLine("Manual reaction required; native automation paused")
            if not self.reaction_enabled:
                return True
            if bool(getattr(window, "isPlaying", False)):
                self.reaction_started = True
            elif not self.reaction_started:
                play_button = getattr(window, "playButton", None)
                if play_button is not None and play_button.IsShow():
                    if not _ui_click(play_button):
                        emit_synthetic_click()
                        window._ReactionGameWindow__OnClickPlay()
                    self.reaction_started = True
                    self.AddLine("Reaction game start requested")
                return True
            if not bool(getattr(window, "isPlaying", False)):
                return True
            slot = getattr(window, "activeSlot", None)
            buttons = getattr(window, "slotButtons", ())
            if not isinstance(slot, INTEGER_TYPES) or slot < 0 or slot >= len(buttons):
                return True
            if not bool(getattr(window, "firstBallSpawned", False)):
                return True
            if bool(getattr(window, "isHit", False)):
                return True
            ball_time = getattr(window, "lastBallMoveTime", None)
            if ball_time is None:
                return True
            ball_key = (ball_time, slot)
            if ball_key == self.reaction_last_ball:
                return True
            if ball_key != self.reaction_pending_ball:
                delay = next_reaction_click_delay()
                self.reaction_pending_ball = ball_key
                self.reaction_click_at = now + delay
                self.AddLine("Reaction game slot %d observed; click in %.2fs" %
                             (slot, delay))
                return True
            if now < self.reaction_click_at:
                return True
            if not _ui_click(buttons[slot]):
                emit_synthetic_click()
                window._ReactionGameWindow__OnClickSlot(slot)
            self.reaction_last_ball = ball_key
            self.reaction_pending_ball = None
            self.reaction_click_at = 0.0
            self.AddLine("Reaction game clicked slot %d" % slot)
            self.reaction_last_error = None
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
            if (self.reaction_saved_boss_attack and self.boss_enabled and
                    self.boss_state == BOSS_ATTACK):
                self.StartBossFind()
            elif (self.reaction_saved_hunter_enabled and self.hunter_enabled and
                    self.running and self.reaction_saved_queue_enabled and
                    self.gameplay_available):
                try:
                    player.MetinQueueSetEnabled(1)
                    self.hunter_initial_fill = True
                    self.hunter_label.SetText("Queue: refilling after reaction")
                except Exception as exc:
                    self.hunter_enabled = False
                    self.hunter_button.SetText("OFF")
                    self.hunter_label.SetText("Queue: reaction restore failed")
                    self.AddLine("Reaction queue restore error: %s" % exc)
            self.reaction_native_paused = False
            self.reaction_saved_hunter_enabled = False
            self.reaction_saved_queue_enabled = False
            self.reaction_saved_boss_attack = False
        self.AddLine("Reaction game pause ended after %.1fs" % elapsed)

    def ToggleYinYangDuel(self):
        self.yinyang_duel_enabled = not self.yinyang_duel_enabled
        self.yinyang_duel_button.SetText("ON" if self.yinyang_duel_enabled else "OFF")
        self.yinyang_duel_next_poll = 0.0
        self.yinyang_duel_last_error = None
        self.yinyang_duel_debug = None
        self.yinyang_duel_stall = None
        if self.yinyang_duel_enabled:
            if not self.running:
                self.Start()
                if not self.running:
                    self.yinyang_duel_enabled = False
                    self.yinyang_duel_button.SetText("OFF")
                    self.yinyang_duel_label.SetText(
                        "Yin Yang Duel: enter the game world first")
                    return
            self.yinyang_duel_label.SetText("Yin Yang Duel: probing runtime")
            self.AddLine("Yin Yang Duel ON")
            self.DiagnosticYinYangDuel()
        else:
            self.yinyang_duel_label.SetText("Yin Yang Duel off")
            self.AddLine("Yin Yang Duel OFF")

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
        if not _ui_click(card):
            emit_synthetic_click()
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
                if prev_state in (2, 3, 4) and state == 0:
                    final_outcome = ("win" if our_score > opp_score else
                                     ("lose" if our_score < opp_score else "tie"))
                    self._DuelRecordEvent({
                        "event": "finish",
                        "match_id": tracker.match_id,
                        "our_score": our_score,
                        "opponent_score": opp_score,
                        "outcome": final_outcome,
                    })
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
        if (self.boss_vnum is None or self.boss_position is None or
                self.anchor_position is None or self.anchor_channel is None):
            self.AddLine("Boss Sweep: select the boss and click Mark Boss first")
            return
        if not self.native_queue_wrapper_active:
            self.AddLine("Boss Sweep unavailable: native full-input queue wrapper missing")
            return
        if not self.running:
            self.Start()
            if not self.running:
                return
        self.FindBossRuntime()
        missing = []
        if self.boss_timer is None:
            missing.append("boss timer (open M map once)")
        if self.boss_switch_dialog is None:
            missing.append("channel changer")
        if missing:
            self.AddLine("Boss Sweep unavailable: %s" % ", ".join(missing))
            return
        try:
            self.boss_channels = self.GetBossChannels()
        except Exception as exc:
            self.AddLine("Boss Sweep unavailable: %s" % exc)
            return
        self.boss_enabled = True
        self.boss_state = BOSS_WAIT_TIMER
        self.boss_state_started = time.time()
        self.boss_next_poll = 0.0
        self.boss_timer_armed = True
        self.boss_last_error = None
        self.boss_button.SetText("ON")
        self.boss_label.SetText("Waiting for %s timer" % self.boss_name)
        self.AddLine("Boss Sweep ON; return CH%d at %d, %d; channels %s" %
                     (self.anchor_channel, self.anchor_position[0],
                      self.anchor_position[1], ",".join(map(str, self.boss_channels))))

    def PauseMetinQueueForBoss(self):
        self.boss_saved_hunter_enabled = bool(self.hunter_enabled)
        try:
            self.boss_saved_queue_enabled = bool(player.MetinQueueIsEnabled())
        except Exception:
            self.boss_saved_queue_enabled = False
        self.hunter_enabled = False
        self.hunter_button.SetText("OFF")
        self.hunter_queued_vids.clear()
        self.hunter_initial_fill = True
        self.hunter_batch_add_count = 0
        self.hunter_next_add = 0.0
        self.ResetPriorityEventState()
        self.DisableAndClearMetinQueue()
        self.boss_modes_paused = True
        self.hunter_label.SetText("Queue: paused for boss")

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
            if self.hunter_enabled:
                self.hunter_initial_fill = True
                self.hunter_batch_add_count = 0
                self.hunter_next_add = 0.0
                self.hunter_label.SetText("Queue: starting paced batch after boss")
            else:
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
        if not self.native_queue_wrapper_active:
            raise RuntimeError("native full-input queue wrapper missing")
        distance, vid, px, py = candidate
        self.boss_target_vid = vid
        player.SetAttackKeyState(False)
        player.MetinQueueClear()
        player.AddMetinQueueAllowedRace(self.boss_vnum)
        player.MetinQueueSetEnabled(1)
        self._dispatch_native_add(vid, 2.0)
        queue_size = int(player.MetinQueueGetSize())
        if queue_size < 1:
            player.MetinQueueSetEnabled(0)
            raise RuntimeError("temporary boss queue rejected VID %d" % vid)
        self.boss_state = BOSS_ATTACK
        self.boss_state_started = time.time()
        self.boss_deadline = self.boss_state_started + BOSS_COMBAT_TIMEOUT_SECONDS
        self.boss_target_missing_since = None
        self.boss_label.SetText("CH%d: attacking %s" %
                                (int(net.GetChannelNumber()), self.boss_name))
        self.AddLine("CH%d: boss found [VID %d], distance %d; one-target chase queue started" %
                     (int(net.GetChannelNumber()), vid, distance))

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
        emit_synthetic_click()
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
        if self.HasActiveNativeAutomation():
            self.ClearNativeAutomation()
        self.running = False
        self.hunter_enabled = False
        self.hunter_button.SetText("OFF")
        self.hunter_label.SetText("Queue: stopped and cleared")
        self.ClearMap()
        self.state_label.SetText("Stopped. Set radius, then click Start.")
        self.AddLine("Stopped")

    def Dispose(self):
        self.watcher.Hide()
        self.Stop()
        self.Hide()

    def ToggleMetinHunter(self):
        if self.boss_modes_paused:
            self.AddLine("Metin Hunter unavailable during Boss Sweep")
            return
        if self.hunter_enabled:
            self.hunter_enabled = False
            self.ClearNativeAutomation()
            self.hunter_button.SetText("OFF")
            self.hunter_label.SetText("Queue: stopped and cleared")
            self.AddLine("Metin Hunter OFF; queue cleared")
            return
        if not self.native_queue_wrapper_active:
            self.AddLine("Metin Hunter unavailable: native full-input queue wrapper missing")
            return
        if not self.running:
            self.Start()
            if not self.running:
                return
        try:
            if not player.MetinQueueIsEnabled():
                player.MetinQueueSetEnabled(1)
            cap = min(HUNTER_LIMIT, int(player.MetinQueueGetMaxSize()))
            size = int(player.MetinQueueGetSize())
            if cap <= 0 or size < 0:
                raise ValueError("invalid metin queue capacity or size")
        except Exception as exc:
            self.AddLine("Metin Hunter unavailable: %s" % exc)
            return
        self.hunter_queued_vids.clear()
        self.hunter_logged_rejections.clear()
        self.hunter_initial_fill = (size == 0)
        self.hunter_batch_add_count = 0
        self.hunter_refilling = False
        self.hunter_next_refill = 0.0
        now = time.time()
        self.hunter_next_add = now + random.uniform(0.2, 0.6)
        self.hunter_enabled = True
        self.hunter_button.SetText("ON")
        self.hunter_label.SetText("Starting %d/%d - first add in %.1fs" %
                                  (size, cap,
                                   max(0.0, self.hunter_next_add - now)))
        self.AddLine("Metin Hunter ON; queue limit %d" % cap)

    def ScheduleHunterRefill(self, now):
        self.hunter_refilling = False
        self.hunter_next_refill = now + random.uniform(HUNTER_REFILL_MIN,
                                                       HUNTER_REFILL_MAX)

    def _dispatch_native_add(self, vid, timeout):
        """Run a synchronous native queue add through the action coordinator's
        state machine, returning the raw wrapper result (0/1/2/3).  The
        coordinator records the phase generation and deadline so the surrounding
        loop can detect a phase change or a hang."""
        action_id = self.action_coordinator.request("queue_add", vid, timeout)
        if not self.action_coordinator.validate(action_id, vid > 0):
            return 0
        self.action_coordinator.dispatch(action_id)
        try:
            result = _queue_add(vid)
        except Exception:
            result = 0
        outcome = _ADD_RESULT_OUTCOME.get(result, NativeActionCoordinator.UNKNOWN)
        self.action_coordinator.acknowledge(action_id, outcome)
        self.action_coordinator.finish(action_id)
        return result

    def FeedMetinQueue(self, candidates):
        if not self.hunter_enabled:
            return
        if not player.MetinQueueIsEnabled():
            self.hunter_enabled = False
            self.hunter_button.SetText("OFF")
            self.hunter_label.SetText("Queue: disabled")
            self.AddLine("Metin Hunter paused: queue was disabled")
            return
        cap = min(HUNTER_LIMIT, int(player.MetinQueueGetMaxSize()))
        size = int(player.MetinQueueGetSize())
        now = time.time()
        if size >= cap:
            if self.hunter_refilling or self.hunter_next_refill == 0.0:
                self.ScheduleHunterRefill(now)
            refill_wait = self.hunter_next_refill - now
            if refill_wait > 0.0:
                self.hunter_label.SetText(
                    "Full %d/%d - refill in %.1fs" %
                    (size, cap, refill_wait))
            else:
                self.hunter_label.SetText(
                    "Full %d/%d - refill ready" % (size, cap))
            return
        # Time-driven refill: wait a noisy interval after the queue was last
        # full, then burst-fill back to the cap. This mirrors the observed
        # ~50s human rhythm instead of refilling the instant a slot frees.
        if size == 0:
            # Never leave an empty queue waiting for the long refill timer.
            # Keep the small per-add delay, but begin looking immediately.
            self.hunter_refilling = True
            self.hunter_next_refill = 0.0
        elif not self.hunter_refilling:
            if now < self.hunter_next_refill:
                self.hunter_label.SetText(
                    "Waiting %d/%d - refill in %.1fs" %
                    (size, cap, self.hunter_next_refill - now))
                return
            self.hunter_refilling = True
        if now < self.hunter_next_add:
            self.hunter_label.SetText(
                "Refilling %d/%d - next add in %.1fs" %
                (size, cap, self.hunter_next_add - now))
            return
        eligible = []
        for distance, vid, name in candidates:
            if vid in self.hunter_queued_vids:
                continue
            try:
                vnum = chr.GetVirtualNumber(vid)
                if not nonplayer.IsMonsterStone(vnum):
                    continue
                is_stone = getattr(chr, "IsStone", None)
                if not callable(is_stone) or not is_stone(vid):
                    reason = "native actor is not a stone"
                    rejection = (int(vid), reason)
                    if rejection not in self.hunter_logged_rejections:
                        self.hunter_logged_rejections.add(rejection)
                        self.AddLine("Skipped %s [VID %d]: %s" %
                                     (name or "Metin", vid, reason))
                    continue
                reason = self.queue_admission_guard.RejectionReason(vid)
                if reason is not None:
                    rejection = (int(vid), reason)
                    if rejection not in self.hunter_logged_rejections:
                        self.hunter_logged_rejections.add(rejection)
                        self.AddLine("Skipped %s [VID %d]: %s" %
                                     (name or "Metin", vid, reason))
                    continue
                px, py = chr.GetPixelPosition(vid)[:2]
                player_x, player_y = player.GetMainCharacterPosition()[:2]
                distance = int(((px - player_x) ** 2 +
                                (py - player_y) ** 2) ** 0.5)
                if distance > self.radius:
                    continue
                center_x, center_y = (self.anchor_position or
                                      (player_x, player_y))[:2]
                circle_distance = int(((px - center_x) ** 2 +
                                       (py - center_y) ** 2) ** 0.5)
                if circle_distance > self.radius:
                    continue
                can_attack = getattr(player, "CanAttackInstance", None)
                if callable(can_attack) and not can_attack(vid):
                    continue
                eligible.append((distance, vid, name))
            except Exception:
                continue  # Entity disappeared or changed before queue admission.
        if not eligible:
            self.hunter_label.SetText(
                "Searching %d/%d - no eligible Metin" % (size, cap))
            if size > 0:
                self.ScheduleHunterRefill(now)
            return
        distance, vid, name = random.choice(eligible)
        old_size = size
        add_started = time.time()
        result = self._dispatch_native_add(vid, 2.0)
        add_elapsed_ms = (time.time() - add_started) * 1000.0
        new_size = int(player.MetinQueueGetSize())
        if result == 2:
            # Already present in the authoritative queue; the wrapper did not
            # dispatch a click (a click could remove it).  Treat as queued.
            self.hunter_queued_vids.add(vid)
            self.AddLine("VID %d already queued (no click), queue %d/%d, call %.2fms" %
                         (vid, new_size, cap, add_elapsed_ms))
            if new_size >= cap:
                self.ScheduleHunterRefill(now)
            return
        if result == 1 or new_size > size:
            self.hunter_queued_vids.add(vid)
            if new_size >= cap:
                self.ScheduleHunterRefill(now)
            delay = random.uniform(HUNTER_BURST_DELAY_MIN, HUNTER_BURST_DELAY_MAX)
            self.hunter_next_add = now + delay
            if new_size >= cap:
                self.hunter_label.SetText(
                    "Full %d/%d - refill in %.1fs" %
                    (new_size, cap,
                     max(0.0, self.hunter_next_refill - now)))
            else:
                self.hunter_label.SetText(
                    "Refilling %d/%d - next add in %.1fs" %
                    (new_size, cap, delay))
            self.AddLine("Queued %s [VID %d], distance %d, queue %d->%d/%d, call %.2fms; next add >= %.2fs" %
                         (name or "Metin", vid, distance, old_size, new_size,
                          cap, add_elapsed_ms, delay))
            return
        if result == 3:
            # Outcome unknown: the dispatch ran but the requested VID is not in
            # the queue.  Never retry the same action immediately (it may have
            # executed); let the next scan re-evaluate.
            self.hunter_queued_vids.add(vid)
            self.AddLine("Queue outcome unknown for VID %d, queue %d->%d/%d, call %.2fms; no immediate retry" %
                         (vid, old_size, new_size, cap, add_elapsed_ms))
            delay = random.uniform(HUNTER_BURST_DELAY_MIN,
                                   HUNTER_BURST_DELAY_MAX)
            self.hunter_next_add = now + delay
            self.hunter_label.SetText(
                "Outcome unknown %d/%d - recheck in %.1fs" % (new_size, cap, delay))
            return
        self.AddLine("Queue rejected VID %d, queue %d->%d, call %.2fms" %
                     (vid, old_size, new_size, add_elapsed_ms))
        delay = random.uniform(HUNTER_BURST_DELAY_MIN,
                               HUNTER_BURST_DELAY_MAX)
        self.hunter_next_add = now + delay
        self.hunter_label.SetText(
            "Retrying %d/%d - next try in %.1fs" % (new_size, cap, delay))

    def StartPriorityEventMetin(self, candidate):
        distance, vid, name, expected_vnum = candidate
        try:
            vnum = int(chr.GetVirtualNumber(vid))
            live_name = ascii_text(chr.GetNameByVID(vid))
            if (vnum != expected_vnum or
                    PRIORITY_EVENT_METIN_NAME not in live_name.lower()):
                return False
            name = live_name
            if not nonplayer.IsMonsterStone(vnum):
                return False
            is_stone = getattr(chr, "IsStone", None)
            if not callable(is_stone) or not is_stone(vid):
                return False
            reason = self.queue_admission_guard.RejectionReason(vid)
            if reason is not None:
                raise RuntimeError(reason)
            px, py = chr.GetPixelPosition(vid)[:2]
            player_x, player_y = player.GetMainCharacterPosition()[:2]
            distance = int(((px - player_x) ** 2 +
                            (py - player_y) ** 2) ** 0.5)
            center_x, center_y = (self.anchor_position or
                                  (player_x, player_y))[:2]
            circle_distance = int(((px - center_x) ** 2 +
                                   (py - center_y) ** 2) ** 0.5)
            if distance > self.radius or circle_distance > self.radius:
                return False
            can_attack = getattr(player, "CanAttackInstance", None)
            if callable(can_attack) and not can_attack(vid):
                raise RuntimeError("native actor cannot be attacked")
            self.DisableAndClearMetinQueue()
            self.hunter_queued_vids.clear()
            self.hunter_initial_fill = True
            self.hunter_batch_add_count = 0
            self.hunter_next_add = 0.0
            player.AddMetinQueueAllowedRace(vnum)
            player.MetinQueueSetEnabled(1)
            self._dispatch_native_add(vid, 2.0)
            if int(player.MetinQueueGetSize()) < 1:
                raise RuntimeError("one-target queue rejected VID %d" % vid)
            self.priority_event_vid = int(vid)
            self.priority_event_vnum = vnum
            self.priority_event_name = name or "Legendary Metinstone"
            self.priority_event_missing_since = None
            self.hunter_label.SetText("Priority: %s" % self.priority_event_name)
            self.AddLine("Priority event Metin found: %s [vnum %d, VID %d], distance %d; ordinary queue cancelled" %
                         (self.priority_event_name, vnum, vid, distance))
            return True
        except Exception as exc:
            try:
                self.DisableAndClearMetinQueue()
                if self.hunter_enabled:
                    player.MetinQueueSetEnabled(1)
            except Exception:
                pass
            self.ResetPriorityEventState()
            self.hunter_initial_fill = True
            self.hunter_batch_add_count = 0
            self.hunter_next_add = 0.0
            self.AddLine("Priority event Metin rejected safely: %s" % ascii_text(exc))
            return False

    def FinishPriorityEventMetin(self):
        name = self.priority_event_name or "Legendary Metinstone"
        self.DisableAndClearMetinQueue()
        self.ResetPriorityEventState()
        self.hunter_queued_vids.clear()
        self.hunter_initial_fill = True
        self.hunter_batch_add_count = 0
        self.hunter_next_add = 0.0
        if self.hunter_enabled:
            player.MetinQueueSetEnabled(1)
            self.hunter_label.SetText("Queue: refilling after priority Metin")
        self.AddLine("Priority event Metin gone: %s; ordinary Hunter restored" % name)

    def HandlePriorityEventMetin(self, candidates, now):
        if not self.hunter_enabled or self.boss_modes_paused:
            return False
        candidates = sorted(candidates)
        if self.priority_event_vid:
            for candidate in candidates:
                if int(candidate[1]) == self.priority_event_vid:
                    self.priority_event_missing_since = None
                    return True
            if candidates:
                return self.StartPriorityEventMetin(candidates[0])
            if self.priority_event_missing_since is None:
                self.priority_event_missing_since = now
                return True
            if now - self.priority_event_missing_since < PRIORITY_EVENT_MISSING_SECONDS:
                return True
            self.FinishPriorityEventMetin()
            return False
        if not candidates:
            return False
        return self.StartPriorityEventMetin(candidates[0])

    def Scan(self, player_position):
        vids = visible_vids()
        x, y = (self.anchor_position or player_position)[:2]
        player_x, player_y = player_position[:2]
        found = {}
        metin_offsets = []
        other_offsets = []
        candidates = []
        priority_event_candidates = []
        for vid in vids:
            try:
                vnum = chr.GetVirtualNumber(vid)
                is_metin = nonplayer.IsMonsterStone(vnum)
                if not is_metin and len(other_offsets) >= len(self.map_others):
                    continue
                px, py = chr.GetPixelPosition(vid)[:2]
                circle_distance = int(((px - x) ** 2 + (py - y) ** 2) ** 0.5)
                if circle_distance > self.radius:
                    continue
                if not is_metin:
                    if circle_distance > 1 and len(other_offsets) < len(self.map_others):
                        other_offsets.append((px - x, py - y))
                    continue
                if len(metin_offsets) < len(self.map_metins):
                    metin_offsets.append((px - x, py - y))
                name = ascii_text(chr.GetNameByVID(vid))
                player_distance = int(((px - player_x) ** 2 + (py - player_y) ** 2) ** 0.5)
                if player_distance <= self.radius:
                    candidates.append((player_distance, vid, name))
                    if PRIORITY_EVENT_METIN_NAME in name.lower():
                        priority_event_candidates.append(
                            (player_distance, vid, name, int(vnum)))
                key = (vnum, name)
                if key not in found:
                    found[key] = []
                found[key].append(circle_distance)
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
            summary = "radius=%d %s: no metins visible in range" % (self.radius, mode)
        self.UpdateMap(metin_offsets, other_offsets)
        self.AddLine(summary)
        try:
            now = time.time()
            if self.HandlePriorityEventMetin(priority_event_candidates, now):
                return
            self.FeedMetinQueue(candidates)
        except Exception as exc:
            self.hunter_enabled = False
            self.hunter_button.SetText("OFF")
            self.hunter_label.SetText("Queue: error")
            self.AddLine("Metin Hunter error: %s" % exc)

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

    def OnUpdate(self):
        now = time.time()
        self.action_coordinator.poll()
        if not self.IsGameplayAvailable(now):
            return
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
            # Jitter the scan cadence so Hunter adds don't land on a whole-second
            # grid; the effective click gaps then carry sub-second variation.
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
