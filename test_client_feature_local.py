"""Exercise the Python 2 feature logic with fake client UI and entity modules.

The Hunter redesign is exercised through the real HunterQueueGateway,
HunterCandidateSelector and HunterController with injected fake dependencies, plus
panel-level checks that disabled features report unavailable and perform no
gameplay side effects.
"""

import builtins
import os
import re
import sys
import tempfile
import time
import types
from pathlib import Path

builtins.unicode = str


class Widget:
    def __init__(self):
        self.text = ""
        self.visible = False
        self.parent = None
        self.size = None

    def __getattr__(self, name):
        if name.startswith("Set") or name == "AddFlag":
            return lambda *args: None
        raise AttributeError(name)

    def SetText(self, value):
        self.text = value

    def SetParent(self, parent):
        self.parent = parent

    def SetPosition(self, x, y):
        self.position = (x, y)

    def SetSize(self, width, height):
        self.size = (width, height)

    def GetWidth(self):
        return self.size[0] if self.size is not None else 0

    def GetHeight(self):
        return self.size[1] if self.size is not None else 0

    def GetTextSize(self):
        return (len(self.text) * 6, 12)

    def SetEvent(self, callback):
        self.event = callback

    def SetCloseEvent(self, callback):
        self.close_event = callback

    def GetText(self):
        return self.text

    def Show(self):
        self.visible = True

    def Hide(self):
        self.visible = False

    def IsShow(self):
        return self.visible


ui = types.ModuleType("ui")
for name in ("Window", "BoardWithTitleBar", "TextLine", "Button", "SlotBar", "EditLine", "Bar"):
    setattr(ui, name, type(name, (Widget,), {}))
ui.GenerateColor = lambda *components: 0xFFFFFFFF
sys.modules["ui"] = ui

app = types.ModuleType("app")
app.DIK_LCONTROL = 29
app.DIK_F8 = 66
pressed_keys = set()
app.IsPressed = lambda key: key in pressed_keys
sys.modules["app"] = app

wndMgr = types.ModuleType("wndMgr")
screen_size = [2560, 1369]
wndMgr.GetScreenWidth = lambda: screen_size[0]
wndMgr.GetScreenHeight = lambda: screen_size[1]
sys.modules["wndMgr"] = wndMgr

background = types.ModuleType("background")
background.GetCurrentMapName = lambda: "metin2_map_test"
sys.modules["background"] = background

net = types.ModuleType("net")
channel_state = {"current": 1}
connection_state = {"connected": True}
net.GetChannelNumber = lambda: channel_state["current"]
net.SetChannelNumber = lambda channel: channel_state.__setitem__("current", int(channel))
net.IsConnect = lambda: connection_state["connected"]
phase_window_calls = []
net.SetPhaseWindow = lambda phase, window: phase_window_calls.append((phase, window))
disconnect_calls = []
net.Disconnect = lambda *args, **kwargs: disconnect_calls.append((args, kwargs))
sys.modules["net"] = net

chr_module = types.ModuleType("chr")
chr_module.GetVirtualNumber = lambda vid: {
    1: 8003, 2: 8004, 3: 100, 4: 8003, 5: 8004, 6: 8003,
    7: 8004, 8: 8003, 9: 8004, 10: 2493, 11: 39922
}[vid]
chr_module.GetPixelPosition = lambda vid: {
    1: (300, 400, 0), 2: (1200, 0, 0), 3: (100, 0, 0),
    4: (600, 0, 0), 5: (800, 0, 0), 6: (1000, 0, 0),
    7: (1400, 0, 0), 8: (1500, 0, 0), 9: (1600, 0, 0),
    10: (2100, 0, 0), 11: (2250, 0, 0)
}[vid]
chr_module.GetNameByVID = lambda vid: {
    1: "Battle Metin", 2: "Jealousy Metin", 3: "Wolf",
    4: "Battle Metin", 5: "Jealousy Metin", 6: "Battle Metin",
    7: "Jealousy Metin", 8: "Battle Metin", 9: "Jealousy Metin",
    10: "Test Boss", 11: "Legendary Metinstone III"
}[vid]
actor_stone_overrides = {}
chr_module.IsStone = lambda vid: actor_stone_overrides.get(
    vid, chr_module.GetVirtualNumber(vid) in (8003, 8004, 39922))
