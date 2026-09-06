# v1.0-stable Release Notes / 发布说明

Release date / 发布日期：2026-09-07

## English

### Release identity

`v1.0-stable` is the identifier of this packaged release. It is maintained independently from the product's embedded development-stream version (`0.1.0-dev`), which is intentionally unchanged in this release.

### Highlights

- Provides a single-command Windows CLI workflow around a legally obtained Dolby Encoding Engine v5.2.1 installation.
- Supports the original `5.1+2` / `7.1 Height` compatibility presentation and the validated flat `7.1` layout.
- Applies the validated P2+P3 flat-7.1 patch only when requested, then restores and verifies the original DEE component.
- Supports N-point/N+1-job segmented batch encoding with explicit timecode controls.
- Finalizes flat-7.1 output with the independent pinned Surround EX flag tool and recalculates affected AC-3 CRC values.
- Handles Windows-valid Unicode, spaces, and punctuation in DEE, input, output, and working paths through a disposable conservative runtime stage where required.
- Rejects unknown DEE component hashes and does not distribute Dolby binaries, licenses, or media.

### Verified compatibility

- Operating system: Windows.
- Runtime: Python 3.10 or later.
- Encoder: Dolby Encoding Engine v5.2.1.
- Required original `dee_audio_filter_ddp_atmos.dll` SHA-256: `3d66bcec36031fd48e6565d15f05fea656642377ca4f8c98cdce1cce8b7e95d2`.

The exact supported build requirement is unchanged. This release label does not imply compatibility with unverified DEE builds.

### Verification performed

- Python compilation checks passed for the main wrapper and the independent Surround EX tool.
- All 14 automated wrapper tests passed on 2026-09-07.
- Source-tree validation records document successful absolute- and relative-path real encodes through paths containing Windows-valid Unicode and punctuation on 2026-09-06.
- Those flat-7.1 outputs were checked for layout, Atmos dependent/JOC data, Surround EX signaling, CRC integrity, and restoration of the original DEE component.

### Package contents

- Main wrapper: `dee-ddp71-atmos-wrapper.py`
- Original workflow template: `templates/atmos_mezz_encode_to_atmos_ddp_ec3.xml`
- Independent Surround EX tool and bilingual guide: `tools/`
- English and Simplified Chinese user guides: `README.md`, `README_zh-CN.md`
- Bilingual release notes: `RELEASE_NOTES.md`
- Per-file SHA-256 manifest: `SHA256SUMS.txt`
- License: `LICENSE` (GNU General Public License v3.0)

### Known limits

- Only the exact DLL build identified above is accepted.
- LFE low-pass filtering, 3 dB surround attenuation, and 90-degree surround phase-shift controls are not exposed.
- Users remain responsible for DEE licensing, source-media rights, final muxing, seamlessness, A/V sync, and delivery QC.

## 简体中文

### 发布标识

`v1.0-stable` 是本次打包发布的独立标识。它与产品内置的开发流版本（`0.1.0-dev`）分别维护；本次发布有意不修改产品内置版本。

### 主要内容

- 提供面向合法取得的 Dolby Encoding Engine v5.2.1 安装的 Windows 单命令 CLI 工作流。
- 支持原版 `5.1+2` / `7.1 Height` 兼容呈现以及经过验证的平面 `7.1` 布局。
- 仅在用户选择平面 7.1 时安装经过验证的 P2+P3 补丁，随后还原并校验 DEE 原始组件。
- 支持显式时间码控制的 N 个分段点/N+1 个作业批量编码。
- 使用固定版本的独立 Surround EX 标志工具完成平面 7.1 收尾，并重新计算受影响的 AC-3 CRC。
- 必要时通过保守的临时运行时副本，兼容 DEE、输入、输出和工作路径中的 Windows 合法 Unicode、空格及标点符号。
- 拒绝未知 DEE 组件哈希；不分发 Dolby 二进制文件、许可证或媒体。

### 已验证兼容范围

- 操作系统：Windows。
- 运行环境：Python 3.10 或更高版本。
- 编码器：Dolby Encoding Engine v5.2.1。
- 所需原版 `dee_audio_filter_ddp_atmos.dll` SHA-256：`3d66bcec36031fd48e6565d15f05fea656642377ca4f8c98cdce1cce8b7e95d2`。

精确构建限制保持不变；`v1.0-stable` 发布标识不代表兼容未经验证的 DEE 构建。

### 已完成验证

- 主包装器和独立 Surround EX 工具均通过 Python 编译检查。
- 14 项包装器自动化测试于 2026-09-07 全部通过。
- 源码树中的验证记录记载了 2026-09-06 在包含 Windows 合法 Unicode 与标点符号的路径中完成的绝对路径和相对路径实机编码。
- 这些平面 7.1 输出已经检查声道布局、Atmos dependent/JOC 数据、Surround EX 标志、CRC 完整性以及 DEE 原始组件还原结果。

### 包含文件

- 主包装器：`dee-ddp71-atmos-wrapper.py`
- 原版工作流模板：`templates/atmos_mezz_encode_to_atmos_ddp_ec3.xml`
- 独立 Surround EX 工具及双语说明：`tools/`
- 英文和简体中文用户说明：`README.md`、`README_zh-CN.md`
- 双语发布说明：`RELEASE_NOTES.md`
- 文件级 SHA-256 清单：`SHA256SUMS.txt`
- 许可证：`LICENSE`（GNU General Public License v3.0）

### 已知限制

- 仅接受上文标明的精确 DLL 构建。
- 暂不提供 LFE 低通滤波、环绕声道 3 dB 衰减和环绕声道 90 度相移控制。
- 用户仍须自行负责 DEE 授权、源媒体权利、最终混流、无缝性、音视频同步及交付 QC。
