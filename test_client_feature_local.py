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
def add_metin(vid):
    if vid == 0:
        # The native wrapper's bare-click sentinel (emit_synthetic_click): no
        # queue change, mirrors the real VID-0 click-only path.
        return True
    if vid in queue:
        return True
    if len(queue) >= queue_state["max_size"]:
        return False
    queue.append(vid)
    return True
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
    # Hunter admission no longer depends on screen projection or camera motion;
    # the native wrapper now routes the target through the mouse-state path.
    panel.hunter_next_add = 0
    panel.FeedMetinQueue([(1400, 7, "Jealousy Metin")])
    assert queue == [7]
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
    player.MetinQueueAdd = lambda vid: False
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
print("Local map, safe hunter queue, boss flow, config persistence, reaction, hotkey, and gameplay-exit guard: OK")
