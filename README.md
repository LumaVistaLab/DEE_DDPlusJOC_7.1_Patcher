# DEE_DDPlusJOC_7.1_Patcher

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
> This is unfinished experimental work. No available patch has yet produced the target flat 7.1 JOC layout. Do not use the generated DLLs in production, and always preserve the original binary.

## Current Status

| Variant | Change | Result |
| --- | --- | --- |
| P1 | AtmosProcessor render format: `5.1` -> `7.1` | Encoding succeeds, but the final stream remains `7.1 Height` |
| P2 | One Blu-ray internal configuration site: `19` -> `21` | Encoder pass crashes with an access violation |
| P1+P2 | P1 plus the single P2 configuration change | Same crash as P2 |
| P2+P3 | Paired internal configuration sites: `19` -> `21` | Generated, not yet tested |
| P1+P2+P3 | P1 plus paired P2/P3 changes | Generated, not yet tested |
| P3 only | Opposite single-site diagnostic mismatch | Generated; low-priority diagnostic build |

The successful P1 experiment proves that changing the AtmosProcessor render format alone does not change the final JOC coded layout. The `19` and `21` values are currently believed to belong to an internal Phoenix/spatial-coding configuration layer; there is no proof that `21` means flat 7.1.

The primary reverse-engineering target is now the downstream selector that chooses the final JOC coded/downmix layout among conceptual `5.X`, `7.X`, and `5.X+2` configurations.

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
|-- patch_logs/      Preserved P1, P2, and P1+P2 test logs
|-- example-flow/    Example Blu-ray DD+ Atmos job files
|-- gpt-context/     Reverse-engineering notes and context transfer
|-- dll_original/    Local original DLL; ignored by Git
|-- dll_patched/     Locally generated experimental DLLs; ignored by Git
|-- dee_copy/        Local DEE runtime copy; ignored by Git
`-- results/         Local encoded test outputs
```

Dolby binaries, licenses, and large test media are not part of the source distribution. Supply them from your own authorized installation.

## Generating the P1/P2 Variants

From the repository root, run:

```powershell
python .\patchers\make_dee_flat71_patches.py `
  .\dll_original\dee_audio_filter_ddp_atmos.dll `
  --out-dir .\dll_patched
```

This creates the P1, P2, and P1+P2 variants after validating the source DLL hash and original instruction bytes.

The newer `make_dee_cfg21_patches_v2.py` script creates the P2+P3, P1+P2+P3, and P3-only diagnostic variants next to the source DLL supplied to it. These builds remain unverified experiments.

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

See [CODEX_CONTEXT_TRANSFER.md](gpt-context/CODEX_CONTEXT_TRANSFER.md) for the complete findings, patch offsets, byte sequences, hashes, crash mapping, and recommended next investigation.

## Legal Notice

This repository is an independent research project and is not affiliated with or endorsed by Dolby Laboratories. Dolby, Dolby Atmos, and Dolby Encoding Engine are trademarks or products of their respective owner.

No proprietary Dolby software, license, or test media is granted by this project. You are responsible for complying with all applicable licenses, laws, and contractual restrictions when analyzing or modifying software.

## License

The original code and documentation in this repository are released under the [GNU General Public License v3.0](LICENSE). This license does not apply to third-party proprietary binaries or media.
