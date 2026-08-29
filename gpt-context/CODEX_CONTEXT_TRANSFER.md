# DEE_DDPlusJOC_7.1_Patcher — Codex Context Transfer
Date: 2026-08-29
Target: Dolby Encoding Engine v5.2.1
Primary goal: make DD+ Atmos for Blu-ray produce a **flat 7.1 coded/compatibility layout**
`L R C LFE Ls Rs Lrs Rrs` instead of the modern Blu-ray `5.X+2 / 7.1 Height`
`L R C LFE Ls Rs Tfl Tfr`.

---

## 2026-08-29 validation addendum — goal reached

This addendum supersedes the older "not yet identified" and "next experiment"
statements later in this historical handoff.

- Paired P2+P3 (`0x17C0D7` and `0x17C9E8`, both `19 -> 21`) completes the DEE job with exit code 0.
- Output SHA-256: `cb8b7cad90c722ea41437344be711e83def72af019b731a86bee4786cfb0343c`.
- MediaInfo: `L R C LFE Ls Rs Lb Rb`, Blu-ray Disc, Dep JOC, Dolby Digital Plus with Dolby Atmos.
- FFprobe: 8 channels, 7.1, Dolby Digital Plus + Dolby Atmos.
- The stream contains 8222 AC-3 core frames and 8222 E-AC-3 dependent/JOC frames, with no trailing bytes.
- P1+P2+P3 is no longer an immediate test target because paired P2+P3 already reaches the goal.
- Dolby Surround EX integration remains deferred to a later 5.1 Dolby PLIIx phase.

See `automation/FLAT71_FINDINGS.md` and `patch_logs/flat71_P2P3.log` for the current evidence.

---

## 1. Scope and working assumptions

This project is reverse-engineering DEE v5.2.1's Blu-ray Dolby Digital Plus with Dolby Atmos path.

The current known Blu-ray Atmos workflow is:

- DEE filter: `encode_to_atmos_ddp`
- hidden/internal options:
  - `encoder_mode = bluray`
  - `encoding_backend = atmosprocessor`
- Blu-ray DD+ Atmos bitrates accepted by the Atmos DLL:
  - 1152
  - 1280
  - 1408
  - 1512
  - 1536
  - 1664 kbps
- output node remains `ec3`, but file can be named `.eb3`.

Important: the task is **not** to produce ordinary channel-based E-AC-3 7.1.  
The desired result is **DD+ JOC / Dolby Atmos for Blu-ray** whose coded/compatibility 7.1 arrangement is flat 7.1.

---

## 2. Original binaries

The three original files under reverse engineering are:

1. `dee.exe`
2. `dee_audio_filter_ddp_atmos.dll`
3. `dee_ddp_encoder.exe`

Known original SHA-256:

`dee_audio_filter_ddp_atmos.dll`

```text
3d66bcec36031fd48e6565d15f05fea656642377ca4f8c98cdce1cce8b7e95d2
```

All patch work described below assumes exactly this DLL build.

DEE runtime/version observed in test logs:

```text
Dolby Encoding Engine, version: 5.2.1-5994839
```

Atmos Storage Framework:

```text
Dolby Atmos Storage Framework 1.5.0_5673674
```

---

## 3. Confirmed static reverse-engineering results

### 3.1 `dee.exe`: channel-based flat 7.1 exists

`dee.exe` contains explicit schema/strings for ordinary DD+ 7.1:

```text
WAV_LIST_7_1
ENCODER_MODE_DDP71
channel_configuration=7.1
encoder_mode=ddp71
```

It also contains the flat 8-channel WAV order:

```text
L
R
C
LFE
LS
RS
LRS
RRS
```

Therefore ordinary channel-based DD+ flat 7.1 definitely exists in DEE 5.2.1.

This does **not** by itself prove that DD+ JOC can use the same flat 7.1 coded layout.

---

### 3.2 `dee_ddp_encoder.exe`: hidden Blu-ray encoder modes are real

The standalone DDP encoder contains four encoder mode enum strings:

```text
dd               = 0
ddp              = 1
bluray           = 2
bluray_secondary = 3
```

It also contains:

