"""Actual radar methods and selector against fake world/UI objects only."""
import ast
import math
from pathlib import Path
import unittest

source = Path(__file__).with_name("client_feature.py")
tree = ast.parse(source.read_text(encoding="ascii"), str(source))
methods = {"Scan", "UpdateMap", "UpdateMapPool", "UpdatePlayerMarker", "ClearMap"}
nodes = []
for node in tree.body:
    if getattr(node, "name", None) in ("HunterCandidateSelector", "radar_player_reach_offsets"):
        nodes.append(node)
    if isinstance(node, ast.ClassDef) and node.name == "MetinScanner":
        node.bases = [ast.Name(id="object", ctx=ast.Load())]
        node.body = [method for method in node.body if getattr(method, "name", None) in methods]
        nodes.append(node)
tree.body = nodes
namespace = {"math": math, "ascii_text": str, "hunter_now_ms": lambda: 1000}
exec(compile(ast.fix_missing_locations(tree), str(source), "exec"), namespace)
Panel = namespace["MetinScanner"]
Selector = namespace["HunterCandidateSelector"]
reach_offsets = namespace["radar_player_reach_offsets"]


class Dot:
    def __init__(self):
        self.visible = False
        self.position = None
        self.text = ""

    def SetPosition(self, x, y):
        self.position = (x, y)

    def SetText(self, text):
        self.text = text

    def Show(self):
        self.visible = True

    def Hide(self):
        self.visible = False


class World:
    def __init__(self):
        self.positions = {1: (0, 0, 0), 2: (-800, 0, 0), 3: (1000, 0, 0),
                          4: (1000.5, 0, 0), 5: (1800, 0, 0), 7: (-300, 100, 0)}

    def GetVirtualNumber(self, vid):
        return 1 if vid == 7 else 8014

    def GetNameByVID(self, vid):
        return "Metin" if vid != 7 else "Other"

    def GetPixelPosition(self, vid):
        return self.positions[vid]

    def IsMonsterStone(self, vnum):
        return vnum == 8014


class Controller:
    epoch = 3
    priority_enabled = False

    def on_scan(self, snapshot):
        self.last_scan = snapshot


class CountingSelector(Selector):
    def __init__(self, *args):
        super().__init__(*args)
        self.calls = 0

    def publish(self, *args):
        self.calls += 1
        return super().publish(*args)


