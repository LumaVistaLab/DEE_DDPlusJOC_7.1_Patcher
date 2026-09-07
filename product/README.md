# DD+ 7.1 Atmos Wrapper for Dolby Encoding Engine

English | [简体中文](README_zh-CN.md)

Filename: `dee-ddp71-atmos-wrapper.py`

Product version: `0.2.0-dev`

This is the derivative product of this repository's validated reverse-engineering work. It is the first single-command Dolby Encoding Engine (DEE) v5.2.1 CLI wrapper for modern DD+ Atmos for Blu-ray encoding that lets users select either compatibility-presentation coded-channel layout:

- `5.1+2` / `7.1 Height`: `L R C LFE Ls Rs Lvh Rvh` (some analyzers label the last pair `Tfl Tfr`).
- Flat `7.1`: `L R C LFE Ls Rs Lrs Rrs` (some analyzers label the last pair `Lb Rb`).

The product turns the reverse-engineering result into a complete end-to-end production workflow. It does not directly rewrite coded-channel labels in a finished bitstream, require a specially authored ADM BWF for flat 7.1, or depend on the legacy Dolby Media Producer Suite v2.0 workflow. The input must still be a valid Dolby Atmos mezzanine accepted by the original `atmos_mezz_encode_to_atmos_ddp_ec3.xml` workflow.

> This is currently a development version and supports one exact verified build of `dee_audio_filter_ddp_atmos.dll`. Its original SHA-256 must be `3d66bcec36031fd48e6565d15f05fea656642377ca4f8c98cdce1cce8b7e95d2`.

## Requirements

- Windows and Python 3.10 or later.
- A legally obtained and licensed complete Dolby Encoding Engine v5.2.1 installation.
- `dee.exe`, `dee_audio_filter_ddp_atmos.dll`, and a valid license in the DEE installation.
- A valid Dolby Atmos mezzanine input.

No Dolby proprietary binaries, licenses, or test media are distributed here.

## One-command usage

This version has no multi-step subcommands. One invocation takes the DEE path, input path, output path, then optional overrides, and performs backup, job generation, conditional binary patching, encoding, conditional EX signaling, and restoration:

```powershell
python .\dee-ddp71-atmos-wrapper.py <DEE-directory-or-dee.exe> <input> <output> [overrides]
```

Show built-in help:

```powershell
python .\dee-ddp71-atmos-wrapper.py --help
```

Minimal 5.1+2 encode:

```powershell
python .\dee-ddp71-atmos-wrapper.py `
  "C:\Program Files\Dolby\Dolby Encoding Engine" `
  "D:\masters\feature.atmos" `
  "D:\encodes\feature.eb3"
```

Flat-7.1 encode:

```powershell
python .\dee-ddp71-atmos-wrapper.py `
  "C:\Program Files\Dolby\Dolby Encoding Engine\dee.exe" `
  "D:\masters\feature.wav" `
  "D:\encodes\feature-flat71.eb3" `
  --compatibility-layout flat-7.1
```

Custom dialnorm and data rate:

```powershell
python .\dee-ddp71-atmos-wrapper.py `
  "C:\DEE-5.2.1" "D:\masters\feature.wav" "D:\encodes\feature.eb3" `
  --custom-dialnorm -27 `
  --data-rate 1664
```

Validate, back up, and generate XML without modifying or starting DEE:

```powershell
python .\dee-ddp71-atmos-wrapper.py `
  "C:\DEE-5.2.1" "D:\masters\feature.wav" "D:\encodes\feature.eb3" `
  --compatibility-layout flat-7.1 `
  --dry-run