sys.modules["chr"] = chr_module

nonplayer = types.ModuleType("nonplayer")
nonplayer.IsMonsterStone = lambda vnum: vnum in (8003, 8004, 39922)
sys.modules["nonplayer"] = nonplayer

player = types.ModuleType("player")
player_position = [0, 0, 0]
player.GetMainCharacterPosition = lambda: tuple(player_position)
queue = []
queue_state = {"enabled": False, "max_size": 5}
queue_clear_state = {"count": 0}
allowed_queue_races = set()
player.MetinQueueIsEnabled = lambda: queue_state["enabled"]


def clear_metin_queue():
    queue_clear_state["count"] += 1
    queue[:] = []


def set_metin_queue_enabled(enabled):
    old_enabled = queue_state["enabled"]
    queue_state["enabled"] = bool(enabled)
    if old_enabled and not queue_state["enabled"]:
        clear_metin_queue()


player.MetinQueueSetEnabled = set_metin_queue_enabled
player.MetinQueueGetSize = lambda: len(queue)
player.MetinQueueGetMaxSize = lambda: queue_state["max_size"]
add_calls = []


def add_metin(vid, x=None, y=None):
    vid = int(vid)
    add_calls.append(vid)
    if vid in queue:
        return 1  # stock add returns 1 for an existing VID too
    if len(queue) >= queue_state["max_size"]:
        return 0  # capacity branch
    queue.append(vid)
    return 1


def remove_metin(vid):
    vid = int(vid)
    if vid in queue:
        queue.remove(vid)
        return 1
    return 0


player.MetinQueueAdd = add_metin
player.MetinQueueRemove = remove_metin
player.MetinQueueClear = clear_metin_queue
player.AddMetinQueueAllowedRace = lambda vnum: allowed_queue_races.add(int(vnum))
player.CanAttackInstance = lambda vid: vid in range(1, 12)
native_immune_vids = set()
native_untargetable_vids = set()
player.SetMetinQueueVIDImmune = lambda vid, enabled: None
player.SetMetinQueueVIDUntargetable = lambda vid, enabled: None
target_state = {"vid": 0, "attack": False, "mouse": 17}
player.GetTargetVID = lambda: target_state["vid"]
player.SetTarget = lambda vid: target_state.__setitem__("vid", int(vid))
player.ClearTarget = lambda: target_state.__setitem__("vid", 0)
player.SetAttackKeyState = lambda enabled: target_state.__setitem__("attack", bool(enabled))
player.GetMouseFunc = lambda button: target_state["mouse"]
player.SetMouseFunc = lambda button, function: target_state.__setitem__("mouse", function)
main_character = {"vid": 999, "name": "Local Tester"}
player.GetMainCharacterIndex = lambda: main_character["vid"]
player.GetMainCharacterName = lambda: main_character["name"]
player.MBT_LEFT = 0
player.MBF_AUTO = 2
sys.modules["player"] = player


class TargetBoard:
    def GetTargetVID(self):
        return target_state["vid"]


class CursedBossAtlasPanel:
    def __init__(self):
        self.remaining = 120

    def GetTimeRemaining(self):
        return self.remaining


class MoveChannelDialog:
    def __init__(self):
        self.selected = channel_state["current"]
        self.visible = False

    def GetChannelCount(self):
        return 3

    def GetChannelNumber(self):
        return self.selected

    def _MoveChannelDialog__SelectChannel(self, channel):
        self.selected = int(channel)

    def AcceptButton(self):
        channel_state["current"] = self.selected


class ReactionGameWindow:
    def __init__(self):
        self.visible = False
        self.isPlaying = False
        self.firstBallSpawned = True
        self.isHit = False
        self.activeSlot = 2
        self.lastBallMoveTime = 1.0
        self.slotButtons = [object()] * 4
        self.playButton = Widget()
        self.playButton.Show()
        self.clicked = []
        self.start_count = 0

    def IsShow(self):
        return self.visible

    def _ReactionGameWindow__OnClickPlay(self):
        self.start_count += 1
        self.isPlaying = True

    def _ReactionGameWindow__OnClickSlot(self, slot):
        self.clicked.append(slot)


