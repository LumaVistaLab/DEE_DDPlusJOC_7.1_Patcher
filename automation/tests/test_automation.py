from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from pathlib import Path

AUTOMATION_DIR = Path(__file__).resolve().parents[1]
if str(AUTOMATION_DIR) not in sys.path:
    sys.path.insert(0, str(AUTOMATION_DIR))

from common import (  # noqa: E402
    load_config,
    manifest_changes,
    reserve_unique_paths,
    tree_manifest,
)
from build_flat71_patch import (  # noqa: E402
    EXPECTED_OUTPUT_SHA256,
    PATCHES,
    build_patched_bytes,
)
from run import capture_process  # noqa: E402
from stream_validation import scan_frames  # noqa: E402
from generate_916_test_master import (  # noqa: E402
    TRACKS,
    build_axml,
    build_chna,
    read_riff_chunks,
)


class AutomationTests(unittest.TestCase):
    def setUp(self) -> None:
        work = AUTOMATION_DIR / "work"
        work.mkdir(parents=True, exist_ok=True)
        # tempfile.mkdtemp uses a restrictive Windows mode that can produce an
        # unusable ACL inside the managed workspace sandbox. A normal directory
        # inherits the repository ACL and is still uniquely named.
        self.temp = work / f"unit-{uuid.uuid4().hex}"
        self.temp.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.temp)

    def test_config_is_flat_layout_only(self) -> None:
        config = load_config()
        self.assertIn("flat 7.1", config["scope"])
        self.assertIn("out of scope", config["scope"])
        self.assertEqual(config["cases"][0]["id"], "flat71_P2P3")
        self.assertFalse(config["cases"][0]["gated"])
        self.assertTrue(config["cases"][1]["gated"])
        self.assertEqual(config["cases"][2]["id"], "atmos916_flat71_P2P3")
        self.assertFalse(config["cases"][2]["gated"])
        self.assertIn("automation/work/test_audio", config["cases"][2]["input_audio"])
        self.assertEqual(len(config["cases"][2]["expected_input_sha256"]), 64)

    def test_916_adm_rewrite_has_16_matching_tracks(self) -> None:
        template = AUTOMATION_DIR.parent / "example-flow" / "sollevante_lp_v01_DAMF_Nearfield_48k_24b_24.wav"
        source = read_riff_chunks(template, {b"axml", b"chna"})
        axml = build_axml(source[b"axml"])
        chna = build_chna(source[b"chna"])
        self.assertEqual(len(TRACKS), 16)
        self.assertEqual(len({track["label"] for track in TRACKS}), 16)
        self.assertEqual(len([track for track in TRACKS if track["kind"] == "bed"]), 10)
        self.assertEqual(len([track for track in TRACKS if track["kind"] == "object"]), 6)
        self.assertEqual(int.from_bytes(chna[0:2], "little"), 16)
        self.assertEqual(int.from_bytes(chna[2:4], "little"), 16)
        self.assertIn(b"Atmos_9.1.6_Channel_ID", axml)
        self.assertEqual(axml.count(b"<audioTrackUID "), 16)

    def test_paths_never_overwrite_and_reruns_are_numbered(self) -> None:
        output = self.temp / "case.eb3"
        log = self.temp / "case.log"
        evidence = self.temp / "case"
        output.touch()
        with self.assertRaises(FileExistsError):
            reserve_unique_paths(output, log, evidence, rerun=False)
        new_output, new_log, new_evidence, suffix = reserve_unique_paths(output, log, evidence, rerun=True)
        self.assertEqual(suffix, "_r02")
        self.assertEqual(new_output.name, "case_r02.eb3")
        self.assertEqual(new_log.name, "case_r02.log")
        self.assertEqual(new_evidence.name, "case_r02")

    def test_zero_byte_output_survives_crash(self) -> None:
        output = self.temp / "crash.eb3"
        output.touch()
        log = self.temp / "crash.log"
        fake = Path(__file__).with_name("fake_dee.py")
        report = capture_process(
            [sys.executable, str(fake), "--mode", "crash", "--output", str(output)],
            self.temp,
            log,
            timeout_seconds=5,
        )
        self.assertEqual(report["returncode"], 10)
        self.assertEqual(output.stat().st_size, 0)
        text = log.read_text(encoding="utf-8")
        self.assertIn("Access violation", text)
        self.assertIn("Application exits with error code: 10", text)

    def test_success_output_and_complete_log_are_retained(self) -> None:
        output = self.temp / "success.eb3"
        output.touch()
        log = self.temp / "success.log"
        fake = Path(__file__).with_name("fake_dee.py")
        report = capture_process(
            [sys.executable, str(fake), "--mode", "success", "--output", str(output)],
            self.temp,
            log,
            timeout_seconds=5,
        )
        self.assertEqual(report["returncode"], 0)
        self.assertEqual(output.read_bytes(), b"synthetic-output")
        text = log.read_text(encoding="utf-8")
        self.assertIn("measurement pass", text)
        self.assertIn("encoder pass complete", text)
        self.assertIn("Time elapsed:", text)

    def test_timeout_retains_placeholder(self) -> None:
        output = self.temp / "timeout.eb3"
        output.touch()
        log = self.temp / "timeout.log"
        fake = Path(__file__).with_name("fake_dee.py")
        report = capture_process(
            [sys.executable, str(fake), "--mode", "slow", "--output", str(output)],
            self.temp,
            log,
            timeout_seconds=0.2,
        )
        self.assertTrue(report["timed_out"])
        self.assertEqual(output.stat().st_size, 0)
        self.assertIn("Automation timeout", log.read_text(encoding="utf-8"))

    def test_tree_manifest_detects_changes(self) -> None:
        guarded = self.temp / "guarded"
        guarded.mkdir()
        sample = guarded / "sample.txt"
        sample.write_text("before", encoding="utf-8")
        before = tree_manifest(guarded)
        sample.write_text("after", encoding="utf-8")
        after = tree_manifest(guarded)
        changes = manifest_changes(before, after)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["change"], "modified")

    def test_empty_stream_is_a_retained_result_not_missing(self) -> None:
        path = self.temp / "empty.eb3"
        path.touch()
        report = scan_frames(path)
        self.assertEqual(report["status"], "empty")
        self.assertEqual(report["frame_count"], 0)

    def test_validated_patch_is_reproducible_and_only_changes_the_pair_plus_checksum(self) -> None:
        source_path = AUTOMATION_DIR.parent / "dll_original" / "dee_audio_filter_ddp_atmos.dll"
        source = source_path.read_bytes()
        output = build_patched_bytes(source)
        import hashlib

        self.assertEqual(hashlib.sha256(output).hexdigest(), EXPECTED_OUTPUT_SHA256)
        for offset, expected, replacement in PATCHES:
            self.assertEqual(source[offset : offset + len(expected)], expected)
            self.assertEqual(output[offset : offset + len(replacement)], replacement)


if __name__ == "__main__":
    unittest.main(verbosity=2)