```

## Template defaults and fixed wrapper behavior

- `<encoding_backend>atmosprocessor</encoding_backend>` is fixed and cannot be overridden.
- `<encoder_mode>bluray</encoder_mode>` is fixed and cannot be overridden.
- Defaults for XML parameters come from `templates/atmos_mezz_encode_to_atmos_ddp_ec3.xml`, so they can be customized in one place. CLI options override those template values for the current run.
- The bundled template sets `<data_rate>` to `1152`.
- The bundled template sets `<preferred_downmix_mode>` to `loro`. For `5.1+2`, that value is retained when no CLI override is supplied; for `flat-7.1`, wrapper switching logic selects `ltrt`. An explicit CLI value wins in either layout.
- The compatibility-layout switch, generated paths, fixed Blu-ray backend/mode, and other behavior that is not an XML parameter remain implemented by the wrapper.

## Category 1: original XML overrides

The options are listed in original XML order. Every item is optional.

| CLI option | XML parameter | Accepted input | Bundled template/wrapper behavior |
| --- | --- | --- | --- |
| `--input-timecode-frame-rate` | input `<timecode_frame_rate>` | `not_indicated`, `23.976`, `24`, `25`, `29.97`, `30`, `48`, `50`, `59.94`, `60` | `not_indicated` |
| `--input-offset` | `<offset>` | `auto`, `HH:MM:SS:FF`, `HH:MM:SS.xx`, or decimal seconds | `auto` |
| `--input-ffoa` | `<ffoa>` | `auto`, `HH:MM:SS:FF`, `HH:MM:SS.xx`, or decimal seconds | `auto` |
| `--metering-mode` | `<metering_mode>` | `1770-4`, `1770-3`, `1770-2`, `1770-1`, `LeqA` | `1770-4` |
| `--dialogue-intelligence` | `<dialogue_intelligence>` | `true`, `false` | `true` |
| `--speech-threshold` | `<speech_threshold>` | integer `0` through `100` | `15` |
| `--data-rate` | `<data_rate>` | `1152`, `1280`, `1408`, `1512`, `1536`, `1664` | bundled template value `1152` |
| `--timecode-frame-rate` | filter `<timecode_frame_rate>` | `not_indicated`, `23.976`, `24`, `25`, `29.97`, `30`, `48`, `50`, `59.94`, `60` | `not_indicated` |
| `--start` | `<start>` | `first_frame_of_action`, timecode, decimal seconds, or video-frame number | `first_frame_of_action`; incompatible with segmented batch mode |
| `--end` | `<end>` | `end_of_file`, timecode, decimal seconds, or video-frame number | `end_of_file`; incompatible with segmented batch mode |
| `--time-base` | `<time_base>` | `file_position`, `embedded_timecode` | `file_position` |
| `--prepend-silence-duration` | `<prepend_silence_duration>` | nonnegative decimal seconds or frames such as `12f` | `0.0` |
| `--append-silence-duration` | `<append_silence_duration>` | nonnegative decimal seconds or frames such as `12f` | `0.0` |
| `--line-mode-drc-profile` | `<line_mode_drc_profile>` | `film_standard`, `film_light`, `music_standard`, `music_light`, `speech`, `none` | `film_light` |
| `--rf-mode-drc-profile` | `<rf_mode_drc_profile>` | same as above | `film_light` |
| `--loro-center-mix-level` | `<loro_center_mix_level>` | `+3`, `+1.5`, `0`, `-1.5`, `-3`, `-4.5`, `-6`, `-inf` | `-3` |
| `--loro-surround-mix-level` | `<loro_surround_mix_level>` | `-1.5`, `-3`, `-4.5`, `-6`, `-inf` | `-3` |
| `--ltrt-center-mix-level` | `<ltrt_center_mix_level>` | `+3`, `+1.5`, `0`, `-1.5`, `-3`, `-4.5`, `-6`, `-inf` | `-3` |
| `--ltrt-surround-mix-level` | `<ltrt_surround_mix_level>` | `-1.5`, `-3`, `-4.5`, `-6`, `-inf` | `-3` |
| `--preferred-downmix-mode` | `<preferred_downmix_mode>` | Blu-ray-valid `loro`, `ltrt` | follows the layout rules above; Blu-ray mode does not support `ltrt-pl2` |
| `--surround-trim-5-1` | `<surround_trim_5_1>` | `0`, `-3`, `-6`, `-9`, `auto` | `auto` |
| `--height-trim-5-1` | `<height_trim_5_1>` | `-3`, `-6`, `-9`, `-12`, `auto` | `auto` |
| `--clean-temp` | `<clean_temp>` | `true`, `false` | `true` |
| `--temp-dir` | `<temp_dir><path>` | valid directory path | defaults to `temp` inside the run directory |

`--input-timecode-frame-rate` controls input-mezzanine `offset`/`ffoa`; `--timecode-frame-rate` controls filter `start`/`end`. They are distinct XML parameters.

## Category 2: wrapper extensions

| CLI option | Accepted input | Effect |
| --- | --- | --- |
| `--custom-dialnorm` | integer `-31` through `0` | writes `<custom_dialnorm>`; `0` means no measured-value override |
| `--segmented-batch` | flag | explicitly enables N-point/N+1-job batch encoding |
| `--segment-start` | `first_frame_of_action`, `file_start` | logical first-job start; `file_start` is translated according to `--time-base`, matching DME v3.7 |
| `--segment-point` | `HH:MM:SS:FF` | repeat N times in strict ascending order; values are passed unchanged to adjacent jobs |
| `--compatibility-layout` | `5.1+2`, `flat-7.1` | coded compatibility layout; default `5.1+2` |

Operational helpers: `--license-file <path>` selects a license outside the DEE directory; otherwise adjacent `license.lic` is used. The wrapper stages it temporarily through a conservative path because DEE 5.2.1 cannot open a license whose own path contains some Windows-valid special characters. `--overwrite` permits replacing requested outputs; `--dry-run` stops after backup, validation, and XML generation.

## Segmented batch encoding

Segmented mode requires `--segmented-batch`, explicit `--timecode-frame-rate`, explicit `--time-base`, explicit `--segment-start`, and at least one `--segment-point`.

Two points producing three jobs:

```powershell
python .\dee-ddp71-atmos-wrapper.py `
  "C:\DEE-5.2.1" "D:\masters\feature.wav" "D:\encodes\feature.eb3" `
  --compatibility-layout flat-7.1 `
  --segmented-batch `
  --timecode-frame-rate 24 `
  --time-base file_position `
  --segment-start file_start `
  --segment-point 00:20:00:00 `
  --segment-point 00:40:00:00
