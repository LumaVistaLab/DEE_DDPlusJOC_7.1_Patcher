# patch_dsur_ex.py

English | [简体中文](README_zh-CN.md)

This is the independent Dolby Surround EX signaling tool invoked by the main wrapper. It is not integrated into `dee-ddp71-atmos-wrapper.py`, so it can be updated, tested, and audited separately.

Source:

- [https://github.com/LumaVistaLab/DolbySurrEX-flag-patcher](https://github.com/LumaVistaLab/DolbySurrEX-flag-patcher)
- Pinned commit: `2966e09`
- Repository reference version: `DolbySurrEX-flag-patcher-2966e09`

The script scans AC-3 core and E-AC-3 dependent/JOC frames in an interleaved Blu-ray DD+ stream. For strictly matching AC-3 core frames, it changes `dsurexmod` to the requested value and recalculates both AC-3 CRC fields. It does not alter dependent/JOC frames, create a PLIIx matrix, or convert an arbitrary Lo/Ro or conventional 5.1 stream to flat 7.1.

## Usage

Check structure, frame counts, current signaling, and CRCs only:

```powershell
python .\tools\DolbySurrEX-flag-patcher-2966e09\patch_dsur_ex.py --check input.eb3
```

Write a new output, setting `dsurexmod` to `2` (Dolby Surround EX) by default:

```powershell
python .\tools\DolbySurrEX-flag-patcher-2966e09\patch_dsur_ex.py input.eb3 output.dsur-ex.eb3
```

Select an explicit target:

```powershell
python .\tools\DolbySurrEX-flag-patcher-2966e09\patch_dsur_ex.py input.eb3 output.eb3 --target 0
python .\tools\DolbySurrEX-flag-patcher-2966e09\patch_dsur_ex.py input.eb3 output.eb3 --target 1
python .\tools\DolbySurrEX-flag-patcher-2966e09\patch_dsur_ex.py input.eb3 output.eb3 --target 2
```

Allowed `--target` values are `0` = not indicated, `1` = not EX, and `2` = EX. `--no-strict` skips unexpected AC-3 frames. The production wrapper does not use that option; it retains strict checking.

Input and output must be different paths; the script does not patch in place. Use it only on flat-7.1 DEE output whose compatibility core has already been verified to contain the PLIIx matrix.

See the product's [GNU GPL v3 license](../../LICENSE).
