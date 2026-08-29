# Automated reverse engineering and validation

This directory contains the repository's isolated flat-7.1 encoding automation
and read-only PLIIx compatibility-core analysis. The encoder runner never edits
files under `example-flow` and never mutates Surround EX metadata. That metadata
step remains a separate, explicit invocation of the bundled
`DolbySurrEX-flag-patcher` project.

The stereo-compatibility invariant is profile-specific: streaming Pro Logic II
uses the Atmos `Lt/Rt (Pro Logic II) w/Phase 90` path. Blu-ray permits Lo/Ro or
traditional Lt/Rt but not the Pro Logic II Lt/Rt selector; its surround phase
rotation is supplied by the bitstream encoder preprocessing. The current
Blu-ray workflow keeps Lo/Ro as its default. The 7.1-to-5.1 PLIIx matrix itself
remains phase-neutral. See `PHASE_SHIFT_FINDINGS.md` for the binary and signal
evidence.

Primary commands (run from the repository root):

```powershell
python .\automation\tests\test_automation.py
python .\automation\build_flat71_patch.py --check
python .\automation\validate.py baseline
python .\automation\reverse_analysis.py
python .\automation\run.py preflight flat71_P2P3
python .\automation\run.py run flat71_P2P3
```

Generate and encode the deterministic 9.1.6 channel-identification master:

```powershell
python .\automation\generate_916_test_master.py
python .\automation\run.py preflight atmos916_flat71_P2P3
python .\automation\run.py run atmos916_flat71_P2P3
```

The generated master is 40 seconds of 48 kHz/24-bit audio. It uses a 7.1.2
Atmos bed plus six fixed objects for `Lw`, `Rw`, `Ltf`, `Rtf`, `Ltr`, and `Rtr`.
Its adjacent JSON report records the exact two-second listening schedule,
coordinates, frequencies, and SHA-256. The source master and report are kept in
`automation/work/test_audio`; the DD+ JOC result follows the normal retained
`results`, `patch_logs`, and `automation/evidence/runs` paths.

Analyze the encoded 5.1 AC-3 compatibility core against the documented Dolby
PLIIx 7.1-to-5.1 coefficients:

```powershell
python .\automation\pliix_core_analysis.py `
  .\results\atmos916_flat71_P2P3_r03.eb3 `
  --schedule .\automation\work\test_audio\atmos_916_channel_id_adm.wav.json `
  --output-dir .\automation\evidence\pliix\atmos916_flat71_P2P3
```

The analyzer extracts only AC-3 core frames, decodes them to six channels with
FFmpeg, measures the four isolated surround events, and writes a JSON evidence
report. It refuses to overwrite an existing evidence directory. See
`PLIIX_FINDINGS.md` for the validated result.

After the signal measurement passes, set and verify the separate Surround EX
metadata stage explicitly:

```powershell
python .\DolbySurrEX-flag-patcher-2966e09\patch_dsur_ex.py `
  .\results\atmos916_flat71_P2P3_r03.eb3 `
  .\results\atmos916_flat71_P2P3_r03.dsur-ex.eb3
python .\DolbySurrEX-flag-patcher-2966e09\patch_dsur_ex.py `
  --check .\results\atmos916_flat71_P2P3_r03.dsur-ex.eb3
python .\automation\validate.py stream `
  .\results\atmos916_flat71_P2P3_r03.dsur-ex.eb3
```

The automation preflight pins the generated master to SHA-256
`bf67c22de5ea8b1c9ea776945f3e2bab46bf6356753f908dfd7942e8f751ad83`.

Raw DEE logs are retained under `patch_logs`. Every declared encoded output is
retained under `results`, including zero-byte outputs. Existing evidence is never
overwritten; pass `--rerun` to allocate `_r02`, `_r03`, and later suffixes.

Generated runtime copies and machine-readable evidence live under
`automation/work` and `automation/evidence` and are ignored by Git, but are not
deleted by the automation.
