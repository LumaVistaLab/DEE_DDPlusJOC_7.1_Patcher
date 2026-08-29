# DD+ 7.1 Atmos Patcher for DEE

Language: English | [简体中文](README_zh-CN.md)

A validated binary-patch implementation and reverse-engineering project for Dolby Encoding Engine (DEE) 5.2.1. The paired P2+P3 implementation makes Blu-ray Dolby Digital Plus with Dolby Atmos (DD+ JOC) use this flat 7.1 coded/compatibility layout:

```text
L R C LFE Ls Rs Lrs Rrs
```

instead of the current Blu-ray `5.X+2` / `7.1 Height` layout:

```text
L R C LFE Ls Rs Tfl Tfr
```

This project does not target ordinary channel-based E-AC-3 7.1. The target is specifically a DD+ JOC / Dolby Atmos for Blu-ray bitstream with a flat 7.1 coded layout.

The supported end-to-end output workflow has two required stages: encode with
the validated P2+P3 DLL, then finalize the stream with the bundled
`DolbySurrEX-flag-patcher`. P2+P3 already creates the 5.1 Dolby PLIIx matrixed
compatibility core; the second stage supplies its missing Surround EX signaling.

> [!WARNING]
> This patch implementation is validated for one exact DEE 5.2.1 binary build and the encoding/decoding paths documented below. It is not claimed to be a general-purpose or production-ready patch. Always preserve the original binary.

## Validated Implementation Status

| Variant | Change | Result |
| --- | --- | --- |
| P1 | AtmosProcessor render format: `5.1` -> `7.1` | Encoding succeeds, but the final stream remains `7.1 Height` |
| P2 | One Blu-ray internal configuration site: `19` -> `21` | Encoder pass crashes with an access violation |
| P1+P2 | P1 plus the single P2 configuration change | Same crash as P2 |
| P2+P3 | Paired internal configuration sites: `19` -> `21` | **Validated implementation: flat 7.1 DD+ JOC (`L R C LFE Ls Rs Lb Rb`)** |
| P1+P2+P3 | P1 plus paired P2/P3 changes | Not tested; P2+P3 already reaches the target |
| P3 only | Opposite single-site diagnostic mismatch | Generated; low-priority diagnostic build |

The successful P1 experiment proves that changing the AtmosProcessor render format alone does not change the final JOC coded layout. The later P2+P3 experiment proves that both `19 -> 21` sites must change together: a single-site change creates inconsistent initialization and crashes, while the paired change produces the target flat 7.1 layout.

Automated static analysis also found a separate `0x0C / 0x0E / 0x10` three-state channel-mode mapping. Because P2+P3 already reaches the target, that candidate was neither modified nor dynamically tested.

## Formal end-to-end workflow

```text
ADM/DAMF master
  -> DEE 5.2.1 + validated P2+P3 DLL
  -> flat 7.1 DD+ JOC with a 5.1 PLIIx core (dsurexmod=0)
  -> DolbySurrEX-flag-patcher
  -> final flat 7.1 DD+ JOC (dsurexmod=2, AC-3 CRC updated)
```

`DolbySurrEX-flag-patcher` is therefore the formal finalization stage for this
project's validated output, not an optional way to create a different downmix.
It does not synthesize or alter the PLIIx matrix: that audio is already produced
by the P2+P3 encoding stage. It changes only the AC-3 core's `dsurexmod` field
from `0` to `2` and the corresponding CRC bytes. The E-AC-3 dependent/JOC frames
must remain byte-identical.

The flag patcher must only be used after the stream has been confirmed to carry
the PLIIx matrixed core. It is not a generic conversion for an arbitrary Lo/Ro
or conventional 5.1 stream.

## Playback Validation

The validated P2+P3 implementation was encoded with the automation-generated
40-second 9.1.6 channel-identification master. The resulting test stream was
`atmos916_flat71_P2P3_r03.eb3`, SHA-256
`de0536e1ec495404e5d1a91b82569c1e5ab1ccb8cb50fa2f4de631208906d354`.

| Validation path | Decoder | Result |
| --- | --- | --- |
| Flat 7.1 compatibility presentation and coded-channel rendering | LAV Audio Decoder 0.82.0 | **Passed:** the encoded 7.1 channels render in the intended `L R C LFE Ls Rs Lb Rb` arrangement |
| Dolby Atmos presentation and spatial rendering | Dolby Media Decoder v3.2.0 | **Passed:** the 9.1.6 test positions render correctly in the Dolby Atmos presentation |