target_board = TargetBoard()
boss_timer = CursedBossAtlasPanel()
channel_dialog = MoveChannelDialog()
reaction_window = ReactionGameWindow()
# Do NOT register a native observer: Hunter is unavailable without one.

source_path = Path(__file__).with_name("client_feature.py")
source = source_path.read_text(encoding="ascii")
directory_line = next(line for line in source.splitlines()
                      if line.startswith("DIRECTORY = "))
directory_probe = {}
exec(compile("import os\nimport sys\n" + directory_line + "\n",
             str(source_path), "exec"), directory_probe)
assert Path(directory_probe["DIRECTORY"]).resolve() == source_path.parent.resolve()

with tempfile.TemporaryDirectory() as directory:
    source = re.sub(r"^DIRECTORY = .*$", lambda match: "DIRECTORY = %r" % directory,
                    source, flags=re.M)
    exec(compile(source, str(source_path), "exec"), {"__name__": "__main__"})
    panel = sys.modules["__main__"]._lirin_metin_scanner

    # --- panel construction ------------------------------------------------
    assert panel.radius == 2500 and panel.radius_edit.GetText() == "2500"
    assert panel.size == (620, 555)
    assert panel.position == (40, 80)
    assert panel.native_button_size == (88, 21)
    assert panel.stop_button.text == "Stop farming"
    assert panel.active_tab == "farming"
    assert panel.farming_page.visible
    assert panel.hunter_button.parent is panel.farming_page
    assert panel.hunter_observer is None  # no native observer in the mock
    assert panel.hunter_controller is not None
    assert panel.hunter_controller.state == "OFF"

    # --- disabled features report unavailable with no side effects ----------
    panel.hunter_enabled = True
    panel.running = True
    queue[:] = [1]
    queue_state["enabled"] = True
    target_state["vid"] = 1
    panel.ToggleBossSweep()
    assert not panel.boss_enabled
    assert "unavailable" in panel.boss_label.text
    panel.ToggleYinYangDuel()
    assert not panel.yinyang_duel_enabled
    assert "unavailable" in panel.yinyang_duel_label.text
    panel.ToggleTwinSouls()
    assert not panel.twin_souls_enabled
    assert "unavailable" in panel.twin_souls_label.text
    # The disabled features must not clear the queue, attack key, or target.
    assert queue == [1] and queue_state["enabled"] and target_state["vid"] == 1
    assert not target_state["attack"]
    # Hunter cannot start without the observer.
    panel.hunter_enabled = False
    panel.ToggleMetinHunter()
    assert not panel.hunter_enabled
    assert panel.hunter_button.text == "OFF"
    queue[:] = []
    queue_state["enabled"] = False
    target_state["vid"] = 0
    panel.running = False
    panel.hunter_enabled = False

    # --- HunterQueueGateway -------------------------------------------------
    hg = panel.PollYinYangDuel.__globals__["HunterQueueGateway"]

    class FakeObserver:
        def __init__(self, queue, enabled, max_size, cookie=0xCAFE):
            self._queue = queue
            self._enabled = enabled
            self._max_size = max_size
            self._cookie = cookie

        def now_ms(self):
            return int(time.time() * 1000)

        def snapshot(self):
            return {"api_version": 1, "valid": True, "error": None,
                    "player_cookie": self._cookie,
                    "vids": tuple(self._queue), "enabled": self._enabled,
                    "max_size": self._max_size,
                    "observed_tick_ms": int(time.time() * 1000),
                    "stock_binding_ok": True}

        def admission(self, vid):
            return {"valid": True, "eligible": True, "reason": None,
                    "player_cookie": self._cookie}

    fake_queue = queue
    observer = FakeObserver(fake_queue, queue_state["enabled"], queue_state["max_size"])
    gateway = hg(observer, player)
    snap = gateway.snapshot()
    assert snap["valid"] and snap["max_size"] == 5
    assert gateway.observer_available()
    cookie = snap["player_cookie"]

    def req(vid, **kw):
        r = {"vid": vid, "player_cookie": cookie, "pre_snapshot": None}
        r.update(kw)
        return r

    # Truthy stock add without the requested VID is UNKNOWN (membership decisive).
    queue[:] = []
    queue_state["max_size"] = 5
    original_add = player.MetinQueueAdd
    player.MetinQueueAdd = lambda vid, x=None, y=None: 1  # truthy but no insert
    assert gateway.add_once(req(7)) == "UNKNOWN"
    player.MetinQueueAdd = original_add
    # Duplicate pre-membership makes no call.
    queue[:] = [7]
    add_calls[:] = []
    assert gateway.add_once(req(7)) == "ALREADY_PRESENT"
    assert add_calls == []
    # A real insertion is ADDED (requested VID newly present).
    queue[:] = []
    assert gateway.add_once(req(7)) == "ADDED"
    assert 7 in queue
    # Capacity rejection is REJECTED_NATIVE.
    queue[:] = []
    player.MetinQueueAdd = lambda vid, x=None, y=None: 0
    assert gateway.add_once(req(9)) == "REJECTED_NATIVE"
    player.MetinQueueAdd = original_add
    # remove_once removes exactly the requested VID.
    queue[:] = [1, 7, 2]
    assert gateway.remove_once(req(7)) == "REMOVED"
    assert queue == [1, 2]
    # remove of an absent VID is ALREADY_ABSENT.
    assert gateway.remove_once(req(99)) == "ALREADY_ABSENT"
    # A stale-session request is not dispatched.
    queue[:] = []
    add_calls[:] = []
    assert gateway.add_once(req(7, player_cookie=0xBAD)) == "CANCELLED_PRECALL"
    assert add_calls == []
    # A dispatched request never executes again.
    queue[:] = []
    already = req(7, dispatched=True)
    assert gateway.add_once(already) == "CANCELLED_PRECALL"
    assert add_calls == []
    # Unavailable observer is not "empty".
    no_observer = hg(None, player)
    snap = no_observer.snapshot()
    assert not snap["valid"] and snap["vids"] == ()

    # --- HunterCandidateSelector -------------------------------------------
    selector = panel.PollYinYangDuel.__globals__["HunterCandidateSelector"](player, chr_module, nonplayer)
    snap = selector.publish([1, 2, 3, 11], (0, 0), None, 2500, 1, 1000)
    vids = [c["vid"] for c in snap["candidates"]]
    assert vids == [1, 2, 11]  # 3 is a Wolf (not stone); nearest-first then VID
    assert snap["candidates"][0]["vid"] == 1  # distance sqrt(300^2+400^2)=500
    # selection excludes queue/backoff/excluded, respects staleness
    chosen = selector.select(snap, 1000, {1}, set(), {}, False)
    assert chosen["vid"] == 2
    chosen = selector.select(snap, 1000, {1, 2}, set(), {11: 5000}, False)
    assert chosen is None  # 11 in backoff
    chosen = selector.select(snap, 1000, set(), set(), {}, True)
    assert chosen["vid"] == 11  # priority restricts to legendary
    stale = selector.select(snap, 4000, set(), set(), {}, False)
    assert stale is None  # snapshot older than 2000 ms

    circle = {
        "created_ms": 1000, "player_position": (0, 0),
        "candidates": (
            {"vid": 1, "name": "Metin", "x": 100, "y": 0,
             "distance2": 10000},
            {"vid": 2, "name": "Metin", "x": 0, "y": 100,
             "distance2": 10000},
            {"vid": 4, "name": "Metin", "x": -100, "y": 0,
             "distance2": 10000},
            {"vid": 5, "name": "Metin", "x": 0, "y": -100,
             "distance2": 10000},
        ),
    }
    chosen = selector.select(circle, 1000, set(), set(), {}, False,
                             sweep_angle=100, sweep_direction=-1)
    assert chosen["vid"] == 2  # next clockwise bearing: 90 degrees
    chosen = selector.select(circle, 1000, set(), set(), {}, False,
                             sweep_angle=100, sweep_direction=1)
    assert chosen["vid"] == 4  # next counter-clockwise bearing: 180 degrees

    # --- HunterController ---------------------------------------------------
    HunterController = panel.PollYinYangDuel.__globals__["HunterController"]
    ManualQueueRefillProfile = (
        panel.PollYinYangDuel.__globals__["ManualQueueRefillProfile"])

    first_profile = ManualQueueRefillProfile(lambda values: values[0])
    last_profile = ManualQueueRefillProfile(lambda values: values[-1])
    assert first_profile.refill_start_delay_ms() == 12984
    assert first_profile.burst_add_delay_ms() == 437
    assert first_profile.sweep_direction() == -1
    assert last_profile.refill_start_delay_ms() == 32281
    assert last_profile.burst_add_delay_ms() == 2906
    assert last_profile.sweep_direction() == 1

    class FakeGateway:
        """Controllable gateway implementing the exact gateway surface."""

        def __init__(self, queue, enabled, max_size, cookie=0xBEEF):
            self.queue = queue
            self.enabled = enabled
            self.max_size = max_size
            self.cookie = cookie
            self.add_calls = []
            self.remove_calls = []
            self.set_enabled_calls = []
            self.add_outcome = None
            self.remove_outcome = None
            self.valid = True
            self.fail_disable = False

        def snapshot(self):
            if not self.valid:
                return {"valid": False, "error": "boom", "vids": (),
                        "enabled": False, "max_size": 0, "player_cookie": None,
                        "observed_tick_ms": 0, "stock_binding_ok": False}
            return {"valid": True, "error": None, "player_cookie": self.cookie,
                    "vids": tuple(self.queue), "enabled": self.enabled,
                    "max_size": self.max_size, "observed_tick_ms": 0,
                    "stock_binding_ok": True}

        def admission(self, vid):
            return {"valid": True, "eligible": vid != 99, "reason": None,
                    "player_cookie": self.cookie}

        def now_ms(self):
            return int(time.time() * 1000)

        def add_once(self, request):
            vid = request["vid"]
            self.add_calls.append(vid)
            request["dispatched"] = True
            if vid in self.queue:
                return "ALREADY_PRESENT"
            if self.add_outcome is not None:
                return self.add_outcome
            if len(self.queue) < self.max_size:
                self.queue.append(vid)
                return "ADDED"
            return "REJECTED_NATIVE"

        def remove_once(self, request):
            vid = request["vid"]
            self.remove_calls.append(vid)
            request["dispatched"] = True
            if vid in self.queue:
                self.queue.remove(vid)
                return "REMOVED"
            return "ALREADY_ABSENT"

        def set_enabled_once(self, value, lease=None):
            self.set_enabled_calls.append(value)
            if self.fail_disable and not value:
                return "UNKNOWN", self.snapshot(), None
            old = self.enabled
            self.enabled = bool(value)
            # native true->false disable performs a full clear
            if old and not self.enabled:
                self.queue[:] = []
            return ("ENABLED" if value else "DISABLED"), self.snapshot(), None

    class FakeSelector:
        def __init__(self):
            self.next_candidate = {"vid": 7, "name": "Battle Metin", "vnum": 8003,
                                   "x": 100, "y": 100, "distance2": 20000}
            self.priority_candidate = {"vid": 11, "name": "Legendary Metinstone III",
                                       "vnum": 39922, "x": 100, "y": 100, "distance2": 20000}

        def publish(self, *args):
            return {}

        def select(self, snapshot, now_ms, queue_vids, excluded, backoff,
                   priority=False, sweep_angle=None, sweep_direction=-1):
            cand = self.priority_candidate if priority else self.next_candidate
            if cand["vid"] in queue_vids:
                return None
            return cand

    class FakeChr:
        VNUMS = {7: 8003, 8: 8004, 11: 39922}

        def GetVirtualNumber(self, vid):
            return self.VNUMS.get(vid, 8003)

        def GetNameByVID(self, vid):
            return "Metin"

        def GetPixelPosition(self, vid):
            return (100, 100, 0)

        def IsStone(self, vid):
            return True

    class FixedRefillProfile:
        def refill_start_delay_ms(self):
            return 5000

        def burst_add_delay_ms(self):
            return 1000

        def sweep_direction(self):
            return -1

    def make_controller(queue, enabled=False, max_size=5, clock_box=None, priority=False):
        gw = FakeGateway(queue, enabled, max_size)
        sel = FakeSelector()
        if clock_box is None:
            clock_box = [0]
        controller = HunterController(
            gw, sel, lambda: clock_box[0],
            lambda: True, capacity_limit=5, priority_enabled=priority,
            refill_profile=FixedRefillProfile())
        controller._selector._chr = FakeChr()
        controller._selector._nonplayer = nonplayer
        controller._selector._player = player
        return controller, gw, sel, clock_box

    # start: empty+disabled -> enables -> RUNNING
    q = []
    ctrl, gw, sel, clock = make_controller(q, enabled=False)
    clock[0] = 1000
    assert ctrl.start() == "RUNNING"
    assert gw.set_enabled_calls == [True]
    assert ctrl.lease is not None and ctrl.user_requested_on

    # refill: one add per tick, at least 1000 ms apart
    q[:] = []
    ctrl, gw, sel, clock = make_controller(q, enabled=False)
    clock[0] = 1000
    ctrl.start()
    ctrl.last_scan = {"created_ms": 1000, "epoch": ctrl.epoch, "candidates": (),
                      "radius": 2500, "player_position": (0, 0),
                      "anchor_position": None}
    sel.next_candidate = {"vid": 7, "name": "Battle Metin", "vnum": 8003,
                          "x": 100, "y": 100, "distance2": 20000}
    clock[0] = 2000
    ctrl.tick(2000)
    assert 7 in q  # first add
    sel.next_candidate = {"vid": 8, "name": "Jealousy Metin", "vnum": 8004,
                          "x": 200, "y": 200, "distance2": 80000}
    clock[0] = 2500  # < 1000ms since add
    ctrl.tick(2500)
    assert len(gw.add_calls) == 1  # no second add within 1000 ms
    clock[0] = 3100
    ctrl.tick(3100)
    assert len(gw.add_calls) == 2  # second add after interval
    assert 8 in q

    # Once full, a departure schedules the measured-style refill wait.  The
    # controller does not top off continuously, then begins a burst at expiry.
    q[:] = []
    ctrl, gw, sel, clock = make_controller(q, enabled=False)
    clock[0] = 1000
    ctrl.start()
    q[:] = [4, 5, 6, 7, 8]
    ctrl.ledger = set(q)
    clock[0] = 1100
    ctrl.tick(1100)  # observe full and arm the next refill cycle
    q.remove(4)
    ctrl.ledger.discard(4)
    ctrl.last_scan = {"created_ms": 1200, "epoch": ctrl.epoch, "candidates": (),
                      "radius": 2500, "player_position": (0, 0),
                      "anchor_position": None}
    sel.next_candidate = {"vid": 4, "name": "Battle Metin", "vnum": 8003,
                          "x": 100, "y": 100, "distance2": 20000}
    clock[0] = 1200
    ctrl.tick(1200)
    assert len(gw.add_calls) == 0 and ctrl.refill_due_ms == 6200
    clock[0] = 6199
    ctrl.tick(6199)
    assert len(gw.add_calls) == 0
    clock[0] = 6200
    ctrl.last_scan["created_ms"] = 6200
    ctrl.tick(6200)
    assert gw.add_calls == [4] and len(q) == 5

    # regression: a cached (stale) queue observation must not prune a just-added
    # VID.  Updates 1 ms and 100 ms after the add must keep ownership intact.
    q[:] = []
    ctrl, gw, sel, clock = make_controller(q, enabled=False)
    clock[0] = 1000
    ctrl.start()
    ctrl.last_scan = {"created_ms": 1000, "epoch": ctrl.epoch, "candidates": (),
                      "radius": 2500, "player_position": (0, 0),
                      "anchor_position": None}
    sel.next_candidate = {"vid": 7, "name": "Battle Metin", "vnum": 8003,
                          "x": 100, "y": 100, "distance2": 20000}
    clock[0] = 2000
    ctrl.tick(2000)  # add VID 7
    assert 7 in q and 7 in ctrl.ledger
    clock[0] = 2001  # 1 ms later: within the poll gap, must not reuse pre-add cache
    ctrl.tick(2001)
    assert ctrl.state != "ERROR"
    assert 7 in ctrl.ledger
    clock[0] = 2100  # 100 ms later: fresh snapshot still shows the owned VID
    ctrl.tick(2100)
    assert ctrl.state != "ERROR"
    assert 7 in ctrl.ledger

    # membership truthy-but-absent is UNKNOWN -> RECONCILING, no new adds
    q[:] = []
    ctrl, gw, sel, clock = make_controller(q, enabled=False)
    clock[0] = 1000
    ctrl.start()
    ctrl.last_scan = {"created_ms": 1000, "epoch": ctrl.epoch, "candidates": (),
                      "radius": 2500, "player_position": (0, 0),
                      "anchor_position": None}
    gw.add_outcome = "UNKNOWN"
    clock[0] = 2000
    ctrl.tick(2000)
    assert ctrl.state == "RECONCILING"
    assert ctrl.pending_request is not None
    gw.add_outcome = None
    # unresolved past deadline -> ERROR, VID quarantined for the epoch
    clock[0] = 5000
    ctrl.tick(5000)
    assert ctrl.state == "ERROR"
    assert 7 in ctrl.quarantine
    assert 7 not in ctrl.reject_backoff

    # stop on an all-owned queue disables once
    q[:] = []
    ctrl, gw, sel, clock = make_controller(q, enabled=False)
    clock[0] = 1000
    ctrl.start()
    q[:] = [7, 8]
    ctrl.ledger = {7, 8}
    ctrl.stop("stopped")
    assert q == [] and not gw.enabled  # disable cleared owned queue
    assert ctrl.state == "OFF"

    # foreign membership blocks bulk disable; selective remove preserves foreign
    q[:] = []
    ctrl, gw, sel, clock = make_controller(q, enabled=False)
    clock[0] = 1000
    ctrl.start()
    q[:] = [7, 90]
    ctrl.ledger = {7}
    ctrl.stop("stopped")
    assert 90 in q and 7 not in q  # foreign VID preserved

    # reaction pause stops the owned queue; resume revalidates empty+disabled
    q[:] = []
    ctrl, gw, sel, clock = make_controller(q, enabled=False)
    clock[0] = 1000
    ctrl.start()
    q[:] = [7]
    ctrl.ledger = {7}
    token = ctrl.pause("reaction")
    assert ctrl.state == "PAUSED" and q == [] and not gw.enabled
    ctrl.resume(token)
    assert ctrl.state == "RUNNING" and gw.enabled  # resume re-enables

    # Legendary priority drains owned entries one per tick, then adds the target
    q[:] = []
    ctrl, gw, sel, clock = make_controller(q, enabled=False, priority=True)
    clock[0] = 1000
    ctrl.start()
    q[:] = [7, 8]
    ctrl.ledger = {7, 8}
    ctrl.last_scan = {"created_ms": 1000, "epoch": ctrl.epoch,
                      "candidates": ({"vid": 11, "name": "Legendary Metinstone III",
                                      "vnum": 39922, "x": 100, "y": 100, "distance2": 20000},),
                      "radius": 2500, "player_position": (0, 0), "anchor_position": None}
    assert ctrl.request_priority() is True
    assert ctrl.priority_state == "DRAINING_OWNED"
    clock[0] = 2000
    ctrl.tick(2000)  # remove one owned per tick
    assert len(gw.remove_calls) == 1
    clock[0] = 2100
    ctrl.tick(2100)
    assert len(gw.remove_calls) == 2
    clock[0] = 2200
    ctrl.tick(2200)  # drain complete -> ADDING (schedules next add)
    assert ctrl.priority_state == "ADDING_PRIORITY"
    clock[0] = 2300
    ctrl.tick(2300)  # within add interval
    assert ctrl.priority_state == "ADDING_PRIORITY"
    clock[0] = 3300
    ctrl.tick(3300)  # add the priority target
    assert ctrl.priority_state == "ACTIVE_PRIORITY"

    # --- regression: Stop propagates failed cleanup (ERROR, not OFF) ---------
    q[:] = []
    ctrl, gw, sel, clock = make_controller(q, enabled=False)
    clock[0] = 1000
    ctrl.start()
    q[:] = [7]
    ctrl.ledger = {7}
    gw.fail_disable = True
    ctrl.stop("stopped")
    assert ctrl.state == "ERROR" and q == [7] and gw.enabled

    # --- regression: empty-but-enabled owned session is disabled on stop -----
    q[:] = []
    ctrl, gw, sel, clock = make_controller(q, enabled=False)
    clock[0] = 1000
    ctrl.start()  # enables the empty queue
    ctrl.stop("stopped")
    assert not gw.enabled and ctrl.state == "OFF"

    # --- regression: foreign membership revokes ownership --------------------
    q[:] = []
    ctrl, gw, sel, clock = make_controller(q, enabled=False)
    clock[0] = 1000
    ctrl.start()
    ctrl.last_scan = {"created_ms": 1000, "epoch": ctrl.epoch, "candidates": (),
                      "radius": 2500, "player_position": (0, 0), "anchor_position": None}
    q[:] = [90]  # a foreign VID appears in the queue
    clock[0] = 2000
    ctrl.tick(2000)
    assert ctrl.state == "ERROR"
    assert len(gw.add_calls) == 0  # no automatic add into a foreign queue

    # --- regression: a changed player cookie is not accepted as success ------
    q[:] = []
    ctrl, gw, sel, clock = make_controller(q, enabled=False)
    clock[0] = 1000
    ctrl.start()
    gw.cookie = 0xDEAD  # session changes after the lease was acquired
    clock[0] = 2000
    ctrl.tick(2000)
    assert ctrl.state == "ERROR"  # session change detected

    # --- Yin Yang Duel pure logic ------------------------------------------
    duel_globals = panel.PollYinYangDuel.__globals__
    choose_duel_card = duel_globals["choose_duel_card"]
    duel_card_color = duel_globals["duel_card_color"]
    assert duel_card_color(0) == "black" and duel_card_color(1) == "white"
    assert choose_duel_card([0, 1, 2, 3, 4, 5, 6, 7, 8], "black") == 5
    assert choose_duel_card([0, 1, 2, 3, 4, 5, 6, 7, 8], "white") == 6
    assert choose_duel_card([], "black") is None

    # --- Twin Souls pure logic ---------------------------------------------
    ts = panel.PollTwinSouls.__globals__
    MemorySolver = ts["MemorySolver"]
    MemoryKnowledge = ts["MemoryKnowledge"]
    MemoryBoardSnapshot = ts["MemoryBoardSnapshot"]
    enumerate_memory_cards = ts["enumerate_memory_cards"]

    def make_ts_snapshot(**kw):
        defaults = dict(board_id=1, window_id=1, state="playing", phase=None,
                        cell_count=8, pair_count=4, pairs_found=0,
                        time_remaining=30.0, bonus_remaining=None,
                        awaiting_flip=False, busy=False, open_cells=(),
                        matched_cells=frozenset(), visible_faces={},
                        selectable_cells=(), plays_used=0, plays_max=5,
                        plays_used_hwid=0, plays_max_hwid=10,
                        generation_signature=())
        if "open_cells" in kw:
            kw["open_cells"] = tuple(kw["open_cells"])
        if "matched" in kw:
            kw["matched_cells"] = frozenset(kw.pop("matched"))
        if "visible" in kw:
            kw["visible_faces"] = dict(kw.pop("visible"))
        if "selectable" in kw:
            kw["selectable_cells"] = tuple(kw.pop("selectable"))
        defaults.update(kw)
        return MemoryBoardSnapshot(**defaults)

    solver = MemorySolver()
    d = solver.choose_cell(
        make_ts_snapshot(open_cells=(0,), selectable=(1, 2, 3), visible={0: 7}),
        MemoryKnowledge())
    assert d["mode"] in ("known_mate", "complete_pair", "explore", "wait")
    # unknown cell selected when no pair exists
    k = MemoryKnowledge()
    k.known_face_by_cell = {}
    k.unmatched_cells_by_face = {}
    d = solver.choose_cell(make_ts_snapshot(selectable=(0, 1, 2, 3)), k)
    assert d["mode"] == "explore" and d["cell_index"] == 0

print("Hunter redesign local checks: OK")
