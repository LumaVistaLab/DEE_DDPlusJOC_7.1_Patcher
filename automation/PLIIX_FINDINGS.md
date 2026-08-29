# Validated 5.1 Dolby PLIIx compatibility core

Date: 2026-08-29

## Result

The already validated P2+P3 flat-7.1 DD+ JOC stream contains a 5.1 AC-3
compatibility core whose isolated rear-surround signals match the documented
Dolby PLIIx 7.1-to-5.1 matrix. P1 is not required for this result.

Source stream:

```text
results/atmos916_flat71_P2P3_r03.eb3
SHA-256: de0536e1ec495404e5d1a91b82569c1e5ab1ccb8cb50fa2f4de631208906d354
Size: 8,320,000 bytes
```

The stream contains 1,250 AC-3 core frames of 2,560 bytes and 1,250 E-AC-3
dependent/JOC frames of 4,096 bytes, with no trailing bytes. The AC-3 frames are
5.1+LFE (`acmod=7`, `lfeon=1`) at 640 kb/s. MediaInfo reports the complete stream
as eight-channel Dolby Digital Plus with Dolby Atmos, flat layout
`L R C LFE Ls Rs Lb Rb`.

## Signal measurement

`pliix_core_analysis.py` extracted the AC-3 frames, decoded them with FFmpeg
7.1.1 to `L R C LFE Ls Rs`, and measured the steady-state fundamental of the
isolated 9.1.6 identification events. The generated source uses identical
amplitudes for `Lss`, `Rss`, `Lrs`, and `Rrs`.

The Dolby Media Encoder manual documents these PLIIx coefficients:

```text
Ls = Lss + (-1.2 dB x Lrs) + (-6.2 dB x Rrs)
Rs = Rss + (-6.2 dB x Lrs) + (-1.2 dB x Rrs)
```

Measured results:

| Matrix path | Expected | Observed | Error |
| --- | ---: | ---: | ---: |
| Lrs -> Ls | -1.2 dB | -1.447 dB | -0.247 dB |
| Lrs -> Rs | -6.2 dB | -6.447 dB | -0.247 dB |
| Rrs -> Ls | -6.2 dB | -6.454 dB | -0.254 dB |
| Rrs -> Rs | -1.2 dB | -1.454 dB | -0.254 dB |

All four measurements pass the analyzer's +/-0.75 dB tolerance. The Lrs and
Rrs contributions in Ls/Rs are in phase, matching the positive-sum polarity of
the documented equations. The machine-readable verdict is:

```text
matches_dolby_pliix_7_1_to_5_1_coefficients
```

Here, "in phase" describes the relative phase between the two destinations of
each rear-surround matrix contribution. A separate absolute input-to-output
measurement finds that the final encoded Ls/Rs channels are rotated by about
-90 degrees by the encoder's Surround Phase Shift preprocessing. See
`automation/PHASE_SHIFT_FINDINGS.md` for the stage-by-stage distinction.

Evidence report:

```text
automation/evidence/pliix/atmos916_flat71_P2P3_r03_r02/analysis.json
```

## Surround EX metadata stage

The DEE output has `dsurexmod=0` in every AC-3 core frame even though the audio
matches the PLIIx matrix. Running `patch_dsur_ex.py` with its default target
produced:

```text
results/atmos916_flat71_P2P3_r03.dsur-ex.eb3
SHA-256: 28042cc8d51c23f6f63345771685f9c04cb188e02f0c355b174f5c0f088b90ad
```

Post-patch verification found:

- `dsurexmod=2` in all 1,250 AC-3 core frames;
- zero AC-3 CRC mismatches;
- all 1,250 dependent/JOC frames byte-identical to the encoder output;
- exactly three changed bytes per AC-3 frame: CRC1 bytes 2-3 and metadata byte
  11, for 3,750 changed bytes total;
- unchanged eight-channel flat 7.1 DD+ Atmos classification; and
- MediaInfo `Format settings: Dolby Surround EX`.

The patched stream's decoded core produces the same PLIIx coefficient verdict.

## Experimental P1+P2+P3 note

A short P1+P2+P3 run was added as a gated diagnostic, but the attempted run was
invalidated by a system-wide Windows error 1114 state: AAC, DDP, DDP Atmos,
single-pass DDP, and TrueHD plugins all failed DLL initialization. A known-good
P2+P3 control immediately reproduced the same failure. Therefore that attempt
does not establish a P1+P2+P3 result. It also is not required for the validated
P2+P3 PLIIx-core conclusion above.

## Scope and remaining playback check

The encoded signal coefficients, bitstream structure, CRCs, JOC preservation,
and Surround EX metadata are verified for the exact source and tool versions
recorded here. A dedicated Dolby PLIIx/EX decoder listening test remains useful
as an additional interoperability check; it is not needed to distinguish the
measured matrix from the Standard Lo/Ro coefficients, which the manual defines
as same-side-only 0 dB folding.
