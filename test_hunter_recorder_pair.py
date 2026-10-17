"""Offline tests of the real gateway/controller, using fake native boundaries.

No game process, native producer invocation or network access.
"""
import ast
from pathlib import Path
import tempfile
import unittest

SOURCE = Path(__file__).with_name("client_feature.py")
NAMES = {"HunterQueueGateway", "HunterController", "ManualQueueRefillProfile",
         "recorder_pair_experiment_enabled"}
tree = ast.parse(SOURCE.read_text(encoding="ascii"), str(SOURCE))
tree.body = [node for node in tree.body if getattr(node, "name", None) in NAMES]
namespace = {"hunter_now_ms": lambda: 1000, "ascii_text": lambda value: str(value)}
exec(compile(tree, str(SOURCE), "exec"), namespace)
Gateway = namespace["HunterQueueGateway"]
Controller = namespace["HunterController"]


class Observer:
    def __init__(self):
        self.vids = []
        self.cookie = 123
        self.valid = True
        self.eligible = True
        self.binding_ok = True

    def snapshot(self):
        return {"valid": self.valid, "player_cookie": self.cookie,
                "stock_binding_ok": self.binding_ok, "vids": tuple(self.vids),
                "enabled": True, "max_size": 5}

    def admission(self, vid):
        return {"valid": True, "eligible": self.eligible,
                "player_cookie": self.cookie}


class Pair:
    def __init__(self, events):
        self.events = events
        self.begin_status = 1
        self.end_status = 1
        self.begin_error = False
        self.end_error = False
        self.on_begin = None

    def begin_queue_add(self, vid):
        self.events.append(("down", vid))
        if self.on_begin:
            self.on_begin()
        if self.begin_error:
            raise RuntimeError("uncertain down append")
        return self.begin_status

    def end_queue_add(self, vid):
        self.events.append(("up", vid))
        if self.end_error:
            raise RuntimeError("uncertain up append")
        return self.end_status


class Player:
    def __init__(self, observer, events):
        self.observer = observer
        self.events = events
        self.reject = False
        self.error = False
        self.insert_then_error = False
        self.truthy_no_insert = False

    def MetinQueueGetMaxSize(self):
        return 5

    def MetinQueueAdd(self, vid):
        self.events.append(("add", vid))
        if self.reject:
            return 0
        if self.insert_then_error:
            self.observer.vids.append(vid)
            raise RuntimeError("uncertain queue outcome")
        if self.error:
            raise RuntimeError("uncertain queue outcome")
        if not self.truthy_no_insert:
            self.observer.vids.append(vid)
        return 1


class RecorderPairTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.observer = Observer()
        self.player = Player(self.observer, self.events)
        self.pair = Pair(self.events)
        self.gateway = Gateway(self.observer, self.player, clock=lambda: 1000,
                               recorder_pair_enabled=True, recorder_pair=self.pair)

    def request(self, vid=7):
        return {"vid": vid, "player_cookie": 123}

    def test_default_off_never_calls_native_pair(self):
        gateway = Gateway(self.observer, self.player, clock=lambda: 1000,
                          recorder_pair=self.pair)
        self.assertEqual(gateway.add_once(self.request()), Gateway.ADDED)
        self.assertEqual(self.events, [("add", 7)])

    def test_pair_brackets_exactly_one_stock_call_and_cannot_repeat(self):
        request = self.request()
        self.assertEqual(self.gateway.add_once(request), Gateway.ADDED)
        self.assertEqual(self.events, [("down", 7), ("add", 7), ("up", 7)])
        self.assertEqual(self.gateway.add_once(request), Gateway.CANCELLED_PRECALL)
        self.assertEqual(len(self.events), 3)

    def test_duplicate_and_rejected_admission_create_no_events(self):
        self.observer.vids = [7]
        self.assertEqual(self.gateway.add_once(self.request()), Gateway.ALREADY_PRESENT)
        self.observer.vids = []
        self.observer.eligible = False
        self.assertEqual(self.gateway.add_once(self.request()), Gateway.REJECTED_PRECALL)
        self.assertEqual(self.events, [])

    def test_stale_cookie_or_binding_creates_no_events(self):
        self.observer.cookie = 456
        self.assertEqual(self.gateway.add_once(self.request()), Gateway.CANCELLED_PRECALL)
        self.observer.cookie = 123
        self.observer.binding_ok = False
        self.assertEqual(self.gateway.add_once(self.request()), Gateway.REJECTED_PRECALL)
        self.assertEqual(self.events, [])

    def test_disabled_recorder_keeps_stock_path_without_up(self):
        self.pair.begin_status = 0
        request = self.request()
        self.assertEqual(self.gateway.add_once(request), Gateway.ADDED)
        self.assertEqual(self.events, [("down", 7), ("add", 7)])
        self.assertEqual(request["recorder_pair_begin_status"], 0)
        self.assertIsNone(self.gateway.input_experiment_error)

    def test_missing_native_module_has_no_silent_stock_fallback(self):
        self.gateway._recorder_pair = None
        self.assertEqual(self.gateway.add_once(self.request()), Gateway.REJECTED_PRECALL)
        self.assertTrue(self.gateway.input_experiment_error)
        self.assertEqual(self.events, [])

    def test_down_fault_latches_and_never_retries_same_or_new_request(self):
        self.pair.begin_error = True
        request = self.request()
        self.assertEqual(self.gateway.add_once(request), Gateway.REJECTED_PRECALL)
        self.assertNotIn("dispatched", request)
        self.assertEqual(self.gateway.add_once(request), Gateway.CANCELLED_PRECALL)
        self.assertEqual(self.gateway.add_once(self.request(8)), Gateway.REJECTED_PRECALL)
        self.assertEqual(self.events, [("down", 7)])

    def test_native_rejection_and_up_fault_still_preserve_queue_result(self):
        self.player.reject = True
        self.pair.end_error = True
        self.assertEqual(self.gateway.add_once(self.request()), Gateway.REJECTED_NATIVE)
        self.assertEqual(self.events, [("down", 7), ("add", 7), ("up", 7)])
        self.assertTrue(self.gateway.input_experiment_error)

    def test_up_failure_does_not_hide_confirmed_membership_or_repeat(self):
        self.pair.end_status = -3  # recorder reset/context change
        self.assertEqual(self.gateway.add_once(self.request()), Gateway.ADDED)
        self.assertEqual(self.observer.vids, [7])
        self.assertTrue(self.gateway.input_experiment_error)
        self.assertEqual(self.gateway.add_once(self.request(8)), Gateway.REJECTED_PRECALL)
        self.assertEqual(self.events, [("down", 7), ("add", 7), ("up", 7)])

    def test_queue_exception_still_attempts_up_once_and_stays_unknown(self):
        self.player.error = True
        request = self.request()
        self.assertEqual(self.gateway.add_once(request), Gateway.UNKNOWN)
        self.assertTrue(request["dispatched"])
        self.assertEqual(self.gateway.add_once(request), Gateway.CANCELLED_PRECALL)
        self.assertEqual(self.events, [("down", 7), ("add", 7), ("up", 7)])

    def test_membership_without_reliable_native_return_remains_unknown(self):
        self.player.insert_then_error = True
        self.assertEqual(self.gateway.add_once(self.request()), Gateway.UNKNOWN)
        self.assertEqual(self.observer.vids, [7])
        self.assertEqual(self.events[-1], ("up", 7))

    def test_truthy_return_without_membership_remains_unknown(self):
        self.player.truthy_no_insert = True
        self.assertEqual(self.gateway.add_once(self.request()), Gateway.UNKNOWN)

    def test_identity_change_after_down_blocks_queue_and_attempts_up_once(self):
        self.pair.on_begin = lambda: setattr(self.observer, "cookie", 456)
        request = self.request()
        self.assertEqual(self.gateway.add_once(request), Gateway.REJECTED_PRECALL)
        self.assertNotIn("dispatched", request)
        self.assertEqual(self.events, [("down", 7), ("up", 7)])
        self.assertTrue(self.gateway.input_experiment_error)

    def test_membership_appearing_after_down_prevents_duplicate_stock_dispatch(self):
        self.pair.on_begin = lambda: self.observer.vids.append(7)
        request = self.request()
        self.assertEqual(self.gateway.add_once(request), Gateway.ALREADY_PRESENT)
        self.assertNotIn("dispatched", request)
        self.assertEqual(self.events, [("down", 7), ("up", 7)])
        self.assertEqual(self.gateway.add_once(request), Gateway.CANCELLED_PRECALL)

    def test_invalid_observation_after_dispatched_add_stays_unknown(self):
        original = self.player.MetinQueueAdd
        def add_then_lose_observer(vid):
            result = original(vid)
            self.observer.valid = False
            return result
        self.player.MetinQueueAdd = add_then_lose_observer
        request = self.request()
        self.assertEqual(self.gateway.add_once(request), Gateway.UNKNOWN)
        self.assertTrue(request["dispatched"])
        self.assertEqual(self.gateway.add_once(request), Gateway.CANCELLED_PRECALL)
        self.assertEqual(self.events, [("down", 7), ("add", 7), ("up", 7)])

    def test_logging_failure_cannot_skip_stock_or_up(self):
        def bad_log(message):
            raise IOError("log unavailable")
        self.gateway._experiment_log = bad_log
        self.assertEqual(self.gateway.add_once(self.request()), Gateway.ADDED)
        self.assertEqual(self.events, [("down", 7), ("add", 7), ("up", 7)])

    def test_controller_halts_new_additions_on_latched_experiment_fault(self):
        self.gateway.input_experiment_error = "up outcome unknown"
        # The default profile isn't used before the fault guard.
        controller = Controller(self.gateway, None, lambda: 1000, lambda: True,
                                refill_profile=object())
        controller.state = Controller.RUNNING
        self.assertEqual(controller._run(1000), Controller.ERROR)
        self.assertEqual(self.events, [])
        self.assertEqual(self.observer.vids, [])

    def test_startup_mode_requires_exact_opt_in(self):
        with tempfile.TemporaryDirectory() as directory:
            mode = Path(directory) / "mode.txt"
            namespace["RECORDER_PAIR_MODE"] = str(mode)
            enabled = namespace["recorder_pair_experiment_enabled"]
            self.assertFalse(enabled())
            for value in (b"off", b"1", b"ON", b"on extra", b""):
                mode.write_bytes(value)
                self.assertFalse(enabled())
            mode.write_bytes(b"on\n")
            self.assertTrue(enabled())


if __name__ == "__main__":
    unittest.main()
