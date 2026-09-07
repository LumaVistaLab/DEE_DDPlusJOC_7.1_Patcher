from __future__ import annotations

import importlib.util
import hashlib
import json
import os
import shutil
import subprocess
import sys
import unittest
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock


PRODUCT_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = PRODUCT_DIR / "dee-ddp71-atmos-wrapper.py"
SPEC = importlib.util.spec_from_file_location("dee_ddp71_atmos_wrapper", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
wrapper = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = wrapper
SPEC.loader.exec_module(wrapper)

CLEANER_PATH = PRODUCT_DIR / "tools" / "DEE-staging-cleaner" / "cleanup_dee_staging.py"


class WrapperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = PRODUCT_DIR / "work" / "tests" / uuid.uuid4().hex
        self.root.mkdir(parents=True)
        self.input = self.root / "master.wav"
        self.input.write_bytes(b"test-placeholder")
        self.extra_runtimes: list[Path] = []
        runs_root = PRODUCT_DIR / "work" / "runs"
        self.runs_before = set(runs_root.iterdir()) if runs_root.is_dir() else set()

    def tearDown(self) -> None:
        runtimes = [(self.root / "runtime").resolve(), *self.extra_runtimes]
        for runtime in runtimes:
            identity = hashlib.sha256(os.path.normcase(str(runtime)).encode("utf-8")).hexdigest()[:20]
            generated_backup = PRODUCT_DIR / "backups" / identity
            if generated_backup.is_dir():
                shutil.rmtree(generated_backup)
            generated_lock = PRODUCT_DIR / "backups" / ".locks" / f"{identity}.lock"
            if generated_lock.is_file():
                generated_lock.unlink()
        runs_root = PRODUCT_DIR / "work" / "runs"
        if runs_root.is_dir():
            for run_dir in set(runs_root.iterdir()) - self.runs_before:
                shutil.rmtree(run_dir)
        shutil.rmtree(self.root)

    def args(self, *extra: str):
        values = [str(self.root), str(self.input), str(self.root / "output.eb3"), *extra]
        return wrapper.build_parser().parse_args(values)

    def xml_root(self, args, *, start=None, end=None):
        encoded = self.root / "encoded.eb3"
        temp = self.root / "temp"
        temp.mkdir(exist_ok=True)
        return wrapper.make_job_xml(args, self.input, encoded, temp, start, end).getroot()

    def test_template_defaults_and_wrapper_fixed_values_for_height(self) -> None:
        args = self.args()
        root = self.xml_root(args)
        base = "./filter/audio/encode_to_atmos_ddp"
        self.assertEqual(root.findtext(f"{base}/data_rate"), "1152")
        self.assertEqual(root.findtext(f"{base}/downmix/preferred_downmix_mode"), "loro")
        self.assertEqual(root.findtext(f"{base}/encoding_backend"), "atmosprocessor")
        self.assertEqual(root.findtext(f"{base}/encoder_mode"), "bluray")
        self.assertIsNone(root.find(f"{base}/custom_dialnorm"))

    def test_xml_override_arguments_do_not_duplicate_template_defaults(self) -> None:
        parser = wrapper.build_parser()
        args = parser.parse_args([str(self.root), str(self.input), str(self.root / "output.eb3")])
        group = next(
            item
            for item in parser._action_groups
            if item.title == "original template parameter overrides (in XML order)"
        )
        for action in group._group_actions:
            self.assertIsNone(getattr(args, action.dest), action.dest)

    def test_xml_parameter_defaults_can_be_customized_in_the_template(self) -> None:
        template = ET.parse(wrapper.TEMPLATE_PATH)
        template_root = template.getroot()
        template_root.find("./filter/audio/encode_to_atmos_ddp/data_rate").text = "1536"
        template_root.find(
            "./filter/audio/encode_to_atmos_ddp/loudness/measure_only/speech_threshold"
        ).text = "27"
        custom_template = self.root / "custom-template.xml"
        template.write(custom_template, encoding="utf-8", xml_declaration=True)

        with mock.patch.object(wrapper, "TEMPLATE_PATH", custom_template):
            root = self.xml_root(self.args())

        base = "./filter/audio/encode_to_atmos_ddp"
        self.assertEqual(root.findtext(f"{base}/data_rate"), "1536")
        self.assertEqual(root.findtext(f"{base}/loudness/measure_only/speech_threshold"), "27")

    def test_flat71_default_and_user_overrides(self) -> None:
        args = self.args(
            "--compatibility-layout", "flat-7.1",
            "--data-rate", "1664",
            "--preferred-downmix-mode", "loro",
            "--custom-dialnorm", "-27",
            "--dialogue-intelligence", "false",
            "--speech-threshold", "44",
        )
        root = self.xml_root(args)
        base = "./filter/audio/encode_to_atmos_ddp"
        self.assertEqual(root.findtext(f"{base}/data_rate"), "1664")
        self.assertEqual(root.findtext(f"{base}/downmix/preferred_downmix_mode"), "loro")
        self.assertEqual(root.findtext(f"{base}/custom_dialnorm"), "-27")
        self.assertEqual(root.findtext(f"{base}/loudness/measure_only/dialogue_intelligence"), "false")
        self.assertEqual(root.findtext(f"{base}/loudness/measure_only/speech_threshold"), "44")
        children = [child.tag for child in root.find(base)]
        self.assertLess(children.index("custom_dialnorm"), children.index("encoding_backend"))

    def test_flat71_uses_ltrt_when_not_overridden(self) -> None:
        root = self.xml_root(self.args("--compatibility-layout", "flat-7.1"))
        self.assertEqual(
            root.findtext("./filter/audio/encode_to_atmos_ddp/downmix/preferred_downmix_mode"),
            "ltrt",
        )

    def test_every_original_value_override_is_written_to_its_xml_node(self) -> None:
        args = self.args(
            "--input-timecode-frame-rate", "25",
            "--input-offset", "01:00:00:00",
            "--input-ffoa", "01:00:08:00",
            "--metering-mode", "1770-3",
            "--dialogue-intelligence", "false",
            "--speech-threshold", "23",
            "--data-rate", "1408",
            "--timecode-frame-rate", "25",
            "--start", "01:01:00:00",
            "--end", "01:02:00:00",
            "--time-base", "embedded_timecode",
            "--prepend-silence-duration", "12f",
            "--append-silence-duration", "1.25",
            "--line-mode-drc-profile", "music_standard",
            "--rf-mode-drc-profile", "speech",
            "--loro-center-mix-level", "+1.5",
            "--loro-surround-mix-level", "-4.5",
            "--ltrt-center-mix-level", "-1.5",
            "--ltrt-surround-mix-level", "-6",
            "--preferred-downmix-mode", "ltrt",
            "--surround-trim-5-1", "-6",
            "--height-trim-5-1", "-9",
            "--clean-temp", "false",
        )
        root = self.xml_root(args)
        expected = {
            "./input/audio/atmos_mezz/timecode_frame_rate": "25",
            "./input/audio/atmos_mezz/offset": "01:00:00:00",
            "./input/audio/atmos_mezz/ffoa": "01:00:08:00",
            "./filter/audio/encode_to_atmos_ddp/loudness/measure_only/metering_mode": "1770-3",
            "./filter/audio/encode_to_atmos_ddp/loudness/measure_only/dialogue_intelligence": "false",
            "./filter/audio/encode_to_atmos_ddp/loudness/measure_only/speech_threshold": "23",
            "./filter/audio/encode_to_atmos_ddp/data_rate": "1408",
            "./filter/audio/encode_to_atmos_ddp/timecode_frame_rate": "25",
            "./filter/audio/encode_to_atmos_ddp/start": "01:01:00:00",
            "./filter/audio/encode_to_atmos_ddp/end": "01:02:00:00",
            "./filter/audio/encode_to_atmos_ddp/time_base": "embedded_timecode",
            "./filter/audio/encode_to_atmos_ddp/prepend_silence_duration": "12f",
            "./filter/audio/encode_to_atmos_ddp/append_silence_duration": "1.25",
            "./filter/audio/encode_to_atmos_ddp/drc/line_mode_drc_profile": "music_standard",
            "./filter/audio/encode_to_atmos_ddp/drc/rf_mode_drc_profile": "speech",
            "./filter/audio/encode_to_atmos_ddp/downmix/loro_center_mix_level": "+1.5",
            "./filter/audio/encode_to_atmos_ddp/downmix/loro_surround_mix_level": "-4.5",
            "./filter/audio/encode_to_atmos_ddp/downmix/ltrt_center_mix_level": "-1.5",
            "./filter/audio/encode_to_atmos_ddp/downmix/ltrt_surround_mix_level": "-6",
            "./filter/audio/encode_to_atmos_ddp/downmix/preferred_downmix_mode": "ltrt",
            "./filter/audio/encode_to_atmos_ddp/custom_trims/surround_trim_5_1": "-6",
            "./filter/audio/encode_to_atmos_ddp/custom_trims/height_trim_5_1": "-9",
            "./misc/temp_dir/clean_temp": "false",
        }
        for path, value in expected.items():
            self.assertEqual(root.findtext(path), value, path)

    def test_segmented_batch_builds_n_plus_one_adjacent_ranges(self) -> None:
        args = self.args(
            "--segmented-batch",
            "--timecode-frame-rate", "24",
            "--time-base", "file_position",
            "--segment-start", "file_start",
            "--segment-point", "00:10:00:00",
            "--segment-point", "00:20:00:00",
        )
        input_path, outputs = wrapper.validate_arguments(args)
        run_dir = self.root / "run"
        first_start = wrapper.resolve_segment_first_start(args, self.root, input_path)
        plans = wrapper.plan_jobs(args, input_path, outputs, run_dir, run_dir / "temp", first_start)
        self.assertEqual(len(plans), 3)
        self.assertEqual([plan.start for plan in plans], ["0", "00:10:00:00", "00:20:00:00"])
        self.assertEqual([plan.end for plan in plans], ["00:10:00:00", "00:20:00:00", "end_of_file"])
        self.assertEqual(
            [path.name for path in outputs],
            [
                "output.part001of003.eb3",
                "output.part002of003.eb3",
                "output.part003of003.eb3",
            ],
        )
        for plan in plans:
            root = ET.parse(plan.xml_path).getroot()
            self.assertEqual(root.findtext("./filter/audio/encode_to_atmos_ddp/start"), plan.start)
            self.assertEqual(root.findtext("./filter/audio/encode_to_atmos_ddp/end"), plan.end)

    def test_segment_points_are_passed_without_reformatting(self) -> None:
        args = self.args(
            "--segmented-batch",
            "--timecode-frame-rate", "29.97",
            "--time-base", "embedded_timecode",
            "--segment-start", "first_frame_of_action",
            "--segment-point", "01:02:03:04",
        )
        _, outputs = wrapper.validate_arguments(args)
        first_start = wrapper.resolve_segment_first_start(args, self.root, self.input)
        plans = wrapper.plan_jobs(
            args,
            self.input,
            outputs,
            self.root / "run",
            self.root / "run" / "temp",
            first_start,
        )
        self.assertEqual(plans[0].end, "01:02:03:04")
        self.assertEqual(plans[1].start, "01:02:03:04")

    def test_embedded_file_start_uses_explicit_input_offset(self) -> None:
        args = self.args(
            "--input-timecode-frame-rate", "24",
            "--input-offset", "01:00:00:00",
            "--segmented-batch",
            "--timecode-frame-rate", "24",
            "--time-base", "embedded_timecode",
            "--segment-start", "file_start",
            "--segment-point", "01:10:00:00",
        )
        self.assertEqual(
            wrapper.resolve_segment_first_start(args, self.root, self.input),
            "01:00:00:00",
        )

    def test_embedded_file_start_is_probed_and_converted_at_fractional_rates(self) -> None:
        atmos_info = self.root / "atmos_info.exe"
        atmos_info.write_bytes(b"placeholder")
        for frame_rate in ("23.976", "29.97", "59.94"):
            with self.subTest(frame_rate=frame_rate):
                args = self.args(
                    "--segmented-batch",
                    "--timecode-frame-rate", frame_rate,
                    "--time-base", "embedded_timecode",
                    "--segment-start", "file_start",
                    "--segment-point", "01:10:00:00",
                )
                output = (
                    "AtmosInfo Tool (version 1.1)\n"
                    "    Start time (in seconds): 3603.600000000000000\n"
                    f"    Video frame rate: {frame_rate}\n"
                )
                completed = subprocess.CompletedProcess([], 0, stdout=output)
                with mock.patch.object(wrapper.subprocess, "run", return_value=completed) as run:
                    first_start = wrapper.resolve_segment_first_start(args, self.root, self.input)
                self.assertEqual(first_start, "01:00:00:00")
                self.assertEqual(run.call_args.args[0][0], str(atmos_info))
                self.assertIn("--skip-validation", run.call_args.args[0])
                _, outputs = wrapper.validate_arguments(args)
                run_dir = self.root / f"run-{frame_rate}"
                plans = wrapper.plan_jobs(
                    args,
                    self.input,
                    outputs,
                    run_dir,
                    run_dir / "temp",
                    first_start,
                )
                root = ET.parse(plans[0].xml_path).getroot()
                self.assertEqual(root.findtext("./filter/audio/encode_to_atmos_ddp/start"), "01:00:00:00")

    def test_embedded_file_start_rejects_frame_offset_without_input_rate(self) -> None:
        args = self.args(
            "--input-offset", "01:00:00:00",
            "--segmented-batch",
            "--timecode-frame-rate", "24",
            "--time-base", "embedded_timecode",
            "--segment-start", "file_start",
            "--segment-point", "01:10:00:00",
        )
        with self.assertRaisesRegex(wrapper.WrapperError, "input-timecode-frame-rate"):
            wrapper.resolve_segment_first_start(args, self.root, self.input)

    def test_embedded_file_start_allows_source_and_filter_rates_to_differ(self) -> None:
        args = self.args(
            "--input-timecode-frame-rate", "29.97",
            "--segmented-batch",
            "--timecode-frame-rate", "29.97",
            "--time-base", "embedded_timecode",
            "--segment-start", "file_start",
            "--segment-point", "01:10:00:00",
        )
        (self.root / "atmos_info.exe").write_bytes(b"placeholder")
        output = "Start time (in seconds): 3603.6\nVideo frame rate: 24\n"
        completed = subprocess.CompletedProcess([], 0, stdout=output)
        with mock.patch.object(wrapper.subprocess, "run", return_value=completed):
            self.assertEqual(
                wrapper.resolve_segment_first_start(args, self.root, self.input),
                "01:00:00:00",
            )

    def test_embedded_file_start_uses_decimal_seconds_off_filter_grid(self) -> None:
        args = self.args(
            "--segmented-batch",
            "--timecode-frame-rate", "29.97",
            "--time-base", "embedded_timecode",
            "--segment-start", "file_start",
            "--segment-point", "01:10:00:00",
        )
        (self.root / "atmos_info.exe").write_bytes(b"placeholder")
        output = "Start time (in seconds): 3600\nVideo frame rate: 24\n"
        completed = subprocess.CompletedProcess([], 0, stdout=output)
        with mock.patch.object(wrapper.subprocess, "run", return_value=completed):
            self.assertEqual(
                wrapper.resolve_segment_first_start(args, self.root, self.input),
                "01:00:00.0",
            )

    def test_embedded_file_start_converts_explicit_offset_between_rates(self) -> None:
        args = self.args(
            "--input-timecode-frame-rate", "24",
            "--input-offset", "01:00:00:00",
            "--segmented-batch",
            "--timecode-frame-rate", "29.97",
            "--time-base", "embedded_timecode",
            "--segment-start", "file_start",
            "--segment-point", "01:10:00:00",
        )
        self.assertEqual(
            wrapper.resolve_segment_first_start(args, self.root, self.input),
            "01:00:00.0",
        )

    def test_segmented_batch_rejects_missing_required_controls(self) -> None:
        args = self.args("--segmented-batch", "--segment-point", "00:00:10:00")
        with self.assertRaisesRegex(wrapper.WrapperError, "timecode-frame-rate"):
            wrapper.validate_arguments(args)

    def test_leading_tilde_is_preserved_as_a_literal_path_character(self) -> None:
        runtime = self.root / "~DEE"
        runtime.mkdir()
        (runtime / "dee.exe").write_bytes(b"placeholder")
        (runtime / wrapper.PATCHED_COMPONENT).write_bytes(b"placeholder")
        input_path = self.root / "~master.wav"
        input_path.write_bytes(b"placeholder")
        previous_cwd = Path.cwd()
        try:
            os.chdir(self.root)
            args = wrapper.build_parser().parse_args(["~DEE", "~master.wav", "~output.eb3"])
            resolved_runtime, _, _ = wrapper.resolve_dee(args.dee)
            resolved_input, outputs = wrapper.validate_arguments(args)
        finally:
            os.chdir(previous_cwd)
        self.assertEqual(resolved_runtime, runtime.resolve())
        self.assertEqual(resolved_input, input_path.resolve())
        self.assertEqual(outputs, [(self.root / "~output.eb3").resolve()])

    def test_special_character_input_and_output_fallbacks_need_no_shell(self) -> None:
        special_dir = self.root / "路径 !#$%&'()+,-.;=@[]^_`{}~"
        special_dir.mkdir()
        special_input = special_dir / "母带 !#$%&'()+,-.;=@[]^_`{}~.wav"
        special_input.write_bytes(b"master")
        stage_root = self.root / "safe-stage"
        stage_root.mkdir()
        with mock.patch.object(wrapper, "windows_short_path", return_value=None):
            dee_input, method = wrapper.prepare_dee_input(special_input, stage_root)
        self.assertIn(method, ("hardlink", "copy"))
        self.assertEqual(dee_input.read_bytes(), b"master")
        self.assertIsNotNone(wrapper.CONSERVATIVE_WINDOWS_PATH_RE.fullmatch(str(dee_input)))

        requested_output = special_dir / "输出 !#$%&'()+,-.;=@[]^_`{}~.eb3"
        encoded = self.root / "encoded.eb3"
        encoded.write_bytes(b"encoded")
        wrapper.publish(encoded, requested_output, overwrite=False)
        self.assertEqual(requested_output.read_bytes(), b"encoded")

    def test_manual_stage_cleaner_force_clears_the_entire_staging_root(self) -> None:
        staging_root = self.root / "manual-temp" / "dee-ddp71-wrapper"
        arbitrary_stage = staging_root / "unmarked-or-incomplete-run" / "input"
        arbitrary_stage.mkdir(parents=True)
        (arbitrary_stage / "master.wav").write_bytes(b"temporary")
        listing = subprocess.run(
            [sys.executable, str(CLEANER_PATH), "--staging-root", str(staging_root), "--list"],
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(listing.returncode, 0, listing.stdout)
        self.assertIn("unmarked-or-incomplete-run", listing.stdout)
        self.assertTrue(staging_root.is_dir())

        forced = subprocess.run(
            [sys.executable, str(CLEANER_PATH), "--staging-root", str(staging_root)],
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(forced.returncode, 0, forced.stdout)
        self.assertIn("[cleared]", forced.stdout)
        self.assertFalse(staging_root.exists())

        invalid_root = self.root / "not-a-wrapper-stage"
        invalid_root.mkdir()
        rejected = subprocess.run(
            [sys.executable, str(CLEANER_PATH), "--staging-root", str(invalid_root)],
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(rejected.returncode, 2, rejected.stdout)
        self.assertTrue(invalid_root.is_dir())

    def test_validated_patch_matches_known_hash_when_research_fixture_exists(self) -> None:
        original = PRODUCT_DIR.parent / "dll_original" / wrapper.PATCHED_COMPONENT
        if not original.is_file():
            self.skipTest("repository-only proprietary test fixture is absent")
        patched = wrapper.build_flat71_binary(original.read_bytes())
        self.assertEqual(wrapper.sha256_bytes(patched), wrapper.EXPECTED_FLAT71_SHA256)
        for offset, _expected, replacement in wrapper.FLAT71_PATCHES:
            self.assertEqual(patched[offset : offset + len(replacement)], replacement)

    def test_patch_install_and_restore_round_trip(self) -> None:
        original = PRODUCT_DIR.parent / "dll_original" / wrapper.PATCHED_COMPONENT
        if not original.is_file():
            self.skipTest("repository-only proprietary test fixture is absent")
        component = self.root / wrapper.PATCHED_COMPONENT
        backup = self.root / "backup.dll"
        shutil.copy2(original, component)
        shutil.copy2(original, backup)
        wrapper.install_flat71_patch(component)
        self.assertEqual(wrapper.sha256_file(component), wrapper.EXPECTED_FLAT71_SHA256)
        wrapper.restore_component(backup, component)
        self.assertEqual(wrapper.sha256_file(component), wrapper.SUPPORTED_ORIGINAL_SHA256)

    def test_stale_known_patch_is_recovered_from_verified_backup(self) -> None:
        original = PRODUCT_DIR.parent / "dll_original" / wrapper.PATCHED_COMPONENT
        if not original.is_file():
            self.skipTest("repository-only proprietary test fixture is absent")
        runtime = self.root / "runtime"
        runtime.mkdir()
        component = runtime / wrapper.PATCHED_COMPONENT
        shutil.copy2(original, component)
        backup, recovered = wrapper.ensure_component_backup(runtime, component)
        self.assertFalse(recovered)
        wrapper.install_flat71_patch(component)
        same_backup, recovered = wrapper.ensure_component_backup(runtime, component)
        self.assertEqual(same_backup, backup)
        self.assertTrue(recovered)
        self.assertEqual(wrapper.sha256_file(component), wrapper.SUPPORTED_ORIGINAL_SHA256)

    def test_independent_surround_ex_patcher_on_one_frame_pair(self) -> None:
        validated_stream = PRODUCT_DIR.parent / "results" / "atmos916_flat71_P2P3_r03.eb3"
        if not validated_stream.is_file():
            self.skipTest("repository-only validated stream fixture is absent")
        source = self.root / "one-pair.eb3"
        output = self.root / "one-pair.dsur-ex.eb3"
        with validated_stream.open("rb") as handle:
            source.write_bytes(handle.read(2560 + 4096))
        result = subprocess.run(
            [sys.executable, str(wrapper.DSUR_EX_PATCHER), str(source), str(output)],
            cwd=str(PRODUCT_DIR),
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        check = subprocess.run(
            [sys.executable, str(wrapper.DSUR_EX_PATCHER), "--check", str(output)],
            cwd=str(PRODUCT_DIR),
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(check.returncode, 0, check.stdout)
        self.assertIn("dsurexmod counts: {2: 1}", check.stdout)
        self.assertEqual(source.read_bytes()[2560:], output.read_bytes()[2560:])

    def test_dry_run_backs_up_generates_xml_and_leaves_component_original(self) -> None:
        original = PRODUCT_DIR.parent / "dll_original" / wrapper.PATCHED_COMPONENT
        if not original.is_file():
            self.skipTest("repository-only proprietary test fixture is absent")
        runtime = self.root / "runtime"
        runtime.mkdir()
        (runtime / "dee.exe").write_bytes(b"dry-run placeholder")
        component = runtime / wrapper.PATCHED_COMPONENT
        shutil.copy2(original, component)
        args = wrapper.build_parser().parse_args(
            [
                str(runtime),
                str(self.input),
                str(self.root / "dry-run.eb3"),
                "--compatibility-layout", "flat-7.1",
                "--dry-run",
            ]
        )
        before = set((PRODUCT_DIR / "work" / "runs").glob("*/run.json"))
        self.assertEqual(wrapper.execute(args), 0)
        self.assertEqual(wrapper.sha256_file(component), wrapper.SUPPORTED_ORIGINAL_SHA256)
        created = set((PRODUCT_DIR / "work" / "runs").glob("*/run.json")) - before
        self.assertEqual(len(created), 1)
        manifest = created.pop().read_text(encoding="utf-8")
        self.assertIn('"status": "dry-run-complete"', manifest)

    def test_dee_master_and_output_accept_windows_valid_special_characters(self) -> None:
        original = PRODUCT_DIR.parent / "dll_original" / wrapper.PATCHED_COMPONENT
        if not original.is_file():
            self.skipTest("repository-only proprietary test fixture is absent")
        special_root = self.root / "路径 !#$%&'()+,-.;=@[]^_`{}~"
        runtime = (special_root / "DEE !#$%&'()+,-.;=@[]^_`{}~").resolve()
        runtime.mkdir(parents=True)
        self.extra_runtimes.append(runtime)
        (runtime / "dee.exe").write_bytes(b"simulated DEE placeholder")
        component = runtime / wrapper.PATCHED_COMPONENT
        shutil.copy2(original, component)
        special_input = special_root / "母带 !#$%&'()+,-.;=@[]^_`{}~.wav"
        special_input.write_bytes(b"special-path master")
        output = special_root / "输出 !#$%&'()+,-.;=@[]^_`{}~.eb3"
        args = wrapper.build_parser().parse_args([str(runtime), str(special_input), str(output)])

        def simulated_run_logged(command, cwd, log_path, label):
            self.assertTrue(label.startswith("DEE job"))
            self.assertNotEqual(cwd, runtime)
            self.assertIsNotNone(wrapper.CONSERVATIVE_WINDOWS_PATH_RE.fullmatch(str(cwd)))
            self.assertEqual(wrapper.sha256_file(cwd / wrapper.PATCHED_COMPONENT), wrapper.SUPPORTED_ORIGINAL_SHA256)
            command = list(command)
            dee_input = Path(command[command.index("-a") + 1])
            self.assertNotEqual(dee_input, special_input)
            self.assertIsNotNone(wrapper.CONSERVATIVE_WINDOWS_PATH_RE.fullmatch(str(dee_input)))
            self.assertEqual(dee_input.read_bytes(), special_input.read_bytes())
            job_root = ET.parse(Path(command[command.index("-x") + 1])).getroot()
            self.assertEqual(
                Path(job_root.findtext("./input/audio/atmos_mezz/storage/local/path"))
                / job_root.findtext("./input/audio/atmos_mezz/file_name"),
                special_input,
            )
            Path(command[command.index("-o") + 1]).write_bytes(b"encoded through safe paths")
            log_path.write_text("simulated DEE success\n", encoding="utf-8")

        # Exercise the hard-link/copy fallback used when an NTFS volume has no
        # 8.3 alias for the special-character master.
        with (
            mock.patch.object(wrapper, "windows_short_path", return_value=None),
            mock.patch.object(wrapper, "run_logged", side_effect=simulated_run_logged),
        ):
            self.assertEqual(wrapper.execute(args), 0)

        self.assertEqual(output.read_bytes(), b"encoded through safe paths")
        self.assertEqual(wrapper.sha256_file(component), wrapper.SUPPORTED_ORIGINAL_SHA256)
        runs_root = PRODUCT_DIR / "work" / "runs"
        created = set(runs_root.iterdir()) - self.runs_before
        self.assertEqual(len(created), 1)
        manifest = json.loads((created.pop() / "run.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["input"], str(special_input))
        self.assertEqual(manifest["outputs"][0]["path"], str(output))
        self.assertIn(manifest["dee_input_path_method"], ("hardlink", "copy"))
        self.assertTrue(manifest["safe_runtime_stage_removed"])
        self.assertTrue(manifest["safe_input_stage_removed"])
        self.assertTrue(manifest["safe_stage_root_removed"])
        self.assertFalse(Path(manifest["safe_stage_root"]).exists())

    def test_simulated_flat71_complete_flow_patches_then_restores_before_ex(self) -> None:
        original = PRODUCT_DIR.parent / "dll_original" / wrapper.PATCHED_COMPONENT
        validated_stream = PRODUCT_DIR.parent / "results" / "atmos916_flat71_P2P3_r03.eb3"
        if not original.is_file() or not validated_stream.is_file():
            self.skipTest("repository-only proprietary fixtures are absent")
        runtime = self.root / "runtime"
        runtime.mkdir()
        (runtime / "dee.exe").write_bytes(b"simulated DEE placeholder")
        component = runtime / wrapper.PATCHED_COMPONENT
        shutil.copy2(original, component)
        output = self.root / "complete-flat71.eb3"
        args = wrapper.build_parser().parse_args(
            [
                str(runtime),
                str(self.input),
                str(output),
                "--compatibility-layout", "flat-7.1",
                "--clean-temp", "false",
            ]
        )
        real_run_logged = wrapper.run_logged

        def simulated_run_logged(command, cwd, log_path, label):
            if label.startswith("DEE job"):
                self.assertEqual(wrapper.sha256_file(component), wrapper.EXPECTED_FLAT71_SHA256)
                command = list(command)
                job_root = ET.parse(Path(command[command.index("-x") + 1])).getroot()
                name = job_root.findtext("./output/ec3/file_name")
                parent = job_root.findtext("./output/ec3/storage/local/path")
                self.assertIsNotNone(name)
                self.assertIsNotNone(parent)
                self.assertEqual(Path(command[command.index("-a") + 1]), self.input.resolve())
                cli_output = Path(command[command.index("-o") + 1])
                self.assertEqual(cli_output, Path(parent) / name)
                self.assertTrue(Path(command[command.index("--temp") + 1]).is_dir())
                with validated_stream.open("rb") as handle:
                    cli_output.write_bytes(handle.read(2560 + 4096))
                log_path.write_text("simulated DEE success\n", encoding="utf-8")
                return
            self.assertEqual(wrapper.sha256_file(component), wrapper.SUPPORTED_ORIGINAL_SHA256)
            real_run_logged(command, cwd, log_path, label)

        with mock.patch.object(wrapper, "run_logged", side_effect=simulated_run_logged):
            self.assertEqual(wrapper.execute(args), 0)
        self.assertEqual(wrapper.sha256_file(component), wrapper.SUPPORTED_ORIGINAL_SHA256)
        self.assertTrue(output.is_file())
        check = subprocess.run(
            [sys.executable, str(wrapper.DSUR_EX_PATCHER), "--check", str(output)],
            cwd=str(PRODUCT_DIR),
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(check.returncode, 0, check.stdout)
        self.assertIn("dsurexmod counts: {2: 1}", check.stdout)
        runs_root = PRODUCT_DIR / "work" / "runs"
        created = set(runs_root.iterdir()) - self.runs_before
        self.assertEqual(len(created), 1)
        run_dir = created.pop()
        self.assertEqual(len(list((run_dir / "encoded").glob("*.eb3"))), 1)
        self.assertEqual(len(list((run_dir / "finalized").glob("*.eb3"))), 1)
        self.assertTrue((run_dir / "jobs" / "single.xml").is_file())
        self.assertTrue((run_dir / "logs" / "single.dee.log").is_file())
        self.assertTrue((run_dir / "logs" / "single.dsur-ex.log").is_file())
        manifest = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        self.assertFalse(manifest["clean_temp"])
        self.assertEqual(manifest["intermediate_stream_cleanup"], "disabled")
        self.assertTrue(Path(manifest["backup"]).is_file())

    def test_segmented_batch_publishes_each_completed_segment_immediately(self) -> None:
        original = PRODUCT_DIR.parent / "dll_original" / wrapper.PATCHED_COMPONENT
        validated_stream = PRODUCT_DIR.parent / "results" / "atmos916_flat71_P2P3_r03.eb3"
        if not original.is_file() or not validated_stream.is_file():
            self.skipTest("repository-only proprietary fixtures are absent")
        runtime = self.root / "runtime"
        runtime.mkdir()
        (runtime / "dee.exe").write_bytes(b"simulated DEE placeholder")
        component = runtime / wrapper.PATCHED_COMPONENT
        shutil.copy2(original, component)
        output_base = self.root / "segmented-flat71.eb3"
        outputs = wrapper.output_paths(output_base, 2)
        args = wrapper.build_parser().parse_args(
            [
                str(runtime),
                str(self.input),
                str(output_base),
                "--compatibility-layout", "flat-7.1",
                "--segmented-batch",
                "--timecode-frame-rate", "24",
                "--time-base", "file_position",
                "--segment-start", "file_start",
                "--segment-point", "00:00:10:00",
            ]
        )
        real_run_logged = wrapper.run_logged
        dee_job_count = 0

        def simulated_run_logged(command, cwd, log_path, label):
            nonlocal dee_job_count
            if label.startswith("DEE job"):
                dee_job_count += 1
                self.assertEqual(wrapper.sha256_file(component), wrapper.EXPECTED_FLAT71_SHA256)
                if dee_job_count == 2:
                    self.assertTrue(outputs[0].is_file())
                    self.assertFalse(outputs[1].exists())
                    command = list(command)
                    Path(command[command.index("-o") + 1]).write_bytes(b"partial stream")
                    log_path.write_text("simulated DEE failure\n", encoding="utf-8")
                    raise wrapper.CommandFailure("simulated second DEE job", 77)
                command = list(command)
                cli_output = Path(command[command.index("-o") + 1])
                with validated_stream.open("rb") as handle:
                    cli_output.write_bytes(handle.read(2560 + 4096))
                log_path.write_text("simulated DEE success\n", encoding="utf-8")
                return
            real_run_logged(command, cwd, log_path, label)

        with mock.patch.object(wrapper, "run_logged", side_effect=simulated_run_logged):
            with self.assertRaises(wrapper.CommandFailure):
                wrapper.execute(args)
        self.assertEqual(wrapper.sha256_file(component), wrapper.SUPPORTED_ORIGINAL_SHA256)
        self.assertTrue(outputs[0].is_file())
        self.assertFalse(outputs[1].exists())
        check = subprocess.run(
            [sys.executable, str(wrapper.DSUR_EX_PATCHER), "--check", str(outputs[0])],
            cwd=str(PRODUCT_DIR),
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(check.returncode, 0, check.stdout)
        self.assertIn("dsurexmod counts: {2: 1}", check.stdout)
        runs_root = PRODUCT_DIR / "work" / "runs"
        created = set(runs_root.iterdir()) - self.runs_before
        self.assertEqual(len(created), 1)
        run_dir = created.pop()
        retained = run_dir / "encoded" / "part002of002.encoded.eb3"
        self.assertEqual(list((run_dir / "encoded").iterdir()), [retained])
        self.assertEqual(retained.read_bytes(), b"partial stream")
        self.assertEqual(list((run_dir / "finalized").iterdir()), [])
        self.assertEqual(len(list((run_dir / "jobs").glob("*.xml"))), 2)
        self.assertEqual(len(list((run_dir / "logs").glob("*.log"))), 3)
        manifest = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        self.assertTrue(manifest["clean_temp"])
        self.assertEqual(manifest["intermediate_stream_cleanup"], "complete")
        self.assertEqual(manifest["retained_failed_intermediate_streams"], [str(retained)])
        self.assertEqual(manifest["status"], "failed")
        self.assertTrue(Path(manifest["backup"]).is_file())

    def test_dee_failure_still_restores_original_component(self) -> None:
        original = PRODUCT_DIR.parent / "dll_original" / wrapper.PATCHED_COMPONENT
        if not original.is_file():
            self.skipTest("repository-only proprietary test fixture is absent")
        runtime = self.root / "runtime"
        runtime.mkdir()
        (runtime / "dee.exe").write_bytes(b"simulated DEE placeholder")
        component = runtime / wrapper.PATCHED_COMPONENT
        shutil.copy2(original, component)
        args = wrapper.build_parser().parse_args(
            [
                str(runtime),
                str(self.input),
                str(self.root / "should-not-exist.eb3"),
                "--compatibility-layout", "flat-7.1",
            ]
        )

        def fail_dee(_command, _cwd, _log_path, _label):
            self.assertEqual(wrapper.sha256_file(component), wrapper.EXPECTED_FLAT71_SHA256)
            raise wrapper.CommandFailure("simulated DEE", 77)

        with mock.patch.object(wrapper, "run_logged", side_effect=fail_dee):
            with self.assertRaises(wrapper.CommandFailure):
                wrapper.execute(args)
        self.assertEqual(wrapper.sha256_file(component), wrapper.SUPPORTED_ORIGINAL_SHA256)
        self.assertFalse((self.root / "should-not-exist.eb3").exists())


if __name__ == "__main__":
    unittest.main()