```

Outputs:

```text
feature.part001of003.eb3
feature.part002of003.eb3
feature.part003of003.eb3
```

Each segment is finalized and atomically published to its requested output path before the next DEE job starts. If a later segment fails or the batch is interrupted, every earlier published segment remains available; the failed or not-yet-started segment is not published.

Range rules:

1. First `<start>` is `first_frame_of_action`; for `file_start`, it is video-frame number `0` with `file_position`, or the input source timecode/offset with `embedded_timecode`.
2. Every later `<start>` is the corresponding point.
3. Every nonfinal `<end>` is the next point.
4. Final `<end>` is always `end_of_file`.
5. N points submit N+1 sequential DEE jobs.

The segmentation coordinate has two independent parts. `--timecode-frame-rate` is the video-timecode rate used to interpret filter `<start>`/`<end>`, including every `--segment-point`; it is not the audio sample rate. `--input-timecode-frame-rate` instead belongs to the input `offset`/`ffoa`. `--time-base` selects the origin used for the segment points:

| `--time-base` | Meaning of `--segment-point` | `file_start` written to first `<start>` |
| --- | --- | --- |
| `file_position` | elapsed position from the physical file beginning | video-frame number `0` |
| `embedded_timecode` | absolute source timecode on the input timeline | input source timecode/offset |

This `file_start` behavior matches DME v3.7: changing Time base from File position to Source timecode changes Start from `00:00:00:00` to the input source timecode rather than leaving it at zero. With `offset=auto`, the wrapper runs the `atmos_info.exe` bundled beside DEE 5.2.1 to read the Atmos master start in absolute seconds, then expresses that position using the filter `--timecode-frame-rate`. AtmosInfo's source video frame rate does not have to match the filter rate: the input and filter timecode rates have separate roles. At any supported 1000/1001 nondrop filter rate—23.976, 29.97, or 59.94—`3603.6` seconds maps to `01:00:00:00`. If an absolute-second position is not on the selected filter frame grid, the wrapper emits DEE's frame-rate-independent `HH:MM:SS.xx` form instead of rounding it. If AtmosInfo cannot report the start, the wrapper stops and asks for an explicit `--input-offset`; it never emits an invalid zero start. A frame-form `--input-offset` requires an explicit `--input-timecode-frame-rate`, but that input rate may differ from the filter rate; the wrapper converts between their time domains.

For example, if a 59.94-fps nondrop master begins at source timecode `01:00:00:00`, source-timecode segmentation uses the absolute timeline values directly:

```powershell
python .\dee-ddp71-atmos-wrapper.py `
  "C:\DEE-5.2.1" "D:\masters\feature.wav" "D:\encodes\feature.eb3" `
  --segmented-batch `
  --timecode-frame-rate 59.94 `
  --time-base embedded_timecode `
  --segment-start file_start `
  --segment-point 01:20:00:00 `
  --segment-point 01:40:00:00
```

