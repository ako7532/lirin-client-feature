"""Exercise the Python 2 feature logic with fake client UI and entity modules."""

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

    def __getattr__(self, name):
        if name.startswith("Set") or name == "AddFlag":
            return lambda *args: None
        raise AttributeError(name)

    def SetText(self, value):
        self.text = value

    def SetPosition(self, x, y):
        self.position = (x, y)

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
move_requests = []
chr_module.MoveToDestPosition = lambda vid, x, y: move_requests.append((vid, x, y))
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
add_calls = []  # ('native', vid) for each single-argument world add
projectable_vids = set(range(1, 12))  # VIDs 1..11 "project on screen" natively

def add_metin(vid, x=None, y=None):
    if vid == 0:
        # The native wrapper's bare-click sentinel (emit_synthetic_click): no
        # queue change, mirrors the real VID-0 click-only path.
        return 1
    # The world add is single-argument: the wrapper projects natively then
    # dispatches.  Simulate the native projection here.
    add_calls.append(("native", int(vid)))
    if vid not in projectable_vids:
        return 0  # native projection failed -> rejected
    if vid in queue:
        # Already present; the wrapper reports a distinct code and does not
        # dispatch a click (which the native path could turn into a removal).
        return 2
    if len(queue) >= queue_state["max_size"]:
        return 0
    queue.append(vid)
    return 1
player.MetinQueueAdd = add_metin
player.MetinQueueClear = clear_metin_queue
player.AddMetinQueueAllowedRace = lambda vnum: allowed_queue_races.add(int(vnum))
player.CanAttackInstance = lambda vid: vid in range(1, 12)
native_immune_vids = set()
native_untargetable_vids = set()
def set_native_vid_state(values, vid, enabled):
    vid = int(vid)
    if vid == 0:
        values.clear()
    elif enabled:
        values.add(vid)
    else:
        values.discard(vid)
player.SetMetinQueueVIDImmune = lambda vid, enabled: set_native_vid_state(
    native_immune_vids, vid, enabled)
