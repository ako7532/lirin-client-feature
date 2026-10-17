"""Offline policy integration: actual selector/controller/gateway, fake client.

No game process, native input, injection or network access.
"""
import ast
import math
from pathlib import Path
import random
import unittest

from test_hunter_recorder_pair import Observer, Pair, Player

source = Path(__file__).with_name("client_feature.py")
tree = ast.parse(source.read_text(encoding="ascii"), str(source))
names = {"HunterQueueGateway", "HunterCandidateSelector", "HunterController",
         "ManualQueueRefillProfile"}
tree.body = [node for node in tree.body if getattr(node, "name", None) in names]
namespace = {"math": math, "random": random, "ascii_text": str,
             "hunter_now_ms": lambda: 1000,
             "PRIORITY_EVENT_METIN_NAME": "legendary metinstone"}
exec(compile(tree, str(source), "exec"), namespace)
Gateway = namespace["HunterQueueGateway"]
Controller = namespace["HunterController"]
Selector = namespace["HunterCandidateSelector"]


class QueueObserver(Observer):
    def __init__(self):
        super().__init__()
        self.enabled = False

    def snapshot(self):
        result = super().snapshot()
        result["enabled"] = self.enabled
        return result


class QueuePlayer(Player):
    def MetinQueueSetEnabled(self, enabled):
        self.observer.enabled = bool(enabled)
        if not enabled:
            self.observer.vids[:] = []

    def GetMainCharacterPosition(self):
        return (0, 0, 0)


class Actors:
    def __init__(self):
        self.positions = {1: (100, 0, 0), 2: (0, 200, 0),
                          3: (-300, 0, 0), 4: (0, -400, 0)}

    def GetVirtualNumber(self, vid):
        return 8014

    def GetNameByVID(self, vid):
        return "Metin"

    def GetPixelPosition(self, vid):
        return self.positions[vid]

    def IsStone(self, vid):
        return vid in self.positions

    def IsMonsterStone(self, vnum):
        return vnum == 8014


class Profile:
    def __init__(self):
        self.wait_samples = 0

    def refill_start_delay_ms(self):
        self.wait_samples += 1
        return 5000

    def burst_add_delay_ms(self):
        return 100

    def sweep_direction(self):
        return -1