The wrapper passes all `--segment-point` values unchanged to adjacent jobs. DEE timecode ranges are start-inclusive and end-exclusive, so using the same point as one job's `<end>` and the next job's `<start>` creates adjacent timecode ranges without duplicating that boundary frame. Points are not translated to audio frames, access units, or other encoded boundaries. The current `HH:MM:SS:FF` segment syntax is nondrop only and does not accept DEE's `df` suffix. Joining, muxing, seamlessness, A/V sync, and delivery still require separate QC. To encode only a target excerpt, generate the segmented set through this same entry point and retain the desired part afterward.

## Binary patching, backup, and restoration

Before any potentially patched binary is changed, every run:

1. locks the DEE installation against another wrapper process;
2. validates the exact SHA-256 of `dee_audio_filter_ddp_atmos.dll`;
3. backs up the original component under `backups/<installation-id>/` and verifies it;
4. validates the P2+P3 byte assertions and expected patched hash in memory.

`5.1+2` never installs a DEE patch. `flat-7.1` atomically installs the paired P2+P3 patch. After all DEE jobs complete, fail, or are normally interrupted, the original component is restored from the verified backup and its hash is checked. If power loss or forced process termination prevented `finally` from running, a later invocation detects the exact known patched hash and restores it before proceeding, provided the verified backup exists. Unknown component hashes are rejected rather than overwritten.

DEE 5.2.1's own plugin loader cannot initialize some audio filters when the installation pathname contains otherwise Windows-valid Unicode or punctuation. When such a path is detected, the wrapper copies the executable-directory runtime files to a conservative disposable directory under the current run, patches and executes only that stage, restores its DLL, and removes the stage afterward. The user-supplied DEE package remains at the requested special-character path and is never patched in this compatibility mode.

The generated XML always records the complete input, output, and temporary paths. When starting DEE, the wrapper also supplies explicit `-a`, `-o`, and `--temp` options, matching the original example batch file. This avoids DEE 5.2.1's XML local-storage parser truncating a path at its first space without changing XML parameters or segment boundaries. Component restoration and disposable-runtime cleanup use bounded retries for file handles that Windows may retain briefly after an abnormal DEE exit.

Generated job XML, logs, intermediate streams, and the run manifest are under `work/runs/<run-id>/`. Product-local `.gitignore` excludes `backups/` and `work/`.

## Independent Surround EX finalization

If and only if `flat-7.1` is selected, the main workflow invokes [tools/patch_dsur_ex.py](tools/patch_dsur_ex.py) as a separate process after the original DEE component has already been restored. The tool only sets `dsurexmod=2` in the AC-3 core and recalculates the affected CRC values. It does not change dependent/JOC frames and does not create the flat-7.1 layout.

The script remains independent for future updates and auditing. Pinned source:

- Project: [LumaVistaLab/DolbySurrEX-flag-patcher](https://github.com/LumaVistaLab/DolbySurrEX-flag-patcher)
- Commit: `2966e09` (the repository reference directory is `DolbySurrEX-flag-patcher-2966e09`)
- Separate guide: [English](tools/README.md) / [中文](tools/README_zh-CN.md)

## Category 3: temporarily unsupported

The current CLI deliberately has no controls for:

- LFE low-pass filter enable/disable;
- 3 dB surround attenuation enable/disable;
- 90-degree surround phase-shift enable/disable.

These retain the existing behavior of the validated DEE Blu-ray Atmos path and the master Trim Mode Record.

## Development verification

```powershell
python -m py_compile .\dee-ddp71-atmos-wrapper.py .\tools\patch_dsur_ex.py
python -m unittest discover -s .\tests -v
```

See [VALIDATION.md](VALIDATION.md) for the 2026-09-06 absolute/relative real-encoding validation through Windows-valid special-character paths.

Development changes belong only in this `product` directory. Other repository directories are read-only reverse-engineering, sample, and test references; `release` retains the latest local packaged snapshot and is not a development workspace.

## Legal notice and license

This derivative implementation is an independent reverse-engineering project. It is not affiliated with or endorsed by Dolby Laboratories. Dolby, Dolby Atmos, Dolby Digital Plus, and Dolby Encoding Engine are trademarks or products of their respective owner. Users are responsible for complying with applicable software licenses, laws, and contractual restrictions.

Original product code, documentation, and the independent Surround EX tool are licensed under the [GNU General Public License v3.0](LICENSE). This license does not cover Dolby proprietary software, licenses, or user media.
