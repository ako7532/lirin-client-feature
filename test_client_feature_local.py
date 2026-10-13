"""Exercise the Python 2 feature logic with fake client UI and entity modules."""

import builtins
import os
import re
import sys
import tempfile
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
net.GetChannelNumber = lambda: channel_state["current"]
net.SetChannelNumber = lambda channel: channel_state.__setitem__("current", int(channel))
sys.modules["net"] = net

chr_module = types.ModuleType("chr")
chr_module.GetVirtualNumber = lambda vid: {1: 8003, 2: 8004, 3: 100, 10: 2493}[vid]
chr_module.GetPixelPosition = lambda vid: {
    1: (300, 400, 0), 2: (1200, 0, 0), 3: (100, 0, 0), 10: (2100, 0, 0)
}[vid]
chr_module.GetNameByVID = lambda vid: {
    1: "Battle Metin", 2: "Jealousy Metin", 3: "Wolf", 10: "Test Boss"
}[vid]
move_requests = []
chr_module.MoveToDestPosition = lambda vid, x, y: move_requests.append((vid, x, y))
sys.modules["chr"] = chr_module

nonplayer = types.ModuleType("nonplayer")
nonplayer.IsMonsterStone = lambda vnum: vnum in (8003, 8004)
sys.modules["nonplayer"] = nonplayer

player = types.ModuleType("player")
player_position = [0, 0, 0]
player.GetMainCharacterPosition = lambda: tuple(player_position)
queue = []
queue_state = {"enabled": False, "max_size": 5}
allowed_queue_races = set()
player.MetinQueueIsEnabled = lambda: queue_state["enabled"]
player.MetinQueueSetEnabled = lambda enabled: queue_state.__setitem__("enabled", bool(enabled))
player.MetinQueueGetSize = lambda: len(queue)
player.MetinQueueGetMaxSize = lambda: queue_state["max_size"]
def add_metin(vid):
    if vid in queue:
        return True
    if len(queue) >= queue_state["max_size"]:
        return False
    queue.append(vid)
    return True
player.MetinQueueAdd = add_metin
player.MetinQueueClear = lambda: queue.__setitem__(slice(None), [])
player.AddMetinQueueAllowedRace = lambda vnum: allowed_queue_races.add(int(vnum))
target_state = {"vid": 0, "attack": False, "mouse": 17}
player.GetTargetVID = lambda: target_state["vid"]
player.SetTarget = lambda vid: target_state.__setitem__("vid", int(vid))
player.ClearTarget = lambda: target_state.__setitem__("vid", 0)
player.SetAttackKeyState = lambda enabled: target_state.__setitem__("attack", bool(enabled))
player.GetMouseFunc = lambda button: target_state["mouse"]
player.SetMouseFunc = lambda button, function: target_state.__setitem__("mouse", function)
player.GetMainCharacterIndex = lambda: 999
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