class AvailableRefillTests(unittest.TestCase):
    def setUp(self):
        self.clock = [1000]
        self.events = []
        self.observer = QueueObserver()
        self.player = QueuePlayer(self.observer, self.events)
        self.pair = Pair(self.events)
        self.gateway = Gateway(self.observer, self.player,
                               clock=lambda: self.clock[0],
                               recorder_pair_enabled=True, recorder_pair=self.pair)
        self.actors = Actors()
        self.selector = Selector(self.player, self.actors, self.actors)
        self.profile = Profile()
        self.logs = []
        self.controller = Controller(
            self.gateway, self.selector, lambda: self.clock[0], lambda: True,
            refill_profile=self.profile, log=self.logs.append,
            radius_getter=lambda: 2500, anchor_getter=lambda: (0, 0))
        self.assertEqual(self.controller.start(), Controller.RUNNING)

    def tick(self, now, refresh=True):
        self.clock[0] = now
        if refresh:
            self.controller.on_scan(self.selector.publish(
                self.actors.positions, (0, 0), (0, 0), 2500,
                self.controller.epoch, now))
        return self.controller.tick(now)

    def fill_four(self):
        for now in (1000, 1100, 1200, 1300):
            self.tick(now)
        self.assertEqual(self.observer.vids, [1, 4, 3, 2])
        self.tick(1400)
        self.assertFalse(self.controller.refill_burst_active)
        self.assertEqual(self.controller.refill_completed_count, 4)

    def depart(self, vid):
        self.observer.vids.remove(vid)
        self.actors.positions.pop(vid)

    def test_partial_fill_waits_for_departure_then_fixed_manual_deadline(self):
        self.fill_four()
        self.assertEqual(self.profile.wait_samples, 0)
        self.actors.positions[5] = (500, 0, 0)
        self.tick(1500)
        self.assertEqual(len(self.events), 12)  # respawn alone does not reopen burst
        self.depart(1)
        self.tick(1600)
        self.assertEqual(self.controller.refill_due_ms, 6600)
        self.depart(4)
        self.tick(1700)
        self.tick(6599)
        self.assertEqual(self.profile.wait_samples, 1)
        self.assertEqual(self.controller.refill_due_ms, 6600)
        self.assertEqual(len(self.events), 12)
        self.tick(6600)
        self.assertEqual(self.events[-3:], [("down", 5), ("add", 5), ("up", 5)])

    def test_circular_selection_and_one_recorder_pair_per_add_are_retained(self):
        self.fill_four()
        expected = [(kind, vid) for vid in (1, 4, 3, 2)
                    for kind in ("down", "add", "up")]
        self.assertEqual(self.events, expected)
        self.assertTrue(any("burst complete: no eligible candidate" in s for s in self.logs))

    def test_any_available_count_completes_without_lowering_next_burst_capacity(self):
        for count in (1, 2, 3, 4):
            with self.subTest(count=count):
                self.setUp()
                self.actors.positions = {vid: (vid * 100, 0, 0)
                                         for vid in range(1, count + 1)}
                for index in range(count + 1):
                    self.tick(1000 + index * 100)
                self.assertEqual(len(self.observer.vids), count)
                self.assertEqual(self.controller.refill_completed_count, count)
                # Newly available targets do not reopen a completed burst.
                self.actors.positions.update({vid: (vid * 100, 0, 0)
                                              for vid in range(1, 7)})
                self.tick(1600)
                self.assertEqual(len(self.observer.vids), count)
                self.depart(1)
                self.tick(1700)
                self.assertEqual(self.controller.refill_due_ms, 6700)
                for now in range(6700, 7300, 100):
                    self.tick(now)
                self.assertEqual(len(self.observer.vids), 5)
                self.assertEqual(self.controller.refill_completed_count, 5)

    def test_full_five_still_waits_for_first_vacancy(self):
        self.actors.positions[5] = (500, 0, 0)
        for now in (1000, 1100, 1200, 1300, 1400):
            self.tick(now)
        self.assertEqual(len(self.observer.vids), 5)
        self.assertEqual(self.controller.refill_completed_count, 5)
        self.tick(1500)
        self.assertEqual(self.profile.wait_samples, 0)
        self.depart(1)
        self.tick(1600)
        self.assertEqual(self.controller.refill_due_ms, 6600)

    def test_empty_exhausted_queue_schedules_wait_and_can_fill_later(self):
        self.actors.positions.clear()
        self.tick(1000)
        self.assertEqual(self.controller.refill_completed_count, 0)
        self.tick(1100)
        self.assertEqual(self.controller.refill_due_ms, 6100)
        self.actors.positions[5] = (500, 0, 0)
        self.tick(6000)
        self.assertEqual(self.events, [])
        self.tick(6100)
        self.assertEqual(self.events, [("down", 5), ("add", 5), ("up", 5)])

    def test_unavailable_scans_do_not_complete_burst(self):
        for now in (1000, 1100, 1200, 1300):
            self.tick(now)
        for created in (None, -1000, 9999):
            self.controller.last_scan["created_ms"] = created
            self.tick(1400, refresh=False)
            self.assertTrue(self.controller.refill_burst_active)
            self.assertIsNone(self.controller.refill_completed_count)
        self.controller.last_scan["epoch"] = -1
        self.tick(1500, refresh=False)
        self.assertTrue(self.controller.refill_burst_active)

    def test_unknown_dispatch_is_reconciled_without_new_pair_or_completion(self):
        self.player.truthy_no_insert = True
        self.tick(1000)
        pending = self.controller.pending_request
        self.assertIsNotNone(pending)
        self.actors.positions.clear()
        self.tick(1200)
        self.assertIs(self.controller.pending_request, pending)
        self.assertTrue(self.controller.refill_burst_active)
        self.assertIsNone(self.controller.refill_completed_count)
        self.assertEqual(self.events, [("down", 1), ("add", 1), ("up", 1)])

    def test_recorder_fault_still_halts_before_new_fill_policy(self):
        self.pair.end_status = -3
        self.tick(1000)
        self.assertEqual(self.tick(1100), Controller.ERROR)
        self.assertEqual(self.events, [("down", 1), ("add", 1), ("up", 1)])
        self.assertIsNone(self.controller.refill_completed_count)

    def test_disabled_recorder_keeps_stock_additions_without_up(self):
        self.pair.begin_status = 0
        self.fill_four()
        self.assertEqual(self.events, [(kind, vid) for vid in (1, 4, 3, 2)
                                       for kind in ("down", "add")])

    def test_stop_and_restart_reset_partial_fill_baseline(self):
        self.fill_four()
        self.assertEqual(self.controller.stop(), Controller.OFF)
        self.assertEqual(self.observer.vids, [])
        self.assertEqual(self.controller.start(), Controller.RUNNING)
        self.assertIsNone(self.controller.refill_completed_count)
        self.tick(1500)
        self.assertEqual(len(self.observer.vids), 1)

    def test_session_change_discards_partial_fill_baseline(self):
        self.fill_four()
        self.controller.on_session_change("test session change")
        self.assertIsNone(self.controller.refill_completed_count)
        self.assertIsNone(self.controller.refill_due_ms)
        self.assertFalse(self.controller.refill_burst_active)


if __name__ == "__main__":
    unittest.main()
