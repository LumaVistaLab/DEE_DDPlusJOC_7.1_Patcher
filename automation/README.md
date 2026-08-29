# Automated reverse engineering and validation

This directory contains the repository's isolated flat-7.1 automation. It never
edits files under `example-flow`, and it does not integrate or call the
`DolbySurrEX-flag-patcher` project. Dolby Surround EX flag work is intentionally
deferred until a later 5.1 Dolby PLIIx phase.

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

The automation preflight pins the generated master to SHA-256
`bf67c22de5ea8b1c9ea776945f3e2bab46bf6356753f908dfd7942e8f751ad83`.

Raw DEE logs are retained under `patch_logs`. Every declared encoded output is
retained under `results`, including zero-byte outputs. Existing evidence is never
overwritten; pass `--rerun` to allocate `_r02`, `_r03`, and later suffixes.

Generated runtime copies and machine-readable evidence live under
`automation/work` and `automation/evidence` and are ignored by Git, but are not
deleted by the automation.
