# v1.1-stable Release Notes / 发布说明

Release date / 发布日期：2026-09-07

## English

### Product and internal versions

The product version is `v1.1-stable`. It is maintained independently from the embedded internal version, `0.3.1-dev`.

### Changes since v1.0-stable

- Standardizes version terminology: the packaged version is the product version, the code-state version is the internal version, and `run.json` now records `internal_version` instead of the misleading `product_version` field.
- Adds DME-style `file_start` mapping for segmented jobs, including automatic Atmos master start probing, separate input and filter timecode rates, exact fractional-rate conversion, and decimal-second fallback for positions off the filter frame grid.
- Publishes every completed segment atomically before the next job begins, so earlier successful outputs remain available when a later segment fails or the batch is interrupted.
- Makes effective `clean_temp=true` remove successful intermediate bitstreams while retaining failed-segment evidence and run records for diagnosis.
- Allows XML template defaults to be customized without duplicate wrapper-generated parameters.
- Improves path compatibility with conservative runtime staging, 8.3 aliases, hard-link or verified-copy input staging, explicit license staging, exact output publication, literal leading-tilde handling, and bounded cleanup retries.
- Bundles a separate DEE staging cleaner for remnants left by power loss or forced termination.
- Keeps the pinned independent Surround EX patcher in its own named tool directory.

### Verified compatibility

- Operating system: Windows.
- Runtime: Python 3.10 or later.
- Encoder: Dolby Encoding Engine v5.2.1.
- Required original `dee_audio_filter_ddp_atmos.dll` SHA-256: `3d66bcec36031fd48e6565d15f05fea656642377ca4f8c98cdce1cce8b7e95d2`.

The exact supported build requirement is unchanged. This product version does not imply compatibility with unverified DEE builds.

### Verification performed

- Python compilation checks passed for the main wrapper, the independent Surround EX tool, and the DEE staging cleaner.
- All 27 automated wrapper tests passed on 2026-09-07.
- Historical source-tree records for the 2026-09-06 absolute- and relative-path real encodes remain unchanged; real encoding was not rerun for this packaged product state.

### Package contents

- Main wrapper and XML workflow template.
- English and Simplified Chinese user guides.
- Independent Surround EX tool with bilingual documentation.
- DEE staging cleaner with bilingual documentation.
- Bilingual release notes, per-file SHA-256 manifest, and GNU GPL v3 license.

### Known limits

- Only the exact DLL build identified above is accepted.
- The current segmented timecode syntax is nondrop only.
- LFE low-pass filtering, 3 dB surround attenuation, and 90-degree surround phase-shift controls are not exposed.
- Users remain responsible for DEE licensing, source-media rights, final muxing, seamlessness, A/V sync, and delivery QC.

## 简体中文

### 产品版本与内部版本

产品版本为 `v1.1-stable`，与内置的内部版本 `0.3.1-dev` 分别维护。

### 相对 v1.0-stable 的变更

- 统一版本术语：打包版本称为产品版本，代码状态版本称为内部版本；`run.json` 现记录 `internal_version`，不再使用容易误解的 `product_version` 字段。
- 为分段作业增加与 DME 一致的 `file_start` 映射，包括 Atmos 母带起始位置自动探测、输入与滤镜时间码帧率分离、分数帧率精确换算，以及不在滤镜帧网格上时的小数秒回退。
- 每个已完成分段都会在下一项作业开始前原子发布；后续分段失败或批处理中断时，之前的成功输出仍然可用。
- 生效的 `clean_temp=true` 会删除成功作业的中间码流，同时保留失败分段证据和运行记录供诊断。
- XML 模板默认值可以自定义，不会生成重复的包装器参数。
- 通过保守运行时暂存、8.3 别名、硬链接或大小校验副本输入暂存、显式许可证暂存、精确输出发布、字面前导波浪号处理与有限重试，改善特殊字符路径兼容性。
- 附带独立 DEE 暂存区清理工具，用于处理断电或强制终止遗留的内容。
- 固定版本的 Surround EX 独立工具保留在自身的具名目录中。

### 已验证兼容范围

- 操作系统：Windows。
- 运行环境：Python 3.10 或更高版本。
- 编码器：Dolby Encoding Engine v5.2.1。
- 所需原版 `dee_audio_filter_ddp_atmos.dll` SHA-256：`3d66bcec36031fd48e6565d15f05fea656642377ca4f8c98cdce1cce8b7e95d2`。

精确构建限制保持不变；本产品版本不代表兼容未经验证的 DEE 构建。

### 已完成验证

- 主包装器、Surround EX 独立工具和 DEE 暂存区清理工具均通过 Python 编译检查。
- 27 项包装器自动化测试于 2026-09-07 全部通过。
- 2026-09-06 绝对路径和相对路径实机编码的历史源码树记录保持不变；本次打包产品状态未重新执行实机编码。

### 包含文件

- 主包装器与 XML 工作流模板。
- 英文和简体中文用户说明。
- Surround EX 独立工具及双语说明。
- DEE 暂存区清理工具及双语说明。
- 双语发布说明、文件级 SHA-256 清单和 GNU GPL v3 许可证。

### 已知限制

- 仅接受上文标明的精确 DLL 构建。
- 当前分段时间码语法仅支持 non-drop。
- 暂不提供 LFE 低通滤波、环绕声道 3 dB 衰减和环绕声道 90 度相移控制。
- 用户仍须自行负责 DEE 授权、源媒体权利、最终混流、无缝性、音视频同步及交付 QC。
