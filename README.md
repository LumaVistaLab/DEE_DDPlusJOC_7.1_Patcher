# DD+ 7.1 Atmos Patcher for DEE

Language: English | [简体中文](README_zh-CN.md)

An experimental binary-patching and reverse-engineering project for Dolby Encoding Engine (DEE) 5.2.1. Its goal is to determine whether Blu-ray Dolby Digital Plus with Dolby Atmos (DD+ JOC) can use a flat 7.1 coded/compatibility layout:

```text
L R C LFE Ls Rs Lrs Rrs
```

instead of the current Blu-ray `5.X+2` / `7.1 Height` layout:

```text
L R C LFE Ls Rs Tfl Tfr
```

This project does not target ordinary channel-based E-AC-3 7.1. The target is specifically a DD+ JOC / Dolby Atmos for Blu-ray bitstream with a flat 7.1 coded layout.

> [!WARNING]
> This remains an experimental patch for one exact DEE 5.2.1 binary build. The paired P2+P3 patch has produced the target flat 7.1 JOC layout, but it is not a general-purpose or production-ready patch. Always preserve the original binary.

## Current Status

| Variant | Change | Result |
| --- | --- | --- |
| P1 | AtmosProcessor render format: `5.1` -> `7.1` | Encoding succeeds, but the final stream remains `7.1 Height` |
| P2 | One Blu-ray internal configuration site: `19` -> `21` | Encoder pass crashes with an access violation |
| P1+P2 | P1 plus the single P2 configuration change | Same crash as P2 |
| P2+P3 | Paired internal configuration sites: `19` -> `21` | **Success: flat 7.1 DD+ JOC (`L R C LFE Ls Rs Lb Rb`)** |
| P1+P2+P3 | P1 plus paired P2/P3 changes | Not tested; P2+P3 already reaches the target |
| P3 only | Opposite single-site diagnostic mismatch | Generated; low-priority diagnostic build |

The successful P1 experiment proves that changing the AtmosProcessor render format alone does not change the final JOC coded layout. The later P2+P3 experiment proves that both `19 -> 21` sites must change together: a single-site change creates inconsistent initialization and crashes, while the paired change produces the target flat 7.1 layout.

Automated static analysis also found a separate `0x0C / 0x0E / 0x10` three-state channel-mode mapping. Because P2+P3 already reaches the target, that candidate was neither modified nor dynamically tested.

## Requirements

- A legally obtained Dolby Encoding Engine 5.2.1 installation and valid license
- The exact supported `dee_audio_filter_ddp_atmos.dll` build
- Python 3
- A consistent ADM/DAMF test source and DEE job XML
- MediaInfo or another suitable E-AC-3/JOC bitstream inspection tool

The supported original DLL must have this SHA-256 digest:

```text
3d66bcec36031fd48e6565d15f05fea656642377ca4f8c98cdce1cce8b7e95d2
```

The patch scripts refuse to modify an unsupported binary and verify the expected bytes at every patch site before writing an output file.

## Repository Layout

```text
DEE_DDPlusJOC_7.1_Patcher/
|-- patchers/        Patch-generation scripts
|-- automation/      Isolated patch build, reverse, test, and stream-validation scripts
|-- patch_logs/      Preserved complete test logs
|-- example-flow/    Example Blu-ray DD+ Atmos job files
|-- gpt-context/     Reverse-engineering notes and context transfer
|-- dll_original/    Local original DLL; ignored by Git
|-- dll_patched/     Locally generated experimental DLLs; ignored by Git
|-- dee_copy/        Local DEE runtime copy; ignored by Git
`-- results/         Local encoded test outputs
```

Dolby binaries, licenses, and large test media are not part of the source distribution. Supply them from your own authorized installation.

## Building the validated flat-7.1 patch

From the repository root:

```powershell
python .\automation\build_flat71_patch.py
```

This builds only the validated paired P2+P3 variant. It checks the source DLL hash, original bytes at both sites, PE checksum, and final output hash. Existing output is not overwritten by default.

## Generating legacy diagnostic variants

From the repository root, run:

```powershell
python .\patchers\make_dee_flat71_patches.py `
  .\dll_original\dee_audio_filter_ddp_atmos.dll `
  --out-dir .\dll_patched
```

This creates the P1, P2, and P1+P2 variants after validating the source DLL hash and original instruction bytes.

The earlier `make_dee_cfg21_patches_v2.py` script creates P2+P3, P1+P2+P3, and P3-only diagnostic variants next to the supplied DLL. Only paired P2+P3 has been validated with the fixed test source.

## Automated validation

```powershell
python .\automation\tests\test_automation.py
python .\automation\validate.py baseline
python .\automation\run.py preflight flat71_P2P3
python .\automation\run.py run flat71_P2P3
```

The automation never edits `example-flow`, never overwrites retained evidence, and preserves every declared output, including zero-byte crash outputs. Dolby Surround EX flag patching is outside the current flat-7.1 phase.

## Testing Guidance

1. Keep the original DEE runtime and DLL read-only and backed up.
2. Verify the original and candidate SHA-256 digests before every test.
3. Install only one candidate DLL into a disposable runtime copy.
4. Reuse the same ADM/DAMF source, XML job, bitrate, and temporary-directory settings.
5. Capture the complete DEE log and process exit code.
6. For every successful output, record the MediaInfo channel layout and preserve the bitstream for comparison.
7. For every crash, record the runtime address, loaded DLL base, RVA/static VA, exact instruction, and relevant object state.

Never overwrite the DLL's global `"5.1"` string. P1 changes only the two intended RIP-relative references so the parser's comparison table remains intact.

## Known Evidence

- DEE 5.2.1 contains an ordinary channel-based `ddp71` path with the flat order `L R C LFE Ls Rs Lrs Rrs`.
- The standalone DD+ encoder contains real hidden `bluray` and `bluray_secondary` modes.
- The Atmos filter exposes hidden `encoding_backend` and `encoder_mode` parameters; Blu-ray mode uses the AtmosProcessor backend.
- P1 completes both passes and produces a valid non-zero stream, but the coded layout remains `7.1 Height`.
- P2 and P1+P2 fail deterministically at the same first-frame access violation after the measurement pass, indicating inconsistent paired initialization rather than a confirmed layout switch.
- P2+P3 completes both passes with exit code 0; the output SHA-256 is `cb8b7cad90c722ea41437344be711e83def72af019b731a86bee4786cfb0343c`.
- Its output contains 8,222 2,560-byte AC-3 core frames and 8,222 4,096-byte E-AC-3 dependent/JOC frames with no trailing bytes. MediaInfo reports `L R C LFE Ls Rs Lb Rb`; FFprobe reports eight-channel Dolby Digital Plus + Dolby Atmos.
- The complete `example-flow` file-hash manifest is unchanged before and after the automated run.

See [CODEX_CONTEXT_TRANSFER.md](gpt-context/CODEX_CONTEXT_TRANSFER.md) for historical research context, [the automated flat-7.1 findings](automation/FLAT71_FINDINGS.md) for the successful result, and [the complete P2+P3 log](patch_logs/flat71_P2P3.log).

## Legal Notice

This repository is an independent research project and is not affiliated with or endorsed by Dolby Laboratories. Dolby, Dolby Atmos, and Dolby Encoding Engine are trademarks or products of their respective owner.

No proprietary Dolby software, license, or test media is granted by this project. You are responsible for complying with all applicable licenses, laws, and contractual restrictions when analyzing or modifying software.

## License

The original code and documentation in this repository are released under the [GNU General Public License v3.0](LICENSE). This license does not apply to third-party proprietary binaries or media.
