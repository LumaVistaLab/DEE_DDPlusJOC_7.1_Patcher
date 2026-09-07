# Real encoding through special-character paths

Validation date: 2026-09-06  
Internal version: `0.1.0-dev`
Encoder: Dolby Encoding Engine `5.2.1-5994839`

## Scope

A temporary DEE package containing 85 files and 810,751,824 bytes was created under `product/work/` from `dee_copy`. Its directory intentionally combines Unicode, spaces, `[]`, `+`, `&`, `'`, `#`, `,`, `;`, `=`, `!`, `@`, `%`, and `()`:

```text
work/路径验证 [Win+&' #,;=!@%]/DEE v5.2.1 临时包 [A+B] &(原版)' #,;=!@%
```

The original `dee_audio_filter_ddp_atmos.dll` in that package has SHA-256:

```text
3d66bcec36031fd48e6565d15f05fea656642377ca4f8c98cdce1cce8b7e95d2
```

Flat-7.1 segmented encoding was run once with absolute paths and once with relative paths. Both runs used:

- `timecode_frame_rate=24`;
- `time_base=file_position`;
- first-segment `start=0` (`file_start`);
- split points `00:00:10:00`, `00:00:20:00`, and `00:00:30:00`;
- `compatibility_layout=flat-7.1`;
- default `data_rate=1152` and `preferred_downmix_mode=ltrt`.

Absolute-path manifest: `work/runs/20260906-232420-573c8c10/run.json`.  
Relative-path manifest: `work/runs/20260906-232726-50d2fdc9/run.json`.

The relative test started in `product` and supplied the wrapper script, DEE directory, master, and output base as relative paths. All four were absolute in the absolute-path test.

## XML boundaries

The four generated jobs were identical between the two runs:

| Part | `<start>` | `<end>` |
|---:|---|---|
| 1 | `0` | `00:00:10:00` |
| 2 | `00:00:10:00` | `00:00:20:00` |
| 3 | `00:00:20:00` | `00:00:30:00` |
| 4 | `00:00:30:00` | `end_of_file` |

## Output identity and structure

Corresponding absolute and relative outputs were byte-identical:

| Part | Bytes | SHA-256 | AC-3 core frames | E-AC-3 dependent frames |
|---:|---:|---|---:|---:|
| 1 | 1,442,304 | `1fcde1061c8b8b20ecff33af6104bc3f74865f9475230bf8443bbb7011d84c2d` | 313 | 313 |
| 2 | 1,442,304 | `384acfd3f8c106a90be8e425ecd6b87a009a4b5cda8b21222a7d296ad96fcff5` | 313 | 313 |
| 3 | 1,442,304 | `ec48308f4a2f8ad4186833c3f4106dac0150b52ecee4e6b99588cd8bad550e8f` | 313 | 313 |
| 4 | 33,564,672 | `477e8ff735a68844a62226ae75f25ca3ec0c7ea87e6126d1025909edc745c85f` | 7,284 | 7,284 |

Independent `patch_dsur_ex.py --check` validation of all eight files found:

- `dsurexmod=2` in every AC-3 core frame;
- zero AC-3 CRC mismatches in every file;
- 2,304-byte core and dependent frames throughout;
- `ffprobe` reported `eac3`, `Dolby Digital Plus + Dolby Atmos`, eight channels, `7.1`, 48 kHz, and 1,152,000 bit/s for all four unique outputs;
- MediaInfo reported `Blu-ray Disc`, `L R C LFE Ls Rs Lb Rb`, and `Dolby Surround EX` for every part. Its commercial name included `with Dolby Atmos` only for parts 1 and 4, while `ffprobe` and frame scanning identified Atmos dependent/JOC data in all four parts.

## Restoration result

Both manifests have `status=complete`, `safe_runtime_stage_removed=true`, and the original restored DLL hash. A final read of the source package at the special-character path still returned `3d66bcec...e95d2`; that source package was never patched.

Validation used a normal Windows process context. The proprietary encoder plugins all return Windows error 1114 inside the restricted test sandbox, while the same `dee_copy --print-stages` exits successfully in a normal process context; that condition is therefore not a path or wrapper failure.