source_path = Path(__file__).with_name("client_feature.py")
source = source_path.read_text(encoding="ascii")
with tempfile.TemporaryDirectory() as directory:
    source = re.sub(r"^DIRECTORY = .*$", lambda match: "DIRECTORY = %r" % directory,
                    source, flags=re.M)
    exec(compile(source, str(source_path), "exec"), {"__name__": "__main__"})
    panel = sys.modules["__main__"]._lirin_metin_scanner
    original_find_runtime = panel.FindRuntimeObject
    disabled_discovery_calls = []
    panel.reaction_enabled = False
    panel.FindRuntimeObject = lambda name, methods: disabled_discovery_calls.append(name)
    assert not panel.PollReactionGame(9.0)
    assert disabled_discovery_calls == []
    panel.reaction_enabled = True
    panel.reaction_next_poll = 0.0
    panel.FindRuntimeObject = lambda name, methods: (
        reaction_window if name == "ReactionGameWindow"
        else original_find_runtime(name, methods)
    )
    reaction_window.visible = True
    assert panel.PollReactionGame(10.0)
    assert reaction_window.start_count == 1
    panel.reaction_next_poll = 0.0
    assert panel.PollReactionGame(10.1)
    assert reaction_window.clicked == [2]
    panel.reaction_next_poll = 0.0
    panel.PollReactionGame(10.2)
    assert reaction_window.clicked == [2]
    reaction_window.lastBallMoveTime = 2.0
    panel.reaction_next_poll = 0.0
    panel.PollReactionGame(10.3)
    assert reaction_window.clicked == [2, 2]
    panel.boss_enabled = True
    panel.boss_state_started = 5.0
    panel.boss_deadline = 20.0
    reaction_window.visible = False
    panel.reaction_next_poll = 0.0
    assert not panel.PollReactionGame(10.4)
    assert panel.reaction_window is reaction_window
    panel.ResumeAfterReaction(10.4)
    assert panel.reaction_pause_started is None
    assert round(panel.boss_deadline, 1) == 20.4
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
    panel.ToggleMetinHunter()
    assert panel.hunter_enabled and queue_state["enabled"]
    panel.next_scan = 0
    panel.OnUpdate()
    assert queue == [1], queue
    panel.next_scan = 0
    panel.OnUpdate()
    assert queue == [1, 2], queue
    panel.ToggleMetinHunter()
    assert not panel.hunter_enabled and queue == [1, 2]
    queue[:] = [90, 91, 92, 93]
    panel.ToggleMetinHunter()
    panel.next_scan = 0
    panel.OnUpdate()
    assert len(queue) == 5 and queue[-1] == 1, queue
    panel.next_scan = 0
    panel.OnUpdate()
    assert len(queue) == 5, queue
    panel.ToggleMetinHunter()
    queue[:] = [90, 91, 92]
    queue_state["max_size"] = 3
    panel.ToggleMetinHunter()
    panel.next_scan = 0
    panel.OnUpdate()
    assert len(queue) == 3 and "3/3" in panel.hunter_label.text, queue
    panel.ToggleMetinHunter()
    queue[:] = []
    queue_state["max_size"] = 5
    panel.radius_edit.SetText("1000")
    panel.OnUpdate()
    panel.ToggleAnchor()
    assert panel.anchor_position == (0, 0)
    player_position[0] = 2000
    panel.ToggleMetinHunter()
    panel.next_scan = 0
    panel.player_next_poll = 0
    panel.watcher.OnUpdate()
    assert queue == [1], queue
    assert not panel.map_player.visible
    panel.ToggleAnchor()
    assert panel.anchor_position is None
    panel.next_scan = 0
    panel.player_next_poll = 0
    panel.watcher.OnUpdate()
    assert queue == [1, 2], queue
    assert panel.map_player.visible

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

    target_state["vid"] = 10
    panel.MarkBoss()
    assert panel.boss_vnum == 2493
    assert panel.anchor_position == (2000, 0)
    assert panel.anchor_channel == 1
    assert "timer=yes hp=yes channels=3" in log_path.read_text(encoding="ascii")
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
    boss_update()
    assert panel.boss_state == "wait_hp", panel.boss_state
    target_board.SetHP(100, 1000, 1000)
    boss_update()
    assert panel.boss_state == "attack", panel.boss_state
    assert not target_state["attack"]
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
    panel.AdvanceBossChannel()
    assert channel_state["current"] == 1
    Path(directory, "client_feature_vids.txt").write_text(
        "PID %d\n" % os.getpid(), encoding="ascii"
    )
    boss_update()
    panel.boss_deadline = 0.0
    boss_update()
    boss_update()
    assert panel.boss_state == "wait_timer", panel.boss_state
    assert panel.boss_enabled and panel.hunter_enabled and queue_state["enabled"]
    assert not target_state["attack"]
    assert target_state["mouse"] == 17
    panel.ToggleBossSweep()
    assert not panel.boss_enabled and queue_state["enabled"]

    Path(directory, "client_feature_vids.txt").write_text(
        "PID %d\n1\n2\n" % os.getpid(), encoding="ascii"
    )
    panel.radius_edit.SetText("2000")
    panel.next_scan = 0
    panel.OnUpdate()
    panel.next_scan = 0
    panel.OnUpdate()
    assert queue == [2, 1], queue
    panel.Stop()
    assert not panel.running
    assert not panel.hunter_enabled and queue == [2, 1]
    assert not panel.map_metins[0].visible
    assert all(dot.visible for dot in panel.map_ring)
print("Local map, hunter, boss HP gate/channel timing/return, reaction clicks, hidden scanner, Ctrl+F8, and log: OK")
