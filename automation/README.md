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

Raw DEE logs are retained under `patch_logs`. Every declared encoded output is
retained under `results`, including zero-byte outputs. Existing evidence is never
overwritten; pass `--rerun` to allocate `_r02`, `_r03`, and later suffixes.

Generated runtime copies and machine-readable evidence live under
`automation/work` and `automation/evidence` and are ignored by Git, but are not
deleted by the automation.
