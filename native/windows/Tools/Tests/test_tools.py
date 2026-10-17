import importlib.util
import json
from pathlib import Path
import tempfile
import struct
import unittest

TOOLS = Path(__file__).resolve().parents[1]
def load(name):
    spec = importlib.util.spec_from_file_location(name, TOOLS / (name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

frames = load("frame_report")
toolchain = load("toolchain")
assets = load("asset_inventory")

def metadata():
    return dict(run_id="run1", scene_id="greenhouse", build_hash="c" * 64,
                asset_manifest_hash="a" * 64, raw_capture_sha256="b" * 64,
                raw_capture_path="raw.csv", gpu_name="test GPU", driver="test",
                profile="native", capture_tool_version="test",
                frame_generation=False, vsync=False, vrr=False, frame_cap=False,
                interval_kind="actual_rendered_frame", warmup_seconds=120,
                run_kind="standard", internal_render_percent=100,
                output_resolution=[2560, 1600], excluded_rows=[])

class FrameTests(unittest.TestCase):
    def test_18ms_is_not_60fps(self):
        report = frames.evaluate([18] * 34000, metadata())
        self.assertTrue(report["checks"]["p95_at_most_18ms"])
        self.assertFalse(report["checks"]["mean_fps_at_least_60"])
        self.assertEqual(report["status"], "fail")

    def test_native_fast_capture_passes_frame_gate_only(self):
        report = frames.evaluate([16] * 37500, metadata())
        self.assertEqual(report["status"], "frame_time_gate_pass")
        self.assertAlmostEqual(report["statistics"]["mean_fps"], 62.5)

    def test_nearest_rank_and_one_percent_low(self):
        values = [10] * 99 + [40]
        stats = frames.summarize(values)["statistics"]
        self.assertEqual(stats["p99_ms"], 10)
        self.assertEqual(stats["one_percent_low_fps"], 25)

    def test_bad_rows_are_not_silently_dropped(self):
        for values in ([], [0], [-1], [float("nan")], [float("inf")]):
            with self.assertRaises(ValueError): frames.summarize(values)

    def test_spike_needs_attribution_even_if_percentiles_pass(self):
        report = frames.evaluate([16] * 37500 + [101], metadata())
        self.assertEqual(report["status"], "needs_evidence_review")

    def test_no_fg_capped_short_or_excluded_capture_pass(self):
        for key, value in (("frame_generation", True), ("frame_cap", True), ("vsync", None),
                           ("excluded_rows", [{"reason": "unknown"}]),
                           ("internal_render_percent", 67), ("interval_kind", "displayed_frame")):
            meta = metadata()
            meta[key] = value
            self.assertEqual(frames.evaluate([16] * 37500, meta)["status"], "needs_evidence_review")
        self.assertEqual(frames.evaluate([16] * 100, metadata())["status"], "needs_evidence_review")

    def test_exact_long_frame_ratio_fails(self):
        values = [16] * 999 + [51]
        self.assertFalse(frames.summarize(values)["checks"]["over_50ms_below_0_001"])

    def test_invalid_warmup_never_passes(self):
        for value in (None, "120", float("nan"), float("inf"), True):
            meta = metadata()
            meta["warmup_seconds"] = value
            self.assertEqual(frames.evaluate([16] * 37500, meta)["status"], "needs_evidence_review")

class ToolchainTests(unittest.TestCase):
    def test_missing_engine_is_blocked(self):
        with tempfile.TemporaryDirectory() as root:
            result = toolchain.engine_inventory(Path(root))
            self.assertFalse(result["present"])
            self.assertTrue(result["issues"])

    def test_fake_files_are_inventory_not_qualification(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            version = root / "Engine/Build/Build.version"
            version.parent.mkdir(parents=True)
            version.write_text(json.dumps(dict(MajorVersion=5, MinorVersion=8, PatchVersion=1,
                                               IsPromotedBuild=1, BranchName="++UE5+Release-5.8")))
            for relative in ("Engine/Build/BatchFiles/Build.bat", "Engine/Build/BatchFiles/RunUAT.bat",
                             "Engine/Binaries/Win64/UnrealEditor.exe",
                             "Engine/Binaries/Win64/UnrealEditor-Cmd.exe"):
                p = root / relative
                p.parent.mkdir(parents=True, exist_ok=True)
                p.touch()
            self.assertFalse(toolchain.engine_inventory(root)["issues"])
            data = json.loads(version.read_text())
            data["BranchName"] = "5.8-preview"
            version.write_text(json.dumps(data))
            self.assertTrue(toolchain.engine_inventory(root)["issues"])

class AssetTests(unittest.TestCase):
    def write_glb(self, path, document):
        data = json.dumps(document).encode()
        data += b" " * ((-len(data)) % 4)
        path.write_bytes(struct.pack("<4s4I", b"glTF", 2, 20 + len(data), len(data), 0x4E4F534A) + data)

    def test_counts_mesh_references_separately(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "test.glb"
            self.write_glb(path, {"accessors": [{"count": 6}],
                                 "meshes": [{"primitives": [{"indices": 0}]}],
                                 "nodes": [{"mesh": 0}, {"mesh": 0}]})
            result = assets.glb_summary(path)
            self.assertEqual(result["unique_mesh_triangles"], 2)
            self.assertEqual(result["all_node_referenced_triangles"], 4)

    def test_invalid_or_external_asset_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "test.glb"
            path.write_bytes(b"bad")
            with self.assertRaises(ValueError): assets.glb_summary(path)
            self.write_glb(path, {"images": [{"uri": "https://example.com/private.png"}]})
            with self.assertRaises(ValueError): assets.glb_summary(path)

if __name__ == "__main__":
    unittest.main()