player.SetMetinQueueVIDUntargetable = lambda vid, enabled: set_native_vid_state(
    native_untargetable_vids, vid, enabled)
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
    def __init__(self):
        self.last_hp = None

    def GetTargetVID(self):
        return target_state["vid"]

    def SetHP(self, percentage, current=0, maximum=0):
        self.last_hp = (percentage, current, maximum)


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

    def Show(self):
        self.visible = True


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
sys.modules["__main__"]._lirin_native_queue_wrapper = True

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
    assert panel.radius == 2500 and panel.radius_edit.GetText() == "2500"
    assert [label.text for label in panel.map_compass] == ["N", "S", "E", "W"]
    panel.native_queue_wrapper_active = False
    panel.ToggleMetinHunter()
    assert not panel.hunter_enabled
    try:
        panel.StartBossAttack((100, 10, 100, 100))
        raise AssertionError("Boss attack must require the native queue wrapper")
    except RuntimeError as exc:
        assert "native full-input queue wrapper missing" in str(exc)
    panel.native_queue_wrapper_active = True
    # Scanner-only Stop must not clear a native queue the feature does not own.
    panel.running = True
    queue_state["enabled"] = True
    queue[:] = [1]
    target_state["vid"] = 1
    panel.Stop()
    assert queue == [1] and queue_state["enabled"] and target_state["vid"] == 1
    queue[:] = []
    queue_state["enabled"] = False
    target_state["vid"] = 0
    original_find_runtime = panel.FindRuntimeObject
    disabled_discovery_calls = []
    panel.reaction_enabled = False
    def find_disabled_reaction(name, methods):
        disabled_discovery_calls.append(name)
        return reaction_window if name == "ReactionGameWindow" else None
    panel.FindRuntimeObject = find_disabled_reaction
    reaction_window.visible = True
    panel.reaction_window = None
    disabled_start_count = reaction_window.start_count
    disabled_click_count = len(reaction_window.clicked)
    panel.running = True
    panel.hunter_enabled = True
    queue_state["enabled"] = True
    queue[:] = [1, 2]
    target_state["vid"] = 1
    target_state["attack"] = True
    assert panel.PollReactionGame(9.0)
    assert disabled_discovery_calls == ["ReactionGameWindow"]
    assert reaction_window.start_count == disabled_start_count
    assert len(reaction_window.clicked) == disabled_click_count
    assert not queue and not queue_state["enabled"]
    assert target_state["vid"] == 0 and not target_state["attack"]
    assert panel.hunter_enabled and panel.reaction_native_paused
    assert "Manual reaction required" in Path(directory, "metin_scanner.log").read_text(encoding="ascii")
    reaction_window.visible = False
    panel.reaction_next_poll = 0.0
    assert not panel.PollReactionGame(9.1)
    panel.ResumeAfterReaction(9.1)
    assert queue_state["enabled"] and panel.hunter_initial_fill
    clear_count = queue_clear_state["count"]
    panel.ClearNativeAutomation()
    assert queue_clear_state["count"] == clear_count + 1
    panel.hunter_enabled = False
    panel.running = False
    panel.reaction_enabled = True
    panel.reaction_next_poll = 0.0
    panel.FindRuntimeObject = lambda name, methods: (
        reaction_window if name == "ReactionGameWindow"
        else original_find_runtime(name, methods)
    )
    reaction_window.visible = True
    assert panel.PollReactionGame(10.0)
    assert reaction_window.start_count == 1
    reaction_globals = panel.PollReactionGame.__globals__
    feature_random = reaction_globals["random"]
    original_choice = feature_random.choice
    original_uniform = feature_random.uniform
    delay_samples = reaction_globals["REACTION_CLICK_DELAY_SAMPLES"]
    feature_random.choice = lambda values: min(values)
    feature_random.uniform = lambda minimum, maximum: minimum
    assert reaction_globals["next_reaction_click_delay"]() == 0.30
    feature_random.choice = lambda values: max(values)
    feature_random.uniform = lambda minimum, maximum: maximum
    assert reaction_globals["next_reaction_click_delay"]() == 0.99
    original_delay_function = reaction_globals["next_reaction_click_delay"]
    scheduled_delays = []
    def fixed_reaction_delay():
        scheduled_delays.append(True)
        return 0.60
    reaction_globals["next_reaction_click_delay"] = fixed_reaction_delay
    panel.reaction_next_poll = 0.0
    assert panel.PollReactionGame(10.1)
    assert reaction_window.clicked == []
    assert scheduled_delays == [True]
    panel.reaction_next_poll = 0.0
    panel.PollReactionGame(10.2)
    assert reaction_window.clicked == []
    panel.reaction_next_poll = 0.0
    panel.PollReactionGame(10.71)
    assert reaction_window.clicked == [2]
    reaction_window.lastBallMoveTime = 2.0
    panel.reaction_next_poll = 0.0
    panel.PollReactionGame(10.8)
    assert reaction_window.clicked == [2]
    assert scheduled_delays == [True, True]
    panel.reaction_next_poll = 0.0
    panel.PollReactionGame(11.41)
    assert reaction_window.clicked == [2, 2]
    reaction_globals["next_reaction_click_delay"] = original_delay_function
    feature_random.choice = original_choice
    feature_random.uniform = original_uniform
    assert len(delay_samples) == 37
    panel.boss_enabled = True
    panel.boss_state_started = 5.0
    panel.boss_deadline = 20.0
    reaction_window.visible = False
    panel.reaction_next_poll = 0.0
    assert not panel.PollReactionGame(11.5)
    assert panel.reaction_window is reaction_window
    panel.ResumeAfterReaction(11.5)
    assert panel.reaction_pause_started is None
    assert round(panel.boss_deadline, 1) == 21.5
    panel.boss_enabled = False
    assert len(panel.map_ring) == 96
    assert all(dot.visible for dot in panel.map_ring)
    panel.Start()
    panel.OnUpdate()
    assert panel.last_scan_error is not None
    assert all(dot.visible for dot in panel.map_ring)

    panel.radius_edit.SetText("2000")
    panel.OnUpdate()
    assert panel.radius == 2000
    assert "2000" in panel.radar_label.text

    Path(directory, "client_feature_vids.txt").write_text(
        "PID %d\n" % os.getpid(), encoding="ascii"
    )
    panel.next_scan = 0
    panel.OnUpdate()
    assert all(dot.visible for dot in panel.map_ring)
    assert not panel.map_metins[0].visible
    assert "no metins visible in range" in Path(directory, "metin_scanner.log").read_text(encoding="ascii")

    Path(directory, "client_feature_vids.txt").write_text(
        "PID %d\n1\n2\n3\n" % os.getpid(), encoding="ascii"
    )
    panel.radius_edit.SetText("1000")
    panel.next_scan = 0
    panel.OnUpdate()
    log_path = Path(directory, "metin_scanner.log")
    first_log = log_path.read_text(encoding="ascii")
    assert "Battle Metin" in first_log and "vnum 8003" in first_log, first_log
    assert "Jealousy Metin" not in first_log
    assert panel.map_metins[0].visible
    assert panel.map_metins[0].position == (616, 176), panel.map_metins[0].position
    assert not panel.map_metins[1].visible
    assert panel.map_others[0].visible
    panel.radius_edit.SetText("2000")
    panel.next_scan = 0
    panel.OnUpdate()
    second_log = log_path.read_text(encoding="ascii")
    assert "Jealousy Metin" in second_log and "vnum 8004" in second_log
    assert panel.map_metins[1].visible
    Path(directory, "client_feature_vids.txt").write_text(
        "PID %d\n1\n2\n4\n5\n6\n" % os.getpid(), encoding="ascii"
    )
    panel.ToggleMetinHunter()
    assert panel.hunter_enabled and queue_state["enabled"]
    for expected_size in range(1, 6):
        panel.hunter_next_add = 0
        panel.next_scan = 0
        panel.OnUpdate()
        assert len(queue) == expected_size, queue
    assert set(queue) == {1, 2, 4, 5, 6}, queue
    panel.next_scan = 0
    panel.OnUpdate()
    assert len(queue) == 5, queue

    # Time-driven refill: after the queue is full, wait a noisy interval before
    # refilling, with a random (not nearest) target.
    panel.hunter_refilling = False
    panel.hunter_queued_vids.clear()
    panel.hunter_next_refill = time.time() + 100.0
    queue[:] = [90, 91, 92, 93]
    panel.hunter_next_add = 0
    panel.FeedMetinQueue([(1400, 7, "Jealousy Metin")])
    assert queue == [90, 91, 92, 93], queue
    assert not panel.hunter_refilling
    assert "Waiting 4/5" in panel.hunter_label.text
    assert "refill in" in panel.hunter_label.text
    panel.hunter_next_refill = time.time() - 1.0
    panel.FeedMetinQueue([(1400, 7, "Jealousy Metin")])
    assert queue == [90, 91, 92, 93, 7], queue
    assert not panel.hunter_refilling
    assert "Full 5/5" in panel.hunter_label.text
    assert "refill in" in panel.hunter_label.text
    refill_deadline = panel.hunter_next_refill
    queue[:] = [90, 91, 92, 93, 7]
    panel.hunter_next_add = 0
    panel.FeedMetinQueue([(1400, 8, "Battle Metin")])
    assert queue == [90, 91, 92, 93, 7], queue
    assert not panel.hunter_refilling
    assert panel.hunter_next_refill > time.time()
    assert panel.hunter_next_refill == refill_deadline

    # Full-queue polls must not move the deadline, even after it expires.
    # Arm immediately on the successful add: the queue may drain before the
    # next scan ever observes it full.
    feature_globals = panel.FeedMetinQueue.__globals__
    original_time_module = feature_globals["time"]
    simulated_now = [1000.0]
    feature_globals["time"] = types.SimpleNamespace(
        time=lambda: simulated_now[0], strftime=time.strftime, localtime=time.localtime)
    try:
        panel.hunter_queued_vids.clear()
        panel.hunter_refilling = True
        panel.hunter_next_add = 0
        queue[:] = [90, 91, 92, 93]
        panel.FeedMetinQueue([(1400, 7, "Jealousy Metin")])
        deadline = panel.hunter_next_refill
        assert 1035 <= deadline <= 1070
        assert not panel.hunter_refilling
        for tick in (1001.0, deadline - 1, deadline + 1):
            simulated_now[0] = tick
            panel.FeedMetinQueue([])
            assert panel.hunter_next_refill == deadline
            assert "Full 5/5" in panel.hunter_label.text
        # A fully drained queue must bypass the long refill wait.
        simulated_now[0] = deadline - 1
        queue[:] = []
        panel.hunter_next_add = 0
        panel.FeedMetinQueue([(1500, 8, "Battle Metin")])
        assert queue == [8], queue
        assert "Refilling 1/5" in panel.hunter_label.text
        queue[:] = [90, 91, 92, 93]
        panel.hunter_queued_vids.discard(8)
        panel.hunter_refilling = True
        panel.hunter_next_add = 0
        panel.FeedMetinQueue([(1500, 8, "Battle Metin")])
        assert queue == [90, 91, 92, 93, 8]
        assert panel.hunter_next_refill > simulated_now[0]
    finally:
        feature_globals["time"] = original_time_module
    panel.hunter_refilling = False

    # Native actor type and per-VID exclusions are enforced before low-level add.
    panel.hunter_next_refill = time.time() - 1.0
    queue[:] = []
    panel.hunter_queued_vids.clear()
    actor_stone_overrides[7] = False
    panel.hunter_next_add = 0
    panel.FeedMetinQueue([(1400, 7, "Jealousy Metin")])
    assert not queue
    actor_stone_overrides.pop(7)
    # A projectable target goes through the native full-dispatch route (the
    # wrapper projects and dispatches natively from the single-argument call).
    panel.hunter_next_add = 0
    panel.FeedMetinQueue([(1400, 7, "Jealousy Metin")])
    assert queue == [7]
    assert ("native", 7) in add_calls
    queue[:] = []
    panel.hunter_queued_vids.clear()
    player.SetMetinQueueVIDImmune(7, 1)
    panel.hunter_next_add = 0
    panel.FeedMetinQueue([(1400, 7, "Jealousy Metin")])
    assert not queue
    player.SetMetinQueueVIDImmune(7, 0)
    player.SetMetinQueueVIDUntargetable(7, 1)
    panel.hunter_next_add = 0
    panel.FeedMetinQueue([(1400, 7, "Jealousy Metin")])
    assert not queue
    player.SetMetinQueueVIDUntargetable(7, 0)
    panel.hunter_next_add = 0
    panel.FeedMetinQueue([(1400, 7, "Jealousy Metin")])
    assert queue == [7]
    queue_guard_log = log_path.read_text(encoding="ascii")
    assert "native immune VID" in queue_guard_log
    assert "native untargetable VID" in queue_guard_log

    # A target that does not project on screen is rejected by the native
    # projection (result 0), never queued and never retried immediately.
    queue[:] = []
    panel.hunter_queued_vids.clear()
    add_calls[:] = []
    projectable_vids.discard(7)
    panel.hunter_next_add = 0
    panel.FeedMetinQueue([(1400, 7, "Jealousy Metin")])
    assert not queue and 7 not in panel.hunter_queued_vids
    assert add_calls == [("native", 7)]  # single-argument call, then rejected
    projectable_vids.add(7)
    queue[:] = []
    panel.hunter_queued_vids.clear()

    # _dispatch_native_add maps a post-dispatch exception to UNKNOWN (3), never
    # a rejection, because the click may already have executed.
    add_calls[:] = []
    original_add = player.MetinQueueAdd

    def raise_on_add(vid, x=None, y=None):
        raise RuntimeError("dispatch exploded")

    player.MetinQueueAdd = raise_on_add
    assert panel._dispatch_native_add(7, 2.0) == 3
    player.MetinQueueAdd = original_add

    # A non-positive VID is rejected before any dispatch or projection.
    add_calls[:] = []
    assert panel._dispatch_native_add(0, 2.0) == 0
    assert add_calls == []

    panel.ToggleMetinHunter()
    queue[:] = [90, 91, 92]
    queue_state["max_size"] = 3
    panel.ToggleMetinHunter()
    panel.hunter_next_add = 0
    panel.next_scan = 0
    panel.OnUpdate()
    assert len(queue) == 3 and "3/3" in panel.hunter_label.text, queue
    panel.ToggleMetinHunter()
    queue[:] = []
    queue_state["max_size"] = 5
    Path(directory, "client_feature_vids.txt").write_text(
        "PID %d\n1\n2\n3\n" % os.getpid(), encoding="ascii"
    )
    panel.radius_edit.SetText("1000")
    panel.OnUpdate()
    panel.ToggleAnchor()
    assert panel.anchor_position == (0, 0)
    player_position[0] = 2000
    panel.ToggleMetinHunter()
    panel.hunter_next_add = 0
    panel.next_scan = 0
    panel.player_next_poll = 0
    panel.watcher.OnUpdate()
    assert not queue, queue
    assert not panel.map_player.visible
    panel.ToggleAnchor()
    assert panel.anchor_position is None
    panel.next_scan = 0
    panel.player_next_poll = 0
    panel.watcher.OnUpdate()
    assert queue == [2], queue
    assert panel.map_player.visible

    running_before_minimize = panel.running
    hunter_before_minimize = panel.hunter_enabled
    queue_before_minimize = list(queue)
    assert "minimize_button" not in panel.__dict__
    panel.close_event()
    assert not panel.visible
    assert panel.running == running_before_minimize
    assert panel.hunter_enabled == hunter_before_minimize
    assert queue == queue_before_minimize
    panel.TogglePanel()
    assert panel.visible

    pressed_keys.update((app.DIK_LCONTROL, app.DIK_F8))
    panel.watcher.OnUpdate()
    assert not panel.visible and panel.watcher.visible
    panel.next_scan = 0
    before_hidden_scan = len(log_path.read_text(encoding="ascii"))
    panel.watcher.OnUpdate()
    assert not panel.visible
    assert len(log_path.read_text(encoding="ascii")) > before_hidden_scan
    pressed_keys.clear()
    panel.watcher.OnUpdate()
    pressed_keys.update((app.DIK_LCONTROL, app.DIK_F8))
    panel.watcher.OnUpdate()
    assert panel.visible
    pressed_keys.clear()

    # Marking a boss preserves an existing Metin anchor and stores the boss position.
    panel.anchor_position = (2000, 0)
    panel.anchor_channel = 1
    panel.anchor_map = "metin2_map_test"
    player_position[0] = 2500
    target_state["vid"] = 10
    panel.MarkBoss()
    assert panel.boss_vnum == 2493
    assert panel.anchor_position == (2000, 0)
    assert panel.boss_position == (2100, 0)
    assert panel.anchor_channel == 1
    assert "return anchor 2000, 0" in log_path.read_text(encoding="ascii")
    assert "timer=yes channels=3" in log_path.read_text(encoding="ascii")
    Path(directory, "client_feature_vids.txt").write_text(
        "PID %d\n10\n" % os.getpid(), encoding="ascii"
    )
    boss_timer.remaining = 0
    panel.ToggleBossSweep()
    assert panel.boss_enabled
    def boss_update():
        panel.boss_next_poll = 0.0
        panel.player_next_poll = 0.0
        panel.OnUpdate()
    boss_update()
    assert panel.boss_state == "find", panel.boss_state
    assert not queue and not queue_state["enabled"]
    target_state["vid"] = 0
    boss_update()
    assert panel.boss_state == "attack", panel.boss_state
    assert not target_state["attack"]
    assert target_state["vid"] == 0
    assert queue == [10] and queue_state["enabled"]
    assert 2493 in allowed_queue_races

    Path(directory, "client_feature_vids.txt").write_text(
        "PID %d\n" % os.getpid(), encoding="ascii"
    )
    panel.boss_target_missing_since = 0.0
    boss_update()
    assert panel.boss_state == "wait_channel", panel.boss_state
    assert channel_state["current"] == 2
    assert not queue and not queue_state["enabled"]
    Path(directory, "client_feature_vids.txt").write_text(
        "PID %d\n" % os.getpid(), encoding="ascii"
    )
    connection_state["connected"] = False
    panel.gameplay_next_check = 0
    boss_update()
    assert panel.boss_enabled and panel.boss_state == "wait_channel"
    connection_state["connected"] = True
    panel.gameplay_next_check = 0
    boss_update()
    assert panel.boss_state == "settle_channel", panel.boss_state
    panel.boss_deadline = 0.0
    boss_update()
    assert panel.boss_state == "find", panel.boss_state
    assert 2.9 <= panel.boss_deadline - panel.boss_state_started <= 3.1
    panel.boss_deadline = 0.0
    boss_update()
    assert channel_state["current"] == 3

    panel.boss_channel_index = len(panel.boss_channels) - 1
    player_position[0] = 2600
    panel.AdvanceBossChannel()
    assert channel_state["current"] == 1
    Path(directory, "client_feature_vids.txt").write_text(
        "PID %d\n" % os.getpid(), encoding="ascii"
    )
    boss_update()
    panel.boss_deadline = 0.0
    boss_update()
    assert panel.boss_state == "return_position", panel.boss_state
    boss_update()
    assert move_requests[-1] == (999, 2000, 0)
    first_return_move_count = len(move_requests)
    boss_update()
    assert len(move_requests) == first_return_move_count
    panel.boss_return_last_progress = time.time() - 3.1
    boss_update()
    assert panel.boss_state == "wait_timer", panel.boss_state
    assert panel.boss_enabled and panel.hunter_enabled and queue_state["enabled"]
    assert not target_state["attack"]
    assert target_state["mouse"] == 17
    assert "return blocked inside Metin circle" in log_path.read_text(encoding="ascii")
    player_position[0] = 2000

    # A stale timer can remain at zero after a completed sweep. A live marked
    # boss in the current actor snapshot must start the next sweep without
    # requiring the user to toggle Boss Sweep OFF and ON.
    assert not panel.boss_timer_armed
    boss_timer.remaining = 0
    Path(directory, "client_feature_vids.txt").write_text(
        "PID %d\n10\n" % os.getpid(), encoding="ascii"
    )
    boss_update()
    assert panel.boss_state == "find", panel.boss_state
    assert not panel.hunter_enabled and not queue_state["enabled"]
    assert "starting sweep without timer edge" in log_path.read_text(encoding="ascii")
    panel.ToggleBossSweep()
    assert not panel.boss_enabled and queue_state["enabled"]

    Path(directory, "client_feature_vids.txt").write_text(
        "PID %d\n1\n2\n" % os.getpid(), encoding="ascii"
    )
    panel.radius_edit.SetText("2000")
    panel.next_scan = 0
    panel.OnUpdate()
    panel.hunter_next_add = 0
    panel.next_scan = 0
    panel.OnUpdate()
    assert set(queue) == {1, 2}, queue

    # Any native stone whose name contains Legendary Metinstone interrupts the
    # ordinary Hunter queue, remains the only queued target, then restores
    # paced Hunter refill after its VID has been absent for the grace period.
    Path(directory, "client_feature_vids.txt").write_text(
        "PID %d\n1\n2\n11\n" % os.getpid(), encoding="ascii"
    )
    panel.Scan(tuple(player_position))
    assert queue == [11] and queue_state["enabled"]
    assert panel.priority_event_vid == 11 and panel.hunter_enabled
    panel.Scan(tuple(player_position))
    assert queue == [11]
    Path(directory, "client_feature_vids.txt").write_text(
        "PID %d\n1\n2\n" % os.getpid(), encoding="ascii"
    )
    panel.Scan(tuple(player_position))
    assert queue == [11] and panel.priority_event_missing_since is not None
    panel.priority_event_missing_since = time.time() - 1.6
    panel.Scan(tuple(player_position))
    assert panel.priority_event_vid == 0 and panel.hunter_enabled
    assert queue and queue[0] != 11 and queue_state["enabled"]
    assert "ordinary queue cancelled" in log_path.read_text(encoding="ascii")
    assert "ordinary Hunter restored" in log_path.read_text(encoding="ascii")
    panel.Stop()
    assert not panel.running
    assert not panel.hunter_enabled and not queue and not queue_state["enabled"]
    assert target_state["vid"] == 0 and not target_state["attack"]
    assert not panel.map_metins[0].visible
    assert all(dot.visible for dot in panel.map_ring)

    # Queue admission revalidates the entity and remembers only accepted VIDs.
    panel.running = True
    panel.hunter_enabled = True
    panel.hunter_initial_fill = True
    panel.hunter_batch_add_count = 0
    panel.hunter_next_add = 0
    queue_state["enabled"] = True
    panel.radius = 2000
    player_position[0] = 0
    original_can_attack = player.CanAttackInstance
    player.CanAttackInstance = lambda vid: False
    panel.FeedMetinQueue([(500, 1, "Battle Metin")])
    assert 1 not in panel.hunter_queued_vids and not queue
    player.CanAttackInstance = original_can_attack
    original_queue_add = player.MetinQueueAdd
    player.MetinQueueAdd = lambda vid, x=None, y=None: False
    panel.FeedMetinQueue([(500, 1, "Battle Metin")])
    assert 1 not in panel.hunter_queued_vids and not queue
    player.MetinQueueAdd = original_queue_add
    # An UNKNOWN outcome must not be marked queued, so the next scan re-attempts
    # (the wrapper reports "already present" if the add actually landed).
    original_queue_add = player.MetinQueueAdd
    player.MetinQueueAdd = lambda vid, x=None, y=None: 3
    panel.FeedMetinQueue([(500, 1, "Battle Metin")])
    assert 1 not in panel.hunter_queued_vids and not queue
    player.MetinQueueAdd = original_queue_add
    panel.hunter_next_add = 0
    panel.FeedMetinQueue([(100, 9999, "Stale Metin")])
    assert 9999 not in panel.hunter_queued_vids and not queue
    panel.Stop()

    # A real phase exit must stop Python updates and the independent native queue.
    net.SetPhaseWindow(5, object())
    panel.Start()
    panel.ToggleMetinHunter()
    panel.next_scan = 0
    panel.OnUpdate()
    assert panel.running and panel.hunter_enabled and queue_state["enabled"]
    net.SetPhaseWindow(4, object())
    assert panel.running and panel.hunter_enabled
    assert not queue and not queue_state["enabled"]
    panel.OnUpdate()
    assert not queue
    net.SetPhaseWindow(5, object())
    assert queue_state["enabled"]

    net.Disconnect("local-diagnostic")
    assert disconnect_calls[-1][0] == ("local-diagnostic",)
    assert "Python net.Disconnect called" in log_path.read_text(encoding="ascii")

    # A socket loss is detected before the client eventually changes to login phase.
    connection_state["connected"] = False
    panel.gameplay_next_check = 0
    panel.OnUpdate()
    assert not panel.running and not panel.hunter_enabled
    assert not queue and not queue_state["enabled"]
    assert "game connection is closed" in log_path.read_text(encoding="ascii")
    connection_state["connected"] = True
    panel.gameplay_next_check = 0
    panel.Start()
    panel.ToggleMetinHunter()
    assert panel.running and panel.hunter_enabled
    net.SetPhaseWindow(1, None)
    assert panel.running and panel.hunter_enabled
    net.SetPhaseWindow(1, object())
    assert phase_window_calls[-1][0] == 1
    assert not panel.running and not panel.hunter_enabled and not panel.boss_enabled
    assert not queue and not queue_state["enabled"]
    before_exit_update = len(log_path.read_text(encoding="ascii"))
    panel.next_scan = 0
    panel.OnUpdate()
    assert not queue
    assert len(log_path.read_text(encoding="ascii")) == before_exit_update
    panel.Start()
    assert not panel.running
    assert "Start blocked" in log_path.read_text(encoding="ascii")

    # Character identity is the fallback when no non-game phase event arrives.
    net.SetPhaseWindow(5, object())
    main_character["vid"] = 0
    panel.gameplay_next_check = 0
    panel.Start()
    assert not panel.running and not queue_state["enabled"]

    # Static settings persist, auto-load on a new panel, and never auto-start automation.
    main_character["vid"] = 999
    panel.radius_edit.SetText("3456")
    panel.radius = 3456
    panel.anchor_position = (1111, 2222)
    panel.anchor_channel = 3
    panel.anchor_map = "metin2_map_saved"
    panel.boss_vnum = 2493
    panel.boss_name = "Saved Boss"
    panel.boss_position = (3333, 4444)
    panel.boss_mark_channel = 3
    panel.boss_map = "metin2_map_saved"
    panel.reaction_enabled = False
    panel.config_autoload = True
    assert panel.SaveConfig()
    config_text = Path(directory, "client_feature_config.txt").read_text(encoding="ascii")
    assert "autoload=1" in config_text and "radius=3456" in config_text
    panel.radius_edit.SetText("1000")
    panel.anchor_position = None
    panel.boss_position = None
    panel.reaction_enabled = True
    assert panel.LoadConfig()
    assert panel.radius == 3456
    assert panel.anchor_position == (1111, 2222) and panel.anchor_channel == 3
    assert panel.boss_position == (3333, 4444) and panel.boss_vnum == 2493
    assert not panel.reaction_enabled and panel.config_autoload
    panel.Dispose()
    loaded_panel = type(panel)()
    assert loaded_panel.radius == 3456
    assert loaded_panel.anchor_position == (1111, 2222)
    assert loaded_panel.boss_position == (3333, 4444)
    assert not loaded_panel.reaction_enabled
    assert not loaded_panel.running and not loaded_panel.hunter_enabled
    assert not loaded_panel.boss_enabled
    loaded_panel.Dispose()

    # Yin Yang Duel strategy (cards 0..8; even=black, odd=white).
    duel_globals = panel.PollYinYangDuel.__globals__
    choose_duel_card = duel_globals["choose_duel_card"]
    choose_duel_card_follow = duel_globals["choose_duel_card_follow"]
    choose_duel_card_lead = duel_globals["choose_duel_card_lead"]
    duel_card_color = duel_globals["duel_card_color"]
    assert duel_card_color(0) == "black" and duel_card_color(1) == "white"
    assert choose_duel_card([0, 1, 2, 3, 4, 5, 6, 7, 8], "black") == 5
    assert choose_duel_card([0, 1, 2, 3, 4, 5, 6, 7, 8], "white") == 6
    assert choose_duel_card([0, 1], "black") == 0
    assert choose_duel_card([0, 1, 2, 3, 4, 5, 6, 7, 8], None) == 4
    assert choose_duel_card([], "black") is None
    assert choose_duel_card_follow([0, 1, 2, 3, 4, 5, 6, 7, 8], 6) == 7
    assert choose_duel_card_follow([0, 1, 2, 3], 8) == 0
    assert choose_duel_card_follow([], 3) is None
    assert choose_duel_card_lead([0, 1, 2, 3, 4, 5, 6, 7, 8], {1, 3, 5, 7}) == 6
    assert choose_duel_card_lead([0, 1, 2], {7, 8}) == 0
    assert choose_duel_card_lead([], {}) is None

    # Yin Yang Duel solver (pure card-game logic).
    DuelSolver = duel_globals["DuelSolver"]
    DuelSnapshot = duel_globals["DuelSnapshot"]
    duel_mask_cards = duel_globals["duel_mask_cards"]
    duel_mask_count = duel_globals["duel_mask_count"]
    duel_mask_remove = duel_globals["duel_mask_remove"]
    duel_mask_color = duel_globals["duel_mask_color"]
    round_score_delta = duel_globals["round_score_delta"]
    terminal_duel_value = duel_globals["terminal_duel_value"]

    assert duel_mask_cards(0x1FF) == [0, 1, 2, 3, 4, 5, 6, 7, 8]
    assert duel_mask_count(0x1FF) == 9
    assert duel_mask_remove(0x1FF, 4) == 0x1FF & ~(1 << 4)
    assert duel_mask_cards(duel_mask_color(0x1FF, "black")) == [0, 2, 4, 6, 8]
    assert round_score_delta(6, 3) == 1
    assert round_score_delta(3, 6) == -1
    assert round_score_delta(5, 5) == 0
    assert terminal_duel_value(2) == (1.0, 0.0, 2.0, 1.0)
    assert terminal_duel_value(-1) == (0.0, -1.0, -1.0, -1.0)
    assert terminal_duel_value(0) == (0.0, 0.0, 0.0, 0.0)

    solver = DuelSolver()
    # One-card exact follow: only card 7, opponent led 6 -> must play 7.
    one_card = DuelSnapshot(match_id=1, round_num=9, state=2, we_lead=False,
                            visible_color="black", exact_opponent_led_value=6,
                            exact_value_confident=True,
                            our_remaining_mask=1 << 7,
                            opponent_remaining_mask=1 << 6,
                            our_score=4, opponent_score=4)
    d = solver.choose_move(one_card, time.time() + 2.0)
    assert d is not None and d["card_value"] == 7, d
    # One-card exact follow where we cannot beat: only card 2 vs led 6.
    lose_card = DuelSnapshot(match_id=1, round_num=9, state=2, we_lead=False,
                             visible_color="black", exact_opponent_led_value=6,
                             exact_value_confident=True,
                             our_remaining_mask=1 << 2,
                             opponent_remaining_mask=1 << 6,
                             our_score=4, opponent_score=4)
    d2 = solver.choose_move(lose_card, time.time() + 2.0)
    assert d2 is not None and d2["card_value"] == 2, d2
    # 2-card exact follow: {5,7} vs led 6, opponent remaining {8}.  Playing 7
    # ties the match; playing 5 loses it, so the solver must choose 7.
    follow2 = DuelSnapshot(match_id=1, round_num=8, state=2, we_lead=False,
                           visible_color="black", exact_opponent_led_value=6,
                           exact_value_confident=True,
                           our_remaining_mask=(1 << 5) | (1 << 7),
                           opponent_remaining_mask=1 << 8,
                           our_score=0, opponent_score=0)
    d4 = solver.choose_move(follow2, time.time() + 2.0)
    assert d4 is not None and d4["card_value"] == 7, d4
    # Full-hand lead decision must return a valid in-hand card (and not crash).
    full = DuelSnapshot(match_id=1, round_num=1, state=2, we_lead=True,
                        visible_color=None, exact_opponent_led_value=None,
                        exact_value_confident=False,
                        our_remaining_mask=0x1FF, opponent_remaining_mask=0x1FF,
                        our_score=0, opponent_score=0)
    d3 = solver.choose_move(full, time.time() + 3.0)
    assert d3 is not None and d3["card_value"] in duel_mask_cards(0x1FF), d3

    # Brute-force reference (no memoization) for small exact-follow hands.
    def brute_value(om, pm, sd, leader):
        oc = duel_mask_cards(om)
        pc = duel_mask_cards(pm)
        if not oc:
            return terminal_duel_value(sd)
        if leader == "us":
            best = None
            for a in oc:
                exp = [0.0, 0.0, 0.0, 0.0]
                worst = None
                for b in pc:
                    v = brute_value(duel_mask_remove(om, a), duel_mask_remove(pm, b),
                                    sd + round_score_delta(a, b), "them")
                    for i in range(4):
                        exp[i] += v[i] / len(pc)
                    if worst is None or v < worst:
                        worst = v
                val = tuple(0.75 * exp[i] + 0.25 * worst[i] for i in range(4))
                if best is None or val > best:
                    best = val
            return best
        exp = [0.0, 0.0, 0.0, 0.0]
        worst = None
        for b in pc:
            best_a = None
            for a in oc:
                v = brute_value(duel_mask_remove(om, a), duel_mask_remove(pm, b),
                                sd + round_score_delta(a, b), "us")
                if best_a is None or v > best_a:
                    best_a = v
            for i in range(4):
                exp[i] += best_a[i] / len(pc)
            if worst is None or best_a < worst:
                worst = best_a
        return tuple(0.75 * exp[i] + 0.25 * worst[i] for i in range(4))

    def brute_exact(our_mask, opp_mask, score_delta, b):
        best_val, best_card = None, None
        for a in duel_mask_cards(our_mask):
            v = brute_value(duel_mask_remove(our_mask, a),
                            duel_mask_remove(opp_mask, b),
                            score_delta + round_score_delta(a, b), "us")
            if best_val is None or v > best_val or (v == best_val and a < best_card):
                best_val, best_card = v, a
        return best_card

    rng = duel_globals["random"].Random(7)
    for _ in range(25):
        size = rng.randint(1, 4)
        our_vals = rng.sample(range(9), size)
        opp_vals = rng.sample(range(9), size)
        led = rng.choice(opp_vals)
        our_mask = sum(1 << v for v in our_vals)
        opp_mask = sum(1 << v for v in opp_vals)
        snap = DuelSnapshot(match_id=1, round_num=9 - size, state=2, we_lead=False,
                            visible_color=duel_card_color(led),
                            exact_opponent_led_value=led, exact_value_confident=True,
                            our_remaining_mask=our_mask,
                            opponent_remaining_mask=opp_mask & ~(1 << led),
                            our_score=0, opponent_score=0)
        got = solver.choose_move(snap, time.time() + 2.0)
        expect = brute_exact(our_mask, opp_mask, 0, led)
        assert got is not None and got["card_value"] == expect, (our_vals, opp_vals, led, got, expect)

    # DuelRoundTracker: a stale exact-led value must be cleared when the round
    # advances, so a later follow round never reuses a previous round's card.
    DuelRoundTracker = duel_globals["DuelRoundTracker"]

    class DuelCard:
        def __init__(self, value, played=False):
            self.value = value
            self.played = played

    class DuelWindow:
        def __init__(self):
            self.state = 2
            self.playerScore = 0
            self.opponentScore = 0
            self.leadInfo = {"leads": True, "black": True, "round": 1}
            self.playerCards = {v: DuelCard(v) for v in range(9)}
            self.opponentCards = {v: DuelCard(v) for v in range(9)}

    tracker = DuelRoundTracker()
    window = DuelWindow()
    tracker.on_window(window)
    # Round 1: `leads=True` means the opponent led (we follow).  Their led card
    # 4 is black, so it is detected as the exact led value.
    window.opponentCards[4].played = True
    newly, exact = tracker.observe_opponent(window)
    assert newly == [4] and exact == 4, (newly, exact)
    snap = tracker.build_snapshot(window)
    assert snap is not None and snap.exact_opponent_led_value == 4
    assert snap.we_lead is False
    # We answered in round 1 (our card 2 played); round advances to 2 and the
    # opponent leads again, but the reported colour mismatches (card 6 is
    # black, flag says white) so detection fails.  The stale round-1 value must
    # not leak into the snapshot.
    window.playerCards[2].played = True
    window.leadInfo = {"leads": True, "black": False, "round": 2}
    window.opponentCards[6].played = True
    newly, exact = tracker.observe_opponent(window)
    assert exact is None, exact
    snap = tracker.build_snapshot(window)
    assert snap is not None, "count validation rejected a valid follow state"
    assert snap.exact_opponent_led_value is None, snap.exact_opponent_led_value

    # --- Twin Souls (YinYangMemory / Pexeso) ---
    ts = panel.PollTwinSouls.__globals__
    MemoryBoardSnapshot = ts["MemoryBoardSnapshot"]
    MemoryKnowledge = ts["MemoryKnowledge"]
    MemorySolver = ts["MemorySolver"]
    MemoryBoardTracker = ts["MemoryBoardTracker"]
    MemoryActionAdapter = ts["MemoryActionAdapter"]
    enumerate_memory_cards = ts["enumerate_memory_cards"]
    normalize_memory_face = ts["normalize_memory_face"]
    classify_memory_state = ts["classify_memory_state"]
    resolve_minigame_owner = ts["resolve_minigame_owner"]

    def make_ts_snapshot(state="playing", awaiting=False, busy=False,
                         open_cells=(), matched=(), visible=None,
                         selectable=(), cell_count=8, pair_count=4,
                         pairs_found=0, plays_max=5, plays_max_hwid=10,
                         plays_used=0, plays_used_hwid=0):
        return MemoryBoardSnapshot(
            board_id=1, window_id=1, state=state, phase=None,
            cell_count=cell_count, pair_count=pair_count,
            pairs_found=pairs_found, time_remaining=30.0,
            bonus_remaining=None, awaiting_flip=awaiting, busy=busy,
            open_cells=tuple(open_cells), matched_cells=frozenset(matched),
            visible_faces=dict(visible or {}),
            selectable_cells=tuple(selectable),
            plays_used=plays_used, plays_max=plays_max,
            plays_used_hwid=plays_used_hwid, plays_max_hwid=plays_max_hwid,
            generation_signature=())

    def make_ts_knowledge(known=None, unmatched=None):
        k = MemoryKnowledge()
        k.known_face_by_cell = dict(known or {})
        k.unmatched_cells_by_face = dict(
            (face, set(cells)) for face, cells in (unmatched or {}).items())
        return k

    ts_solver = MemorySolver()

    # Solver: known open mate is selected.
    d = ts_solver.choose_cell(
        make_ts_snapshot(open_cells=(0,), selectable=(1, 2, 3), visible={0: 7}),
        make_ts_knowledge(known={0: 7, 1: 7}, unmatched={7: {0, 1}}))
    assert d["mode"] == "known_mate" and d["cell_index"] == 1 and d["face"] == 7, d
    assert d["mate_cell"] == 0, d

    # Solver: a complete known pair is selected before exploration.
    d = ts_solver.choose_cell(
        make_ts_snapshot(selectable=(0, 1, 2, 3)),
        make_ts_knowledge(known={0: 5, 1: 5}, unmatched={5: {0, 1}}))
    assert d["mode"] == "complete_pair" and d["cell_index"] == 0 and d["mate_cell"] == 1, d

    # Solver: an unknown cell is selected when no pair exists.
    d = ts_solver.choose_cell(make_ts_snapshot(selectable=(0, 1, 2, 3)),
                              make_ts_knowledge())
    assert d["mode"] == "explore" and d["cell_index"] == 0, d

    # Solver: matched cells are excluded from a known mate.
    d = ts_solver.choose_cell(
        make_ts_snapshot(open_cells=(2,), matched=(3,), selectable=(0, 1),
                         visible={2: 9}),
        make_ts_knowledge(known={2: 9, 3: 9}, unmatched={9: {2, 3}}))
    assert d["mode"] == "explore" and d["cell_index"] == 0, d

    # Solver: waits for non-playing, busy, awaiting, and two-open states.
    assert ts_solver.choose_cell(make_ts_snapshot(state="idle"),
                                 make_ts_knowledge())["mode"] == "wait"
    assert ts_solver.choose_cell(make_ts_snapshot(busy=True),
                                 make_ts_knowledge())["reason"] == "client busy"
    assert ts_solver.choose_cell(make_ts_snapshot(awaiting=True),
                                 make_ts_knowledge())["reason"] == "client busy"
    assert ts_solver.choose_cell(make_ts_snapshot(open_cells=(0, 1)),
                                 make_ts_knowledge())["reason"] == "two cards resolving"

    # Solver: deterministic tie-break chooses the lowest first cell.
    d = ts_solver.choose_cell(
        make_ts_snapshot(selectable=(0, 1, 2, 3)),
        make_ts_knowledge(known={0: 3, 2: 3, 1: 4, 3: 4},
                          unmatched={3: {0, 2}, 4: {1, 3}}))
    assert d["cell_index"] == 0 and d["face"] == 3, d

    # Solver: no legal cell returns a wait, not an invalid index.
    d = ts_solver.choose_cell(make_ts_snapshot(selectable=(), matched=(0, 1, 2, 3)),
                              make_ts_knowledge())
    assert d["mode"] == "wait" and d["cell_index"] is None, d

    # Card enumeration: list and dict shapes normalize identically.
    class MCard:
        def __init__(self, index, face=0, matched=False, busy=False):
            self.index = index
            self.face = face
            self.matched = matched
            self._busy = busy
        def IsBusy(self):
            return self._busy

    pairs, ok, _reason = enumerate_memory_cards([MCard(0), MCard(1), MCard(2)])
    assert ok and [i for i, _ in pairs] == [0, 1, 2], pairs
    pairs, ok, _reason = enumerate_memory_cards({2: MCard(2), 0: MCard(0), 1: MCard(1)})
    assert ok and [i for i, _ in pairs] == [0, 1, 2], pairs
    pairs, ok, reason = enumerate_memory_cards([MCard(0), MCard(0)])
    assert not ok and "duplicate" in reason, reason
    pairs, ok, reason = enumerate_memory_cards("not cards")
    assert not ok, reason

    # Face normalization preserves a zero face and only accepts visible faces.
    assert normalize_memory_face(0, True) == 0
    assert normalize_memory_face(7, True) == 7
    assert normalize_memory_face(0, False) is None
    assert normalize_memory_face("x", True) is None

    # State classification treats unverified numeric states as unknown.
    assert classify_memory_state(None) == "unknown"
    assert classify_memory_state("playing") == "playing"
    assert classify_memory_state(2) == "unknown"
    assert classify_memory_state("idle") == "idle"

    # Minigame arbitration: active owner keeps the slot; an enabled duel claims
    # the slot only while it is actively playing or idle-but-startable.
    assert resolve_minigame_owner(True, True, False, False, False) == "duel"
    assert resolve_minigame_owner(False, False, False, True, True) == "twin_souls"
    # Both enabled, neither owning: the duel is idle-but-startable, so it wins.
    assert resolve_minigame_owner(True, False, True, True, False) == "duel"
    # Both enabled, neither owning, duel on cooldown / at limit: Twin Souls wins.
    assert resolve_minigame_owner(True, False, False, True, False) == "twin_souls"
    assert resolve_minigame_owner(False, False, False, True, False) == "twin_souls"
    assert resolve_minigame_owner(False, False, False, False, False) is None
    # duel_enabled alone never claims the slot when the duel cannot act.
    assert resolve_minigame_owner(True, False, False, False, False) is None

    # Duel slot arbitration helpers (`_DuelOwnsSlot` / `_DuelStartable`) and the
    # result-screen dismissal (`_DuelCloseResult`).
    class FakeDuelWindow:
        def __init__(self, state=0, used=0, maximum=8, cooldown=0.0):
            self.state = state
            self.duelsUsedHwid = used
            self.duelsMaxHwid = maximum
            self._cooldown = cooldown
        def GetCooldownRemaining(self):
            return self._cooldown

    duel_original_find = panel.FindRuntimeObject
    duel_window = FakeDuelWindow()
    panel.FindRuntimeObject = lambda name, methods: (
        duel_window if name == "YinYangDuelWindow" else None)
    panel.yinyang_duel_enabled = True

    duel_window.state = 2
    assert panel._DuelOwnsSlot() is True
    duel_window.state = 0
    assert panel._DuelOwnsSlot() is False

    assert panel._DuelStartable() is True
    duel_window.duelsUsedHwid = 8
    duel_window.duelsMaxHwid = 8
    assert panel._DuelStartable() is False  # at daily limit
    duel_window.duelsUsedHwid = 0
    duel_window._cooldown = 30.0
    assert panel._DuelStartable() is False  # on cooldown
    duel_window._cooldown = 0.0
    duel_window.state = 2
    assert panel._DuelStartable() is False  # not idle
    duel_window.state = 0
    panel.yinyang_duel_enabled = False
    assert panel._DuelStartable() is False  # disabled
    assert panel._DuelOwnsSlot() is False
    panel.yinyang_duel_enabled = True

    # `_DuelCloseResult` dismisses via the known handler, a discovered member,
    # or the Close() fallback.
    dismissed = []
    duel_window._YinYangDuelWindow__OnResultContinue = (
        lambda: dismissed.append("continue"))
    assert panel._DuelCloseResult(duel_window) is True
    assert dismissed == ["continue"]
    assert "result dismissed" in panel.yinyang_duel_label.text

    dismissed[:] = []
    del duel_window._YinYangDuelWindow__OnResultContinue
    duel_window._YinYangDuelWindow__OnResultClicked = (
        lambda: dismissed.append("discovered"))
    assert panel._DuelCloseResult(duel_window) is True
    assert dismissed == ["discovered"]

    dismissed[:] = []
    del duel_window._YinYangDuelWindow__OnResultClicked
    duel_window.Close = lambda: dismissed.append("closed")
    assert panel._DuelCloseResult(duel_window) is True
    assert dismissed == ["closed"]
    assert "closed" in panel.yinyang_duel_label.text

    # No handler and no Close -> the result screen is left alone (returns False).
    del duel_window.Close
    assert panel._DuelCloseResult(duel_window) is False

    panel.FindRuntimeObject = duel_original_find
    panel.yinyang_duel_enabled = False

    class FakeMemoryWindow:
        def __init__(self, cards=None):
            self.state = "playing"
            self.phase = None
            self.cards = cards if cards is not None else []
            self.openCells = []
            self.faceCount = 0
            self.pairsFound = 0
            self.awaitingFlip = False
            self.playsUsed = 0
            self.playsMax = 5
            self.playsUsedHwid = 0
            self.playsMaxHwid = 10
            self.timeLeftSec = 30.0
        def GetTimeRemaining(self):
            return self.timeLeftSec
        def GetCooldownRemaining(self):
            return 0.0
        def GetBonusRemaining(self):
            return 0.0

    def ts_window(card_specs, open_cells=(), pairs_found=0):
        window = FakeMemoryWindow([MCard(i, f, m) for i, f, m in card_specs])
        window.faceCount = len(card_specs) // 2
        window.pairsFound = pairs_found
        window.openCells = list(open_cells)
        return window

    # Tracker: a revealed face is learned from authoritative state.
    mt = MemoryBoardTracker()
    w = ts_window([(0, 7, False), (1, 0, False), (2, 8, False), (3, 0, False)],
                  open_cells=(0,))
    snap, err = mt.observe(w, 1.0)
    assert err is None and snap.visible_faces == {0: 7}, (snap.visible_faces, err)
    assert mt.known_face_by_cell.get(0) == 7

    # Tracker: mismatch faces remain known after the cards close.
    w.openCells = [0, 2]
    w.cards[0].face = 7
    w.cards[2].face = 8
    snap, err = mt.observe(w, 2.0)
    assert snap.visible_faces == {0: 7, 2: 8}
    w.openCells = []
    w.cards[0].face = 0
    w.cards[2].face = 0
    snap, err = mt.observe(w, 3.0)
    assert snap.visible_faces == {}
    assert mt.known_face_by_cell.get(0) == 7
    assert mt.known_face_by_cell.get(2) == 8

    # Tracker: matched cells leave the unmatched index.
    mt2 = MemoryBoardTracker()
    w = ts_window([(0, 7, False), (1, 7, False), (2, 8, False), (3, 8, False)],
                  open_cells=(0, 1))
    mt2.observe(w, 1.0)
    assert mt2.known_cells_by_face.get(7) == {0, 1}
    w.cards[0].matched = True
    w.cards[1].matched = True
    w.openCells = []
    mt2.observe(w, 2.0)
    assert not mt2.known_cells_by_face.get(7)

    # Tracker: a new window clears all old knowledge.
    mt3 = MemoryBoardTracker()
    w = ts_window([(0, 7, False), (1, 0, False)], open_cells=(0,))
    mt3.observe(w, 1.0)
    assert mt3.known_face_by_cell.get(0) == 7
    board_before = mt3.board_id
    w2 = ts_window([(0, 9, False), (1, 0, False)], open_cells=(0,))
    mt3.observe(w2, 2.0)
    assert mt3.board_id == board_before + 1
    assert mt3.known_face_by_cell == {0: 9}

    # Tracker: a within-window board reset (pairsFound back to zero) clears.
    mt4 = MemoryBoardTracker()
    w = ts_window([(0, 7, False), (1, 7, False), (2, 8, False), (3, 8, False)],
                  open_cells=(0, 1), pairs_found=1)
    w.cards[0].matched = True
    w.cards[1].matched = True
    mt4.observe(w, 1.0)
    assert mt4.known_face_by_cell.get(0) == 7
    board_before = mt4.board_id
    w.pairsFound = 0
    w.cards[0].matched = False
    w.cards[1].matched = False
    w.cards[0].face = 0
    w.cards[1].face = 0
    w.openCells = []
    mt4.observe(w, 2.0)
    assert mt4.board_id == board_before + 1
    assert mt4.known_face_by_cell == {}

    # Tracker: a contradictory face mutation inside one board is rejected.
    mt5 = MemoryBoardTracker()
    w = ts_window([(0, 7, False), (1, 0, False)], open_cells=(0,))
    mt5.observe(w, 1.0)
    w.cards[0].face = 8
    mt5.observe(w, 2.0)
    assert mt5.known_face_by_cell.get(0) == 7
    assert mt5.last_error is not None

    # Tracker: list and dictionary card collections normalize consistently.
    mt_list = MemoryBoardTracker()
    mt_dict = MemoryBoardTracker()
    cards = [(0, 7, False), (1, 0, False), (2, 8, False), (3, 0, False)]
    w_list = ts_window(cards, open_cells=(0,))
    w_dict = FakeMemoryWindow({i: MCard(i, f, m) for i, f, m in cards})
    w_dict.faceCount = 2
    w_dict.openCells = [0]
    s_list, _ = mt_list.observe(w_list, 1.0)
    s_dict, _ = mt_dict.observe(w_dict, 1.0)
    assert s_list.visible_faces == s_dict.visible_faces == {0: 7}
    assert s_list.selectable_cells == s_dict.selectable_cells

    # Tracker: pending flip clears only on authoritative progress.
    mt6 = MemoryBoardTracker()
    w = ts_window([(0, 7, False), (1, 0, False)], open_cells=())
    snap, _ = mt6.observe(w, 1.0)
    mt6.mark_pending_flip(0, snap)
    assert mt6.has_pending_flip()
    w.openCells = []
    snap2, _ = mt6.observe(w, 2.0)
    assert mt6.resolve_pending_flip(snap2, 2.0) is False
    assert mt6.has_pending_flip()
    w.openCells = [0]
    snap3, _ = mt6.observe(w, 3.0)
    assert mt6.resolve_pending_flip(snap3, 3.0) is True
    assert not mt6.has_pending_flip()

    # Controller lifecycle (observation only; no dispatch without the adapter).
    controller_window = FakeMemoryWindow(
        [MCard(0, 7, False), MCard(1, 0, False), MCard(2, 8, False), MCard(3, 0, False)])
    controller_window.faceCount = 2
    original_find = panel.FindRuntimeObject
    panel.FindRuntimeObject = lambda name, methods: (
        controller_window if name == "YinYangMemoryWindow" else None)

    def reset_ts_controller():
        panel.twin_souls_enabled = True
        panel.twin_souls_next_poll = 0.0
        panel.twin_souls_discover_at = 0.0
        panel.twin_souls_window = None
        panel.twin_souls_last_state = None
        panel.twin_souls_last_board = None
        panel.twin_souls_last_finished_board = None
        panel.twin_souls_tracker = MemoryBoardTracker()
        panel.twin_souls_adapter = MemoryActionAdapter()
        panel.boss_enabled = False
        panel.yinyang_duel_enabled = False

    # Uninitialized limits prevent automatic spending.
    reset_ts_controller()
    controller_window.state = "idle"
    controller_window.playsMax = 0
    controller_window.playsMaxHwid = 0
    controller_window.playsUsed = 0
    controller_window.playsUsedHwid = 0
    controller_window.openCells = []
    controller_window.GetCooldownRemaining = lambda: 0.0
    panel.PollTwinSouls(10.0)
    assert "waiting for limits/state" in panel.twin_souls_label.text, panel.twin_souls_label.text

    # An initialized daily limit disables the mode.
    controller_window.playsMax = 2
    controller_window.playsUsed = 2
    controller_window.playsMaxHwid = 10
    controller_window.playsUsedHwid = 0
    reset_ts_controller()
    panel.PollTwinSouls(11.0)
    assert not panel.twin_souls_enabled
    assert "daily limit 2/2" in panel.twin_souls_label.text, panel.twin_souls_label.text

    # Cooldown blocks start.
    controller_window.playsMax = 5
    controller_window.playsUsed = 0
    reset_ts_controller()
    controller_window.GetCooldownRemaining = lambda: 42.0
    panel.PollTwinSouls(12.0)
    assert "cooldown 42s" in panel.twin_souls_label.text, panel.twin_souls_label.text
    controller_window.GetCooldownRemaining = lambda: 0.0

    # The unverified adapter issues no start (no pending, no dispatch).
    reset_ts_controller()
    assert not panel.twin_souls_adapter.is_verified()
    panel.PollTwinSouls(13.0)
    assert "waiting for verified background input" in panel.twin_souls_label.text, \
        panel.twin_souls_label.text
    assert not panel.twin_souls_tracker.has_pending_start()

    # A verified adapter marks exactly one pending start for an idle board.
    class VerifiedAdapter:
        def is_verified(self):
            return True
    reset_ts_controller()
    panel.twin_souls_adapter = VerifiedAdapter()
    panel.PollTwinSouls(14.0)
    assert panel.twin_souls_tracker.has_pending_start()

    # openPending suppresses a duplicate start.
    controller_window.openPending = True
    panel.twin_souls_tracker.pending_start = False
    panel.twin_souls_next_poll = 0.0
    panel.twin_souls_window = None
    panel.PollTwinSouls(15.0)
    assert "start pending" in panel.twin_souls_label.text, panel.twin_souls_label.text
    assert not panel.twin_souls_tracker.has_pending_start()
    controller_window.openPending = False

    # A finishing board never starts and performs no solver action.
    controller_window.state = "finishing"
    reset_ts_controller()
    panel.twin_souls_adapter = VerifiedAdapter()
    panel.PollTwinSouls(16.0)
    assert "finished" in panel.twin_souls_label.text, panel.twin_souls_label.text
    assert not panel.twin_souls_tracker.has_pending_start()

    # An active playing board is solved and recorded, but not dispatched.
    controller_window.state = "playing"
    controller_window.openCells = [0]
    reset_ts_controller()
    panel.PollTwinSouls(17.0)
    assert "background input unverified" in panel.twin_souls_label.text, \
        panel.twin_souls_label.text

    # Disable clears pending state and board memory.
    panel.twin_souls_enabled = True
    panel.twin_souls_tracker.mark_pending_start()
    panel.twin_souls_tracker.mark_pending_flip(0, snap)
    panel.ToggleTwinSouls()
    assert not panel.twin_souls_enabled
    assert not panel.twin_souls_tracker.has_pending_start()
    assert panel.twin_souls_tracker.pending_flip is None

    panel.FindRuntimeObject = original_find

    # NativeActionCoordinator: explicit state machine with phase + deadline.
    NativeActionCoordinator = duel_globals["NativeActionCoordinator"]
    phase_box = [5]
    clock_box = [1000.0]

    def coord_phase():
        return phase_box[0]

    def coord_clock():
        return clock_box[0]

    coord = NativeActionCoordinator(coord_phase, coord_clock)
    # Normal flow to completed.
    aid = coord.request("queue_add", 10, 2.0)
    assert coord.state(aid) == NativeActionCoordinator.REQUESTED
    assert coord.validate(aid, True) == NativeActionCoordinator.VALIDATED
    assert coord.dispatch(aid) == NativeActionCoordinator.AWAITING
    assert (coord.acknowledge(aid, NativeActionCoordinator.COMPLETED) ==
            NativeActionCoordinator.COMPLETED)
    assert not coord.has_pending()
    # Validation failure rejects.
    aid2 = coord.request("queue_add", 0, 2.0)
    assert coord.validate(aid2, False) == NativeActionCoordinator.REJECTED
    # Deadline expiry becomes unknown.
    aid3 = coord.request("queue_add", 11, 2.0)
    coord.validate(aid3, True)
    coord.dispatch(aid3)
    assert coord.has_pending()
    clock_box[0] += 10.0
    coord.poll()
    assert coord.state(aid3) == NativeActionCoordinator.UNKNOWN
    assert not coord.has_pending()
    # Phase change cancels a pending action.
    aid4 = coord.request("queue_add", 12, 2.0)
    coord.validate(aid4, True)
    coord.dispatch(aid4)
    phase_box[0] = 4
    coord.on_phase_change()
    assert coord.state(aid4) == NativeActionCoordinator.CANCELLED
    # Explicit cancel and unknown acknowledgement.
    aid5 = coord.request("ui_click", "card", 2.0)
    coord.validate(aid5, True)
    assert coord.cancel(aid5, "manual") == NativeActionCoordinator.CANCELLED
    aid6 = coord.request("queue_add", 13, 2.0)
    coord.validate(aid6, True)
    coord.dispatch(aid6)
    assert (coord.acknowledge(aid6, NativeActionCoordinator.UNKNOWN) ==
            NativeActionCoordinator.UNKNOWN)
print("Local map, safe hunter queue, boss flow, config persistence, reaction, hotkey, and gameplay-exit guard: OK")