```text
Embedding timestamp is supported only by DD and Bluray encoder modes.
```

Therefore `bluray` is a real Dolby internal encoder mode, not a third-party invented keyword.

The output-channel-layout string table exposes:

```text
mono   = 0
stereo = 1
5.1    = 2
auto   = 4
```

Enum value 3 is not exposed by the CLI string table.

---

### 3.3 `dee_audio_filter_ddp_atmos.dll`: hidden Atmos parameters are confirmed

The DLL embeds the filter schema.

Confirmed hidden/less-visible parameters:

```text
encoding_backend
  enum: PE, atmosprocessor
  default: PE

encoder_mode
  enum: ddp, bluray
  default: ddp
```

The DLL also contains the runtime fallback:

```text
PE backend is not supported for Blu-ray Mode.
Using atmosprocessor backend.
```

So in Blu-ray mode, AtmosProcessor is mandatory and will be selected automatically if PE was requested.

Other confirmed Atmos filter options include:

```text
preferred_downmix_mode:
  loro
  ltrt
  ltrt-pl2
  not_indicated
```

Blu-ray restriction:

```text
Preferred Downmix mode Pro Logic II is not supported in Blu-ray Mode
```

---

## 4. Important architecture distinction

There are at least three different layout/configuration layers. They must not be conflated.

### Layer A — AtmosProcessor render/output format

The DLL output-format parser accepts:

```text
2.0   -> enum 0
5.1   -> enum 1
5.1.4 -> enum 2
7.1   -> enum 3
7.1.4 -> enum 4
```

The original DD+ Atmos filter has two runtime construction sites that reference the literal `"5.1"`.

Changing those call-site references to the existing `"7.1"` literal is valid and has been tested successfully.

This is the patch currently called **P1**.

### Layer B — internal Phoenix / spatial-coding configuration

Several numeric configuration values exist, including:

```text
7
19
21
24
28
```

Earlier work incorrectly concluded that `21 == flat 7.1`.  
That conclusion is **withdrawn**.

Subsequent analysis suggests these numbers are related to internal Atmos/Phoenix signal/bed configurations, not directly the final JOC coded-channel layout.

### Layer C — final JOC downmix/coded-channel configuration

This is the actual target.

The desired switch is conceptually:

```text
current: 5.X+2
         L R C LFE Ls Rs Tfl Tfr

target:  7.X / flat 7.1
         L R C LFE Ls Rs Lrs Rrs
```

The real selector controlling this layer has **not yet been identified**.

---

## 5. P1 patch — confirmed working

### Purpose

Change AtmosProcessor render/output format from 5.1 to 7.1 by changing two RIP-relative references to point to the existing `"7.1"` literal.

Do **not** overwrite the global `"5.1"` string itself, because the parser also uses it as a comparison constant.

### P1 patch sites

#### P1-A

```text
VA:          0x18017A4EC
file offset: 0x1798EC
```

Original:

```hex
48 8D 15 E5 FF 4C 00
```

Patched:

```hex
48 8D 15 B9 2C 4D 00
```

#### P1-B

```text
VA:          0x18017B8DA
file offset: 0x17ACDA
```

Original:

```hex
48 8D 15 F7 EB 4C 00
```

Patched:

```hex
48 8D 15 CB 18 4D 00
```

### Experimental result

P1 completed the full two-pass encode successfully.

Observed log characteristics:

```text
Encoding Backend: AtmosProcessor.
...
Encoder done.
...
Overall progress: 100.0
```

The output `.eb3` was valid/non-zero.

However MediaInfo still reported:

```text
7.1 Height
L R C LFE Ls Rs Tfl Tfr
```

### Interpretation

P1 proves:

- AtmosProcessor can render 7.1 in this workflow.
- Upstream 7.1 rendering alone does **not** change the final Blu-ray JOC coded layout.
- Therefore the `5.X+2 / 7.1 Height` decision occurs later in the pipeline.

This is one of the most important experimental results in the project.

---

## 6. P2 and P1+P2 — failed experiment and what it proved

### Original P2

Patch:

```text
VA:          0x18017D5E8
file offset: 0x17C9E8
```

Original:

