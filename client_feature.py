"""In-game metin radius scanner for Lirin's embedded Python 2.7 runtime."""

import __main__
import gc
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
FEATURE_VERSION = 38
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
BOSS_KILL_CONFIRM_SECONDS = 1.5
BOSS_COMBAT_TIMEOUT_SECONDS = 90.0
BOSS_CHANNEL_TIMEOUT_SECONDS = 35.0
BOSS_RETURN_DISTANCE = 120
BOSS_RETURN_STALL_SECONDS = 3.0
BOSS_RETURN_PROGRESS_DISTANCE = 25

BOSS_IDLE = "idle"
BOSS_WAIT_TIMER = "wait_timer"
BOSS_FIND = "find"
BOSS_ATTACK = "attack"
BOSS_CHANGE_CHANNEL = "change_channel"
BOSS_WAIT_CHANNEL = "wait_channel"
BOSS_SETTLE_CHANNEL = "settle_channel"
BOSS_RETURN_POSITION = "return_position"

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
        self.SetSize(820, 485)
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
        self.player_next_poll = 0.0
        self.last_player_position = None
        self.gameplay_phase = None
        self.gameplay_available = True
        self.gameplay_next_check = 0.0
        self.gameplay_stopped = False
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
        player.MetinQueueAdd(vid)
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
                    self.BeginBossSweep()
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
        result = player.MetinQueueAdd(vid)
        add_elapsed_ms = (time.time() - add_started) * 1000.0
        new_size = int(player.MetinQueueGetSize())
        if new_size > size:
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
        if not result:
            self.AddLine("Queue rejected VID %d, queue %d->%d, call %.2fms" %
                         (vid, old_size, new_size, add_elapsed_ms))
        else:
            self.AddLine("Queue accepted VID %d without size change, queue %d->%d, call %.2fms; no retry" %
                         (vid, old_size, new_size, add_elapsed_ms))
            self.hunter_queued_vids.add(vid)
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
            player.MetinQueueAdd(vid)
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