These playback results complete both intended validations: the flat 7.1 coded
compatibility layer and the Dolby Atmos spatial presentation. The scope remains
the exact DEE build, patch, test stream, and decoder versions stated here.

## 5.1 Dolby PLIIx core validation

The same 40-second P2+P3 stream was split into its 640 kb/s AC-3 compatibility
core and E-AC-3 dependent/JOC frames. FFmpeg decoding of the AC-3 core was then
measured against the isolated `Lss`, `Rss`, `Lrs`, and `Rrs` events in the test
master. The measured 7.1-to-5.1 coefficients match the Dolby-documented PLIIx
matrix within 0.254 dB:

| Matrix path | Documented | Measured |
| --- | ---: | ---: |
| Lrs -> Ls | -1.2 dB | -1.447 dB |
| Lrs -> Rs | -6.2 dB | -6.447 dB |
| Rrs -> Ls | -6.2 dB | -6.454 dB |
| Rrs -> Rs | -1.2 dB | -1.454 dB |

Both rear events also preserve the positive-sum polarity of the documented
equations. This validates that the P2+P3 output contains a 5.1 Dolby PLIIx
matrixed compatibility core; P1 is not required for this result.

The encoder leaves the AC-3 `dsurexmod` metadata at `0` (not indicated).
Accordingly, the formal workflow finishes the encoded stream with the bundled
Surround EX postprocessor. It changes the flag to `2` in all 1,250 core frames,
recomputes valid CRCs, and leaves all 1,250 dependent/JOC frames byte-identical.
The resulting stream remains flat 7.1 DD+ Atmos and MediaInfo reports Dolby
Surround EX. See [PLIIx findings](automation/PLIIX_FINDINGS.md) for hashes,
measurements, and limits of the conclusion.

## Downmix phase and Blu-ray preprocessing behavior

Binary control-flow analysis and decoded-core measurements distinguish the
7.1-to-5.1 matrix from the preprocessing used for later 5.1-to-2.0
compatibility:

| Scope | Validated behavior |
| --- | --- |
| PLIIx 7.1-to-5.1 matrix | The coefficient matrix itself is phase-neutral. Each isolated `Lrs` or `Rrs` contribution reaches its two `Ls`/`Rs` destinations at 0.0 degrees relative phase. |
| Encoded 5.1 AC-3 core | The encoder applies one Surround Phase Shift to the surround channels. After compensating the common 256-sample codec delay, `Lss`, `Rss`, `Lrs`, and `Rrs` measure from -88.402 to -90.448 degrees relative to the source. |
| Streaming Preferred Stereo Downmix | Selecting Pro Logic II corresponds to `Lt/Rt (Pro Logic II) w/Phase 90`; this path owns the single required 5.1-to-2.0 surround phase rotation. |
| Blu-ray Preferred Stereo Downmix | Blu-ray permits Lo/Ro or traditional Lt/Rt, with Lo/Ro retained as this project's default. It rejects the Pro Logic II selector (`ltrt-pl2`). The bitstream encoder's Surround Phase Shift preprocessing supplies the phase rotation independently of that preference. |
| LFE lowpass filter | Enabled by default and passed to the encoder in the Blu-ray Atmos path. It is the Dolby 120 Hz, eighth-order preprocessing filter. |
| Surround 3 dB attenuation | The ordinary DD+ encoder initializes this option to enabled, but an Atmos input with a Trim Mode Record overrides the generic switch. The current master has `Surround trim: 0 dB` for every layout, so no additional 3 dB attenuation is effective. A different Atmos master follows its own Trim Mode Record. |

The current `encode_to_atmos_ddp` job therefore intentionally keeps
`preferred_downmix_mode=loro`. Its XML does not expose the LFE-lowpass,
Surround-Phase-Shift, or surround-attenuation switches used by the ordinary PCM
DD+ encoder. LFE filtering remains enabled internally, the surround phase shift
is observable in the coded core, and surround attenuation is taken from the
Atmos master rather than forced to -3 dB.