```hex
B8 13 00 00 00
```

Patched:

```hex
B8 15 00 00 00
```

i.e.

```text
19 -> 21
```

### Result

Both:

- P2 only
- P1 + P2

failed at the start of the encoder pass.

The measurement pass completed normally.

Immediately after:

```text
Encoding Backend: AtmosProcessor.
```

the process crashed with an access violation.

Observed runtime crash address:

```text
0x00007FFE4E1106BF
```

With the DLL ASLR base reconstructed as approximately:

```text
0x00007FFE4E0A0000
```

the crash maps to:

```text
RVA:       0x706BF
Static VA: 0x1800706BF
```

Nearby code checks an object field against decimal 19 and then dereferences an auxiliary object pointer:

```asm
cmp dword ptr [rbx+24h], 13h
jne ...
mov rcx, [rbx+182E8h]
...
mov eax, [rcx+1Ch]     ; crash when auxiliary object is missing/invalid
```

### Critical interpretation

The runtime main object was still behaving as configuration 19 even though P2 had changed one initialization-side value to 21.

Therefore P2 was **not** the final JOC coded-layout selector.

It changed one half of a paired configuration setup and caused inconsistent allocation/initialization.

---

## 7. Newly identified matching P3 site

A second matching Blu-ray `19` was found.

### P3

```text
VA:          0x18017CCD7
file offset: 0x17C0D7
```

Original:

```hex
B8 13 00 00 00
```

Candidate:

```hex
B8 15 00 00 00
```

i.e.

```text
19 -> 21
```

### Current interpretation

The two sites appear to be used at different DDPI initialization stages:

```text
P2 side: querymem/open-related configuration
P3 side: set_params-related configuration
```

P2-only created a mismatched configuration:

```text
one side = 21
other side = 19
```

which explains the deterministic first-frame access violation.

### New experimental candidates

Two new DLLs have been generated but have **not yet been tested**:

#### Candidate A — P2 + P3

Both internal config values changed from 19 to 21.

Filename:

```text
dee_audio_filter_ddp_atmos_cfg21_P2P3.dll
```

SHA-256:

```text
fd49c7b9b19bba5f7ec0b862a9811a7b822b2efe200bc82a033fb9b7f54c1588
```

#### Candidate B — P1 + P2 + P3

AtmosProcessor 7.1 render plus synchronized 19->21 internal config.

Filename:

```text
dee_audio_filter_ddp_atmos_cfg21_P1P2P3.dll
```

SHA-256:

```text
82fef3a4f9683cde7d51dd42ee755c92c60f9be829960694edc1746b71af2b05
```

There is also a diagnostic `P3only` build:

```text
dee_audio_filter_ddp_atmos_cfg21_P3only.dll
```

SHA-256:

```text
caac9ec16306949d60bb7125b7ec8385fb4423568fb3684adb5d1e29c625dcc3
```

`P3only` is expected to create the opposite mismatch and is not a priority test.

---

## 8. Important correction: do NOT assume 21 means flat 7.1

Earlier reverse engineering inferred that config 21 represented flat 7.1 from an 8->6 downmix path.

That inference is now considered unreliable.

Additional internal signal-mask behavior suggests:

```text
cfg 7  -> 6-signal-like configuration
cfg 19 -> 10-signal-like configuration
cfg 21 -> 10-signal-like configuration
cfg 24 -> 9-signal-like configuration
cfg 28 -> 10-signal-like configuration
```

The Atmos DLL also contains strings such as:

```text
5.1.2
5.1.4
5.1.6
7.1.2
7.1.4
7.1.6
```

and errors including:

```text
Bed mixer process failed to create 7.1.2 bed
Invalid master. Signal contains a 7.1.2 bed which does not start at index 0
Invalid monitored spatial coding bed configuration value
```

Therefore the current best model is:

```text
7 / 19 / 21 / 24 / 28
```

belong to an internal Phoenix/spatial-coding/bed configuration layer.

They should not be treated as the final JOC `5.X / 7.X / 5.X+2` enum until proven.

---

## 9. What the user has experimentally established

### P1

Status: **PASS**

