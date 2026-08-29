# Validated flat-7.1 result

Date: 2026-08-29

Scope: Blu-ray Dolby Digital Plus with Dolby Atmos (DD+ JOC) flat 7.1 only.
Dolby Surround EX flag patching was not imported, called, or used by this
flat-layout workflow. The later, separate PLIIx core result is documented in
`PLIIX_FINDINGS.md`.

## Validated patch

Supported source SHA-256:

```text
3d66bcec36031fd48e6565d15f05fea656642377ca4f8c98cdce1cce8b7e95d2
```

The successful P2+P3 variant changes the synchronized pair below:

| Site | Static VA | File offset | Original | Replacement |
| --- | ---: | ---: | --- | --- |
| P3 | `0x18017CCD7` | `0x17C0D7` | `B8 13 00 00 00` | `B8 15 00 00 00` |
| P2 | `0x18017D5E8` | `0x17C9E8` | `B8 13 00 00 00` | `B8 15 00 00 00` |

Validated patched-DLL SHA-256:

```text
fd49c7b9b19bba5f7ec0b862a9811a7b822b2efe200bc82a033fb9b7f54c1588
```

P2 alone and P1+P2 are retained as negative controls: both finish the
measurement pass and then crash at the same first-frame access violation. P2+P3
shows that the two sites form a synchronized configuration pair.

## Dynamic result

The isolated test runner installed P2+P3 into a disposable copy of the DEE
runtime. It did not edit `dee_copy`, `dll_original`, or anything in
`example-flow`.

- DEE exit code: `0`
- DEE-reported job time: 119 seconds
- Output size: 54,725,632 bytes
- Output SHA-256: `cb8b7cad90c722ea41437344be711e83def72af019b731a86bee4786cfb0343c`
- Full parsed size: 54,725,632 bytes
- Trailing/unparsed bytes: 0
- AC-3 core frames: 8,222 × 2,560 bytes
- E-AC-3 dependent/JOC frames: 8,222 × 4,096 bytes
- MediaInfo profile: Blu-ray Disc, Dep JOC, Dolby Digital Plus with Dolby Atmos
- MediaInfo layout: `L R C LFE Ls Rs Lb Rb`
- MediaInfo positions: `Front: L C R, Side: L R, Back: L R, LFE`
- FFprobe: eight channels, `7.1`, Dolby Digital Plus + Dolby Atmos
- `example-flow` manifest changes: 0

The resulting layout is the target rear-surround form (`Lb/Rb` is MediaInfo's
alias for `Lrs/Rrs`) and contains no `Tfl/Tfr` height-layout evidence.

The complete console log is retained in `patch_logs/flat71_P2P3.log`; the raw
bitstream is retained in `results/flat71_P2P3.eb3`. Machine-readable run,
MediaInfo, FFprobe, frame-scan, hash, and input-integrity evidence is retained
locally under `automation/evidence/runs/flat71_P2P3`.

## Automated reverse-analysis result

The static pipeline extracted 40,024 strings, parsed 25,920 x64 runtime
functions, and followed 55,964 direct call edges. In addition to the P2/P3
configuration layer, it found a separate three-state channel-mode mapping:

```text
0x0C -> 0
0x0E -> 1
0x10 -> 2
```

The mapping function is at static VA `0x18018B9B0`. Its workflow caller at
`0x18017B710` selects `0x10` for the Blu-ray branch and `0x0C` for the other
branch. The three values are strong static candidates for conceptual
`5.X / 7.X / 5.X+2` modes, but that semantic mapping remains an inference.

No patch was made at this downstream site. P2+P3 already produced the target,
so changing an additional unvalidated selector would add risk without serving
the current objective. P1+P2+P3 remains gated for the same reason.

## Reproduction

```powershell
python .\automation\build_flat71_patch.py --check
python .\automation\tests\test_automation.py
python .\automation\validate.py baseline
python .\automation\run.py preflight flat71_P2P3
python .\automation\run.py run flat71_P2P3
```

Existing logs, results, and evidence are never overwritten. Use `--rerun` to
allocate `_r02`, `_r03`, and later retained copies.
