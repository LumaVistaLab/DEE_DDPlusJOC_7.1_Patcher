# DEE v5.2.1 DD+ Atmos flat-7.1 reverse-engineering notes

Target binary SHA-256:
`3d66bcec36031fd48e6565d15f05fea656642377ca4f8c98cdce1cce8b7e95d2  dee_audio_filter_ddp_atmos.dll`

## Validated result addendum

Paired P2+P3 is now validated. Synchronizing both `19 -> 21` sites produces a
complete Blu-ray DD+ JOC stream whose MediaInfo layout is
`L R C LFE Ls Rs Lb Rb`; the job exits with code 0. The output SHA-256 is
`cb8b7cad90c722ea41437344be711e83def72af019b731a86bee4786cfb0343c`.
See `automation/FLAT71_FINDINGS.md` for the complete automated evidence. Older
statements below describing P2+P3 as untested are retained as historical notes.

## P1 — AtmosProcessor output format 5.1 -> 7.1

The DLL contains an output-format parser with:

- `2.0 -> enum 0`
- `5.1 -> enum 1`
- `5.1.4 -> enum 2`
- `7.1 -> enum 3`
- `7.1.4 -> enum 4`

Two runtime construction sites unconditionally build the string `5.1` and pass it to that parser:

- VA `0x18017A4EC`, file offset `0x1798EC`
  - old: `48 8D 15 E5 FF 4C 00` -> target `0x18064A4D8` (`5.1`)
  - new: `48 8D 15 B9 2C 4D 00` -> target `0x18064D1AC` (`7.1`)
- VA `0x18017B8DA`, file offset `0x17ACDA`
  - old: `48 8D 15 F7 EB 4C 00` -> target `0x18064A4D8` (`5.1`)
  - new: `48 8D 15 CB 18 4D 00` -> target `0x18064D1AC` (`7.1`)

This changes parser output from enum 1 to enum 3 without touching the parser's string table.

## P2 — Blu-ray-specific 19 -> 21 candidate configuration

At VA `0x18017D5E8` / file offset `0x17C9E8`, a configuration pair is built as follows:

```asm
mov dword ptr [rbp+40h], 0Bh
mov eax, 13h          ; 19
cmp r14d, 0Ah
cmove eax, r12d       ; r12d = 7
mov dword ptr [rbp+44h], eax
```

The caller passes `r9d = 10` for Online Media and `r9d = 11` for Blu-ray. This is independently anchored by the same caller's `rdi+4 == 1` Blu-ray branch and the runtime message `Preferred Downmix mode Pro Logic II is not supported in Blu-ray Mode`.

Therefore this pair selects:

- Online: value `7`
- Blu-ray: value `19`

Experimental P2 changes only the Blu-ray default:

- old: `B8 13 00 00 00` (`mov eax,19`)
- new: `B8 15 00 00 00` (`mov eax,21`)

Bottom-level DDP code has a distinct 8-channel/downmix path for configuration 21 consistent with flat 7.1 (`L R C LFE Ls Rs Lrs Rrs`). The exact semantic handoff from the wrapper's pair-id `0x0B` to the DDPI input-configuration API still requires runtime confirmation.

## Variants

- `P1`: only AtmosProcessor output is changed to 7.1.
- `P2`: only the Blu-ray-specific 19 -> 21 candidate configuration is changed.
- `P1P2`: both changes.

The PE checksum is recalculated for every generated DLL.

## Recommended runtime test order

Use a separate copy of the DEE installation and the same short ADM/DAMF source and job for every encode. Keep `encoder_mode=bluray` and `encoding_backend=atmosprocessor` fixed.

1. Original DLL (control)
2. P1 only
3. P2 only
4. P1+P2

Compare:

- whether encoding opens successfully;
- DEE log channel/configuration messages;
- output `.eb3` MediaInfo/ffprobe layout;
- independent/dependent substream structure;
- JOC signalling and evolution/OAMD payload presence;
- non-Atmos 7.1 and 5.1 compatibility decoding;
- Scenarist UHD acceptance.

Do not use these experimental DLLs in the normal DEE installation. P1 is not conditioned on Blu-ray mode and may affect non-Blu-ray Atmos workflows.