- two-pass encode completes
- valid `.eb3`
- MediaInfo: still `7.1 Height`
- layout remains:
  - `L R C LFE Ls Rs Tfl Tfr`

### P2

Status: **FAIL**

- measurement pass completes
- encoder pass begins
- logs:
  - `Encoding Backend: AtmosProcessor.`
- deterministic access violation
- 0-byte output
- application exit code 10

### P1+P2

Status: **FAIL**

- same failure stage
- same crash address
- 0-byte output
- proves P1 is not the source of the P2 crash

These three test logs should be retained as evidence.

---

## 10. Next reverse-engineering target

Do **not** continue blindly changing `19 -> 21`.

The next target is the actual configuration passed to the JOC spatial coder / JOC encoder after AtmosProcessor rendering.

Search and trace around these functional areas/strings:

```text
Spatial Coding encode process
Spatial Coding to OAMDI conversion
Encoding of evolution payload
DD+ JOC encode
Missing or invalid JOC payload for output frame
Missing or invalid OAMD payload for output frame
```

The goal is to identify the structure or enum that chooses among conceptual JOC downmix/coded layouts:

```text
5.X
7.X
5.X+2
```

Useful approaches:

1. Locate all functions referencing strings related to:
   - `spatial coding`
   - `evolution payload`
   - `JOC`
   - `OAMD`
   - `downmix configuration`
   - `channel configuration`

2. Trace the final parameter object immediately before:
   - JOC encode open/init
   - JOC encode process
   - E-AC-3 frame assembly

3. Compare:
   - Online Media path
   - Blu-ray path
   - P1-modified path

4. Look specifically for small enum-like values that differ between:
   - Online 5.1 JOC
   - Blu-ray 5.X+2 JOC

5. Do not rely only on numeric similarity.
   Confirm candidate fields by:
   - all use sites
   - validation tables
   - channel-map construction
   - frame metadata writing
   - bitstream behavior after a controlled patch

---

## 11. Recommended dynamic experiment order

When testing new patches, always use the same ADM/DAMF source and the same XML job.

Recommended immediate order:

### Test A — P2+P3

```text
dee_audio_filter_ddp_atmos_cfg21_P2P3.dll
```

Possible outcomes:

- succeeds, still 7.1 Height:
  - proves 19/21 is internal bed/spatial config, not final JOC layout
- succeeds, layout changes:
  - inspect exact MediaInfo layout and bitstream
- fails at a **new** address:
  - useful; synchronize the next paired structure
- fails at the same `RVA 0x706BF`:
  - reevaluate patch-site role/ASLR mapping

### Test B — P1+P2+P3

Only test after A is understood.

This determines whether upstream 7.1 render is required by the synchronized cfg21 path.

---

## 12. Test workflow currently used

Observed command pattern:

```bat
..\dee_copy\dee.exe ^
  -x ".\atmos_mezz_encode_to_atmos_ddp_ec3.xml" ^
  -a ".\sollevante_lp_v01_DAMF_Nearfield_48k_24b_24.wav" ^
  -o "..\results\<output>.eb3" ^
  --temp "X:\DolbyEncodingEngineTemp"
```

Known test source:

```text
sollevante_lp_v01_DAMF_Nearfield_48k_24b_24.wav
```

Known workflow XML:

```text
atmos_mezz_encode_to_atmos_ddp_ec3.xml
```

These two files are essential for reproducing the existing tests.

---

## 13. Suggested working-directory structure