This separation prevents two incorrect interpretations: the -90-degree result
must not be attributed to the PLIIx 7.1-to-5.1 coefficient matrix, and the
ordinary DD+ `surround_3db_attenuation=true` default must not be treated as an
effective -3 dB trim for every Atmos master. See
[phase-shift findings](automation/PHASE_SHIFT_FINDINGS.md) for the binary
addresses, per-channel measurements, and profile mapping. Dolby's descriptions
of these controls are available in [A Guide to Dolby Metadata](https://professionalsupport.dolby.com/s/article/A-Guide-to-Dolby-Metadata?language=en_US)
and [How the 5.1 and stereo downmix settings work](https://professionalsupport.dolby.com/s/article/How-do-the-5-1-and-Stereo-downmix-settings-work?language=en_US).

## Requirements

- A legally obtained Dolby Encoding Engine 5.2.1 installation and valid license
- The exact supported `dee_audio_filter_ddp_atmos.dll` build
- Python 3
- NumPy and FFmpeg for decoded-core PLIIx coefficient analysis
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
|-- patchers/                            Patch-generation scripts
|-- DolbySurrEX-flag-patcher-2966e09/   Formal dsurexmod/CRC finalization stage
|-- automation/                          Isolated build, reverse, test, and validation scripts
|-- patch_logs/                          Preserved complete test logs
|-- example-flow/                        Example Blu-ray DD+ Atmos job files
|-- gpt-context/                         Reverse-engineering notes and context transfer
|-- dll_original/                        Local original DLL; ignored by Git
|-- dll_patched/                         Locally generated patched DLLs; ignored by Git
|-- dee_copy/                            Local DEE runtime copy; ignored by Git
`-- results/                             Local encoded test outputs
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
python .\automation\pliix_core_analysis.py `
  .\results\atmos916_flat71_P2P3_r03.eb3 `
  --schedule .\automation\work\test_audio\atmos_916_channel_id_adm.wav.json `
  --output-dir .\automation\evidence\pliix\atmos916_flat71_P2P3
python .\DolbySurrEX-flag-patcher-2966e09\patch_dsur_ex.py --check `
  .\results\atmos916_flat71_P2P3_r03.eb3
python .\DolbySurrEX-flag-patcher-2966e09\patch_dsur_ex.py `
  .\results\atmos916_flat71_P2P3_r03.eb3 `
  .\results\atmos916_flat71_P2P3_r03.dsur-ex.eb3
python .\DolbySurrEX-flag-patcher-2966e09\patch_dsur_ex.py --check `
  .\results\atmos916_flat71_P2P3_r03.dsur-ex.eb3
python .\automation\validate.py stream `
  .\results\atmos916_flat71_P2P3_r03.dsur-ex.eb3
```

The encoding automation never edits `example-flow`, never overwrites retained
evidence, and preserves every declared output, including zero-byte crash
outputs. PLIIx core analysis is read-only. Surround EX finalization remains an
explicit, separately auditable invocation of `patch_dsur_ex.py`, but it is the
required second stage of the formal validated workflow. The preflight and final
checks must pass, and validation must confirm that dependent/JOC frames did not
change.

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
- LAV Audio Decoder 0.82.0 playback verifies correct flat 7.1 compatibility-presentation coded-channel rendering.
- Dolby Media Decoder v3.2.0 playback verifies correct Dolby Atmos spatial rendering of the 9.1.6 channel-identification stream.
- Formal Surround EX finalization produces the 8,320,000-byte stream `atmos916_flat71_P2P3_r03.dsur-ex.eb3`, SHA-256 `28042cc8d51c23f6f63345771685f9c04cb188e02f0c355b174f5c0f088b90ad`. All 1,250 AC-3 core frames carry `dsurexmod=2` with valid CRCs, while all 1,250 dependent/JOC frames remain byte-identical.
- The complete `example-flow` file-hash manifest is unchanged before and after the automated run.

See [CODEX_CONTEXT_TRANSFER.md](gpt-context/CODEX_CONTEXT_TRANSFER.md) for
historical research context, [the automated flat-7.1 findings](automation/FLAT71_FINDINGS.md)
for the validated implementation result, [the PLIIx findings](automation/PLIIX_FINDINGS.md)
for the matrix and finalization evidence, [the Surround EX patcher guide](DolbySurrEX-flag-patcher-2966e09/README.md)
for tool-specific safeguards, and [the complete P2+P3 log](patch_logs/flat71_P2P3.log).

## Legal Notice

This repository is an independent research project and is not affiliated with or endorsed by Dolby Laboratories. Dolby, Dolby Atmos, and Dolby Encoding Engine are trademarks or products of their respective owner.

No proprietary Dolby software, license, or test media is granted by this project. You are responsible for complying with all applicable licenses, laws, and contractual restrictions when analyzing or modifying software.

## License

The original code and documentation in this repository are released under the [GNU General Public License v3.0](LICENSE). This license does not apply to third-party proprietary binaries or media.