class RadarRangeTests(unittest.TestCase):
    def setUp(self):
        self.world = World()
        namespace["chr"] = self.world
        namespace["nonplayer"] = self.world
        namespace["visible_vids"] = lambda: list(self.world.positions)
        self.panel = Panel()
        self.panel.radius = 1000
        self.panel.anchor_position = (0, 0)
        self.panel.radar_center = (465, 173)
        self.panel.radar_pixels = 112
        self.panel.hunter_selector = CountingSelector(None, self.world, self.world)
        self.panel.hunter_controller = Controller()
        self.panel.map_metins = [Dot() for _ in range(32)]
        self.panel.map_outside_metins = [Dot() for _ in range(32)]
        self.panel.map_others = [Dot() for _ in range(64)]
        self.panel.map_reach = [Dot() for _ in range(96)]
        self.panel.map_player = Dot()
        self.panel.map_count_label = Dot()
        self.lines = []
        self.panel.AddLine = self.lines.append

    def shown(self, pool):
        return [dot.position for dot in pool if dot.visible]

    def test_red_dots_and_counts_match_the_exact_hunter_snapshot(self):
        self.panel.Scan((800, 0, 0))
        snapshot = self.panel.hunter_controller.last_scan
        self.assertEqual({c["vid"] for c in snapshot["candidates"]}, {1, 3})
        self.assertEqual(self.panel.hunter_selector.calls, 1)
        self.assertEqual(len(self.shown(self.panel.map_metins)), 2)
        self.assertEqual(self.shown(self.panel.map_outside_metins), [(554, 173)])
        self.assertEqual(len(self.shown(self.panel.map_others)), 1)
        self.assertEqual(self.panel.map_count_label.text,
                         "Red: 2 in range  Gray: 1 out  White: 1")

    def test_fractional_anchor_boundary_is_not_rounded_into_range(self):
        self.world.positions = {3: (1000, 0, 0), 4: (1000.5, 0, 0)}
        self.panel.Scan((800, 0, 0))
        self.assertEqual(len(self.shown(self.panel.map_metins)), 1)
        self.assertEqual(len(self.shown(self.panel.map_outside_metins)), 0)
        self.assertEqual(self.shown(self.panel.map_metins), [(353, 173)])

    def test_fractional_player_boundary_is_gray_without_affecting_selection(self):
        self.world.positions = {1: (0, 0, 0), 2: (-0.5, 0, 0)}
        self.panel.Scan((1000, 0, 0))
        self.assertEqual(len(self.shown(self.panel.map_metins)), 1)
        self.assertEqual(len(self.shown(self.panel.map_outside_metins)), 1)

    def test_following_mode_has_one_range_and_no_gray_metins(self):
        self.panel.anchor_position = None
        self.panel.Scan((800, 0, 0))
        self.assertEqual(len(self.shown(self.panel.map_metins)), 4)
        self.assertEqual(len(self.shown(self.panel.map_outside_metins)), 0)
        self.panel.UpdatePlayerMarker((800, 0, 0))
        self.assertEqual(self.shown(self.panel.map_reach), [])

    def test_moving_player_reclassifies_stones_at_next_scan(self):
        self.world.positions = {1: (0, 0, 0), 2: (-800, 0, 0)}
        self.panel.Scan((800, 0, 0))
        self.assertEqual(len(self.shown(self.panel.map_outside_metins)), 1)
        self.panel.Scan((-800, 0, 0))
        self.assertEqual(len(self.shown(self.panel.map_outside_metins)), 0)
        self.assertEqual(len(self.shown(self.panel.map_metins)), 2)

    def test_clipped_reach_outline_obeys_both_circle_geometry_and_original_scale(self):
        offsets = reach_offsets((800, 0), (0, 0), 1000)
        self.assertTrue(0 < len(offsets) < 96)
        for x, y in offsets:
            self.assertLessEqual(x*x + y*y, 1000000 * (1+1e-12))
            self.assertAlmostEqual((x-800)**2 + y*y, 1000000, places=6)
        self.panel.UpdatePlayerMarker((800, 0, 0))
        expected = [(int(465-x*112/1000), int(173-y*112/1000)) for x, y in offsets]
        self.assertEqual(self.shown(self.panel.map_reach), expected)

    def test_disjoint_circles_show_no_reach_outline(self):
        self.assertEqual(reach_offsets((3000, 0), (0, 0), 1000), ())
        self.panel.UpdatePlayerMarker((3000, 0, 0))
        self.assertEqual(self.shown(self.panel.map_reach), [])
        self.assertFalse(self.panel.map_player.visible)

    def test_clear_hides_all_dynamic_dot_pools(self):
        self.panel.Scan((800, 0, 0))
        self.panel.UpdatePlayerMarker((800, 0, 0))
        self.panel.ClearMap()
        for pool in (self.panel.map_metins, self.panel.map_outside_metins,
                     self.panel.map_others, self.panel.map_reach):
            self.assertEqual(self.shown(pool), [])

    def test_snapshot_failure_clears_display_without_publishing_a_fake_scan(self):
        def failed(*args):
            raise RuntimeError("snapshot unavailable")
        self.panel.hunter_selector.publish = failed
        self.panel.Scan((800, 0, 0))
        self.assertFalse(hasattr(self.panel.hunter_controller, "last_scan"))
        self.assertIn("snapshot unavailable", self.lines[-1])
        self.assertEqual(self.shown(self.panel.map_metins), [])

    def test_count_is_not_limited_by_the_32_dot_render_pool(self):
        self.world.positions = {vid: (vid, 0, 0) for vid in range(10, 50)}
        self.panel.Scan((0, 0, 0))
        self.assertEqual(len(self.panel.hunter_controller.last_scan["candidates"]), 40)
        self.assertEqual(len(self.shown(self.panel.map_metins)), 32)
        self.assertIn("Red: 40 in range", self.panel.map_count_label.text)


if __name__ == "__main__":
    unittest.main()