```text
DEE_DDPlusJOC_7.1_Patcher/
│
├─ original/
│  ├─ dee.exe
│  ├─ dee_audio_filter_ddp_atmos.dll
│  └─ dee_ddp_encoder.exe
│
├─ dee_runtime/
│  └─ [complete DEE v5.2.1 runtime copy used for execution]
│
├─ example-flow/
│  ├─ atmos_mezz_encode_to_atmos_ddp_ec3.xml
│  └─ sollevante_lp_v01_DAMF_Nearfield_48k_24b_24.wav
│
├─ patches/
│  ├─ dee_audio_filter_ddp_atmos_flat71_P1.dll
│  ├─ dee_audio_filter_ddp_atmos_flat71_P2.dll
│  ├─ dee_audio_filter_ddp_atmos_flat71_P1P2.dll
│  ├─ dee_audio_filter_ddp_atmos_cfg21_P2P3.dll
│  ├─ dee_audio_filter_ddp_atmos_cfg21_P1P2P3.dll
│  ├─ dee_audio_filter_ddp_atmos_cfg21_P3only.dll
│  ├─ make_dee_flat71_patches.py
│  └─ make_dee_cfg21_patches_v2.py
│
├─ logs/
│  ├─ flat71_P1.log
│  ├─ flat71_P2.log
│  └─ flat71_P1P2.log
│
├─ notes/
│  ├─ DEE_v5.2.1_flat71_reverse_notes.md
│  └─ CODEX_CONTEXT_TRANSFER.md
│
└─ results/
   └─ [generated .eb3 test outputs]
```

---

## 14. Codex instructions / priorities

1. Treat all conclusions in this document as reverse-engineering findings, not Dolby public API guarantees.
2. Preserve the original binaries read-only.
3. Verify SHA-256 before applying any patch.
4. Never patch the global `"5.1"` string directly.
5. P1 is confirmed valid but only changes AtmosProcessor render format.
6. P2 by itself is invalid and must not be reused as a standalone candidate.
7. P2 and P3 appear paired; test them together before drawing further conclusions.
8. Do not assume config value 21 means flat 7.1.
9. The real objective is to locate the final JOC coded-layout selector downstream of AtmosProcessor.
10. Every future candidate patch should be tested independently and logged.
11. For every crash:
    - record full runtime address
    - determine loaded DLL base
    - convert to RVA/static VA
    - disassemble the exact instruction
    - inspect object fields and upstream initializer
12. For every successful `.eb3`:
    - record MediaInfo
    - compare channel layout
    - compare substreams / dependent streams if possible
    - preserve the output for later binary comparison.

---

## 15. Known failed/withdrawn assumptions

Do not reintroduce these unless new evidence supports them:

### Withdrawn assumption A

```text
AtmosProcessor outputFormat = 5.1
```

does **not** mean the final coded layout must be 5.1.

P1 proves 7.1 render can still produce 7.1 Height / 5.X+2 output.

### Withdrawn assumption B

```text
config 21 = flat 7.1
```

is not currently proven and should be treated as false/unresolved.

### Withdrawn assumption C

Changing only one Blu-ray `19 -> 21` site can test the layout.

False. P2-only creates inconsistent initialization and crashes.

---

## 16. Current best mental model

```text
ADM / DAMF
   │
   ▼
AtmosProcessor
   │
   ├─ output format = 5.1   [original]
   │
   └─ output format = 7.1   [P1, confirmed working]
   │
   ▼
Phoenix / spatial-coding internal configuration
   │
   └─ includes values such as 7 / 19 / 21 / 24 / 28
      exact semantic mapping still unresolved
   │
   ▼
JOC spatial coding
   │
   ├─ spatial coding payload
   ├─ evolution payload
   └─ OAMD
   │
   ▼
FINAL JOC coded/downmix layout selector
   │
   ├─ 5.X
   ├─ 7.X       ← TARGET
   └─ 5.X+2     ← CURRENT BLU-RAY OUTPUT
   │
   ▼
E-AC-3 / .eb3
```

The project should now focus on the block labelled:

```text
FINAL JOC coded/downmix layout selector
```

not on AtmosProcessor output format and not on the unresolved 19/21 Phoenix configuration layer.

---

## 17. Immediate Codex task

Recommended first task:

> Reverse-engineer `dee_audio_filter_ddp_atmos.dll` downstream of AtmosProcessor and locate the configuration field that controls the final JOC coded/downmix layout (`5.X`, `7.X`, `5.X+2`). Use the known successful P1 and failed P2/P1+P2 experiments as differential evidence. Do not assume numeric config 19/21 maps directly to final channel layout. Trace JOC/OAMD/evolution-payload initialization and the parameter structure passed into the final DD+ JOC encoder. Preserve exact RVAs, file offsets, byte sequences, call graphs, and semantic confidence for every candidate.
