# 7.1-to-5.1 and 5.1-to-2.0 phase-shift findings

Date: 2026-08-29

## Result

The current P2+P3 DD+ JOC chain has two distinct phase-related behaviors:

| Scope | Result |
| --- | --- |
| PLIIx 7.1-to-5.1 matrix itself | No differential 90-degree shift. The Lrs contribution reaches Ls and Rs at 0.0 degrees relative phase; the same is true for Rrs. The matrix uses real, positive coefficients. |
| Final encoded 5.1 AC-3 core | Yes. After removal of the common 256-sample codec delay, all isolated Lss/Rss/Lrs/Rrs signals in the coded Ls/Rs channels measure approximately -90 degrees relative to the generated source. |
| 5.1-to-2.0 compatibility path | Yes: one 90-degree surround shift is required. In the tested Blu-ray output it is realized by the bitstream encoder's Surround Phase Shift preprocessing, including when Preferred Stereo Downmix remains at the Lo/Ro default; it is not owned by the Atmos `51-to-20...` flag. |

Therefore, the final 5.1 compatibility core already contains the single required
phase rotation for a later 5.1-to-2.0 downmix. The rotation is not a differential term
in the PLIIx 7.1-to-5.1 coefficient matrix, and the two available profile paths
must not both apply it to the same signal.

## Binary behavior

The original `dee_audio_filter_ddp_atmos.dll` keeps these as separate DBMD fields:

```text
downmix_type_7to5
downmix_type_5to2
phaseshift_90deg_5to2
51-to-20_LsRs90degPhaseShift
```

References to `51-to-20_LsRs90degPhaseShift` occur in functions beginning at
virtual addresses `0x1804B5690` and `0x1804BBA00`. The phase-value conversion and
validation path begins at `0x1804DCA80`; its invalid-value diagnostic explicitly
says `Invalid phase shift enable flag for 5.0 to 2.0 downmix`. The
`downmix_type_7to5` field is separately parsed and serialized. This rules out the
DBMD Phase90 flag being an implicit part of the 7-to-5 selector.

The ordinary DD/DD+ encoder DLLs and XML templates also expose a separate
`surround_90_degree_phase_shift` preprocessing option. Dolby's supplied
`pcm_to_ddp` templates set it to `true`. The current `encode_to_atmos_ddp` XML
schema does not expose that element, but the decoded signal proves that the
surround preprocessing is active in the tested output. This matches Dolby's
documented default of Enable for the bitstream encoder's Surround Phase Shift.

The binary also contains a Blu-ray-mode guard at `0x18017BFC0` that reports
`Preferred Downmix mode Pro Logic II is not supported in Blu-ray Mode` when the
PLII stereo preference is selected in that path. This does not prohibit Lo/Ro
or traditional Lt/Rt. The current Blu-ray workflow keeps its default
`preferred_downmix_mode=loro`.

Reverse-analysis evidence:

```text
automation/evidence/reverse/20260829-173422_3d66bcec3603/analysis.json
```

## Source metadata

Converting the generated ADM BWF to a temporary DAMF representation exposed the
metadata without altering it:

```yaml
downmixType_5to2: LoRo_Stereo
51-to-20_LsRs90degPhaseShift: false
warpMode: LoRo

atmos:
  downmix_type_5to2: lo_ro
  downmix_type_7to5: not_indicated
```

The temporary DAMF audio and ADM conversion copies were not retained because
they duplicated approximately 184 MB of PCM data.

## Decoded-signal measurement

Source stream:

```text
results/atmos916_flat71_P2P3_r03.eb3
SHA-256: de0536e1ec495404e5d1a91b82569c1e5ab1ccb8cb50fa2f4de631208906d354
```

The test generator creates absolute-time, zero-phase sine tones. Direct L/R/C
events were used to estimate a shared encoder/decoder delay of exactly 256
samples. Applying that same correction to all events produced:

| Source event | Coded core channel | Residual phase |
| --- | --- | ---: |
| L | L | +0.094 degrees |
| R | R | +0.082 degrees |
| C | C | +0.071 degrees |
| Lss | Ls | -88.402 degrees |
| Rss | Rs | -89.709 degrees |
| Lrs | Ls | -88.703 degrees |
| Rrs | Rs | -90.448 degrees |

The maximum surround error from -90 degrees is 1.598 degrees. The automated
verdict is:

```text
surround_90_degree_phase_shift_observed
```

Machine-readable evidence:

```text
automation/evidence/pliix/atmos916_flat71_P2P3_r03_phase/analysis.json
```

## Profile mapping and interpretation boundary

Dolby documents two related but separate controls. The project applies them as
profile-specific implementations of one invariant: the 5.1-to-2.0 compatibility
chain gets one surround 90-degree shift, never zero and never two.

- Streaming profile: `Preferred Stereo Downmix = Pro Logic II` maps to
  `Lt/Rt (Pro Logic II) w/Phase 90`; the Atmos 5.1-to-2.0 path owns the shift.
- Blu-ray profile: `Preferred Stereo Downmix` may be Lo/Ro or traditional Lt/Rt,
  but `ltrt-pl2` is rejected. The default remains Lo/Ro. The Dolby bitstream
  encoder's Surround Phase Shift preprocessing owns the phase rotation and is
  observable in this core.
- The tested source metadata still reports `LoRo_Stereo` and
  `51-to-20_LsRs90degPhaseShift: false`. That only says the source-side Atmos
  Phase90 path did not own this encode's shift; it does not negate the observed
  encoder preprocessing.

Consequently, a decoder downmixing this AC-3 core inherits the already rotated
Ls/Rs audio and must not add a second phase filter. The stream itself contains
5.1 core audio, not a materialized 2.0 render.

## Blu-ray preference constraint

`example-flow/atmos_mezz_encode_to_atmos_ddp_ec3.xml` selects the default Lo/Ro
preference under `encoder_mode=bluray`. A unit test locks that default and
prevents accidental use of the Blu-ray-incompatible `ltrt-pl2` selector. A
traditional `ltrt` preference remains a valid intentional alternative.

Dolby references:

- https://professionalsupport.dolby.com/s/article/A-Guide-to-Dolby-Metadata?language=en_US
- https://professionalsupport.dolby.com/s/article/How-do-the-5-1-and-Stereo-downmix-settings-work?language=en_US
