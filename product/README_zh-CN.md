# DD+ 7.1 Atmos Wrapper for Dolby Encoding Engine

[English](README.md) | 简体中文

文件名：`dee-ddp71-atmos-wrapper.py`

产品版本：`0.2.0-dev`

这是本仓库已验证逆向工程成果的派生产品，也是首个面向现代 DD+ Atmos for Blu-ray 编码、支持用户选择两种兼容呈现编码声道的 Dolby Encoding Engine（DEE）v5.2.1 单命令 CLI 包装器：

- `5.1+2` / `7.1 Height`：`L R C LFE Ls Rs Lvh Rvh`（码流分析工具也可能显示 `Tfl Tfr`）。
- 平面 `7.1`：`L R C LFE Ls Rs Lrs Rrs`（码流分析工具也可能显示 `Lb Rb`）。

本产品将逆向成果转化为完整的端到端制作工作流。它不直接改写成品码流的编码声道标签，不要求为平面 7.1 另行制作特殊 ADM BWF，也不依赖 Dolby Media Producer Suite v2.0 旧版制作流程。输入仍须是 DEE 原版 `atmos_mezz_encode_to_atmos_ddp_ec3.xml` 工作流可接受的合法 Dolby Atmos mezzanine。

> 当前版本是开发版本，只支持经过验证的 `dee_audio_filter_ddp_atmos.dll` 精确构建。原始文件 SHA-256 必须为 `3d66bcec36031fd48e6565d15f05fea656642377ca4f8c98cdce1cce8b7e95d2`。

## 要求

- Windows、Python 3.10 或更高版本。
- 合法取得并已授权的 Dolby Encoding Engine v5.2.1 完整安装。
- DEE 目录中存在 `dee.exe`、`dee_audio_filter_ddp_atmos.dll` 及有效许可证。
- 合法 Dolby Atmos mezzanine 输入。

本项目不分发 Dolby 专有二进制文件、许可证或测试媒体。

## 单命令用法

本版本没有需要逐步执行的子命令。一个命令按照“DEE 路径、输入路径、输出路径、可选覆盖参数”的固定顺序完成备份、生成作业、必要的二进制补丁、编码、必要的 EX 标志处理和还原：

```powershell
python .\dee-ddp71-atmos-wrapper.py <DEE路径或dee.exe> <输入> <输出> [覆盖参数]
```

三个位置参数都支持含 Windows 合法文件名字符的相对或绝对路径，包括 Unicode、空格及 shell 元字符。请按照调用 shell 的规则引用或转义各参数，确保包装器收到未经改变的路径；Windows 自身禁止的字符和名称不属于有效路径。

查看内置帮助：

```powershell
python .\dee-ddp71-atmos-wrapper.py --help
```

最简 5.1+2 编码：

```powershell
python .\dee-ddp71-atmos-wrapper.py `
  "C:\Program Files\Dolby\Dolby Encoding Engine" `
  "D:\masters\feature.atmos" `
  "D:\encodes\feature.eb3"
```

平面 7.1 编码：

```powershell
python .\dee-ddp71-atmos-wrapper.py `
  "C:\Program Files\Dolby\Dolby Encoding Engine\dee.exe" `
  "D:\masters\feature.wav" `
  "D:\encodes\feature-flat71.eb3" `
  --compatibility-layout flat-7.1
```

自定义 Dialnorm 和码率：

```powershell
python .\dee-ddp71-atmos-wrapper.py `
  "C:\DEE-5.2.1" "D:\masters\feature.wav" "D:\encodes\feature.eb3" `
  --custom-dialnorm -27 `
  --data-rate 1664
```

只执行前置校验、备份并生成 XML，不修改 DEE、也不编码：

```powershell
python .\dee-ddp71-atmos-wrapper.py `
  "C:\DEE-5.2.1" "D:\masters\feature.wav" "D:\encodes\feature.eb3" `
  --compatibility-layout flat-7.1 `
  --dry-run
```

## 模板默认值与包装器固定行为

- `<encoding_backend>atmosprocessor</encoding_backend>` 固定，不提供覆盖入口。
- `<encoder_mode>bluray</encoder_mode>` 固定，不提供覆盖入口。
- XML 参数的默认值统一来自 `templates/atmos_mezz_encode_to_atmos_ddp_ec3.xml`，方便集中定制；命令行参数只覆盖本次运行使用的模板值。
- 随附模板把 `<data_rate>` 设为 `1152`。
- 随附模板把 `<preferred_downmix_mode>` 设为 `loro`。未提供命令行覆盖时，`5.1+2` 保留该值，`flat-7.1` 则由包装器切换逻辑选用 `ltrt`；两种布局下的显式命令行值都具有最高优先级。
- 兼容布局切换、动态生成的路径、固定的 Blu-ray 后端/模式及其他非 XML 参数行为仍封装在包装器本体中。

## 第一类：原版 XML 参数覆盖

以下参数按原版 XML 顺序列出。所有项目都是可选覆盖。

| CLI 参数 | XML 参数 | 允许输入 | 随附模板值/包装器行为 |
| --- | --- | --- | --- |
| `--input-timecode-frame-rate` | 输入 `<timecode_frame_rate>` | `not_indicated`, `23.976`, `24`, `25`, `29.97`, `30`, `48`, `50`, `59.94`, `60` | `not_indicated` |
| `--input-offset` | `<offset>` | `auto`、`HH:MM:SS:FF`、`HH:MM:SS.xx` 或十进制秒 | `auto` |
| `--input-ffoa` | `<ffoa>` | `auto`、`HH:MM:SS:FF`、`HH:MM:SS.xx` 或十进制秒 | `auto` |
| `--metering-mode` | `<metering_mode>` | `1770-4`, `1770-3`, `1770-2`, `1770-1`, `LeqA` | `1770-4` |
| `--dialogue-intelligence` | `<dialogue_intelligence>` | `true`, `false` | `true` |
| `--speech-threshold` | `<speech_threshold>` | 整数 `0` 至 `100` | `15` |
| `--data-rate` | `<data_rate>` | `1152`, `1280`, `1408`, `1512`, `1536`, `1664` | 随附模板值 `1152` |
| `--timecode-frame-rate` | 滤镜 `<timecode_frame_rate>` | `not_indicated`, `23.976`, `24`, `25`, `29.97`, `30`, `48`, `50`, `59.94`, `60` | `not_indicated` |
| `--start` | `<start>` | `first_frame_of_action`、时间码、十进制秒或视频帧编号 | `first_frame_of_action`；不能与分段批量模式并用 |
| `--end` | `<end>` | `end_of_file`、时间码、十进制秒或视频帧编号 | `end_of_file`；不能与分段批量模式并用 |
| `--time-base` | `<time_base>` | `file_position`, `embedded_timecode` | `file_position` |
| `--prepend-silence-duration` | `<prepend_silence_duration>` | 非负十进制秒，或帧数如 `12f` | `0.0` |
| `--append-silence-duration` | `<append_silence_duration>` | 非负十进制秒，或帧数如 `12f` | `0.0` |
| `--line-mode-drc-profile` | `<line_mode_drc_profile>` | `film_standard`, `film_light`, `music_standard`, `music_light`, `speech`, `none` | `film_light` |
| `--rf-mode-drc-profile` | `<rf_mode_drc_profile>` | 同上 | `film_light` |
| `--loro-center-mix-level` | `<loro_center_mix_level>` | `+3`, `+1.5`, `0`, `-1.5`, `-3`, `-4.5`, `-6`, `-inf` | `-3` |
| `--loro-surround-mix-level` | `<loro_surround_mix_level>` | `-1.5`, `-3`, `-4.5`, `-6`, `-inf` | `-3` |
| `--ltrt-center-mix-level` | `<ltrt_center_mix_level>` | `+3`, `+1.5`, `0`, `-1.5`, `-3`, `-4.5`, `-6`, `-inf` | `-3` |
| `--ltrt-surround-mix-level` | `<ltrt_surround_mix_level>` | `-1.5`, `-3`, `-4.5`, `-6`, `-inf` | `-3` |
| `--preferred-downmix-mode` | `<preferred_downmix_mode>` | Blu-ray 有效值 `loro`, `ltrt` | 见上方布局规则；`ltrt-pl2` 不受 Blu-ray 模式支持 |
| `--surround-trim-5-1` | `<surround_trim_5_1>` | `0`, `-3`, `-6`, `-9`, `auto` | `auto` |
| `--height-trim-5-1` | `<height_trim_5_1>` | `-3`, `-6`, `-9`, `-12`, `auto` | `auto` |
| `--clean-temp` | `<clean_temp>` | `true`, `false` | `true`；同时按下文说明控制包装器中间码流 |
| `--temp-dir` | `<temp_dir><path>` | 有效目录路径 | 默认使用本次运行目录内的 `temp` |

`--input-timecode-frame-rate` 属于输入 mezzanine 的 `offset`/`ffoa` 解释；`--timecode-frame-rate` 属于编码滤镜的 `start`/`end` 解释，两者不是同一参数。

`--clean-temp` 的有效值具有双重作用：一方面写入 DEE 的 `<clean_temp>` 参数；另一方面，值为 `true` 时，包装器会删除本次运行目录 `encoded/`、`finalized/` 中每个成功发布分段的中间码流。若某段在编码、收尾或发布阶段失败，该段已经产生的中间码流会特意保留用于诊断，并列入 `run.json`；尚未开始的分段不会产生码流。设为 `--clean-temp false` 时，成功分段的中间码流也会保留。无论此值如何，备份及其他全部运行记录（包括生成的作业 XML、日志和 `run.json`）都会始终保留。

## 第二类：包装器扩展参数

| CLI 参数 | 允许输入 | 作用 |
| --- | --- | --- |
| `--custom-dialnorm` | 整数 `-31` 至 `0` | 写入 `<custom_dialnorm>`；`0` 表示不覆盖测得值 |
| `--segmented-batch` | 开关 | 手动开启自定义分段批量编码 |
| `--segment-start` | `first_frame_of_action`, `file_start` | 首段逻辑起点；`file_start` 按 `--time-base` 转换，与 DME v3.7 行为一致 |
| `--segment-point` | `HH:MM:SS:FF` | 重复 N 次并严格升序；各值不换算、不舍入，原样传递给相邻作业 |
| `--compatibility-layout` | `5.1+2`, `flat-7.1` | 选择兼容呈现编码声道；默认 `5.1+2` |

操作辅助参数：`--license-file <路径>` 可选择 DEE 目录外的许可证，否则自动使用 `dee.exe` 同目录的 `license.lic`。由于 DEE 5.2.1 无法打开自身路径含部分 Windows 合法特殊字符的许可证，包装器会把许可证临时转存到保守路径并显式传入；用后自动删除。`--overwrite` 允许替换目标输出；`--dry-run` 只完成备份、验证和 XML 生成。

## 分段批量编码

分段模式必须显式指定四类信息：`--segmented-batch`、`--timecode-frame-rate`、`--time-base`、`--segment-start`，以及至少一个 `--segment-point`。

两个分段点生成三个作业的示例：

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

输出为：

```text
feature.part001of003.eb3
feature.part002of003.eb3
feature.part003of003.eb3
```

每个分段都会在下一项 DEE 作业开始前完成收尾，并以原子方式发布到目标输出路径。若后续分段失败或批处理被中断，先前已经发布的分段仍然可用；失败或尚未开始的分段不会发布。

区间构造规则：

1. 首段 `<start>` 可以是 `first_frame_of_action`；选择 `file_start` 时，`file_position` 下写入视频帧编号 `0`，`embedded_timecode` 下写入输入源时间码/offset。
2. 每个非首段 `<start>` 使用相应分段点。
3. 每个非末段 `<end>` 使用下一分段点。
4. 末段始终写入 `<end>end_of_file</end>`。
5. N 个分段点自动提交 N+1 个顺序编码作业。

分段坐标由两个互相独立的部分组成。`--timecode-frame-rate` 是解释滤镜 `<start>`/`<end>`（包括所有 `--segment-point`）的视频时间码帧率，不是音频采样率；`--input-timecode-frame-rate` 则属于输入 `offset`/`ffoa`。`--time-base` 决定分段点使用的坐标原点：

| `--time-base` | `--segment-point` 的含义 | `file_start` 写入首段 `<start>` 的值 |
| --- | --- | --- |
| `file_position` | 从物理文件头开始计算的相对位置 | 视频帧编号 `0` |
| `embedded_timecode` | 输入时间线上的绝对源时间码 | 输入源时间码/offset |

这一 `file_start` 行为与 DME v3.7 一致：将 Time base 从 File position 改为 Source timecode 后，Start 会从 `00:00:00:00` 变成输入源时间码，而不是继续保留零。`offset=auto` 时，包装器调用 DEE 5.2.1 同目录自带的 `atmos_info.exe`，读取 Atmos master 以绝对秒表示的起始位置，再按滤镜 `--timecode-frame-rate` 表示该位置。AtmosInfo 报告的源视频帧率不必与滤镜帧率相同：输入和滤镜的时间码帧率各有独立用途。滤镜采用任一受支持的 1000/1001 non-drop 速率——23.976、29.97 或 59.94——时，`3603.6` 秒都对应 `01:00:00:00`。若绝对秒位置不落在所选滤镜帧网格上，包装器会改用 DEE 与帧率无关的 `HH:MM:SS.xx` 格式，而不进行舍入。如果 AtmosInfo 无法报告起始位置，包装器会停止并要求显式提供 `--input-offset`，不会再生成无效的零起点；带帧字段的 `--input-offset` 必须显式提供 `--input-timecode-frame-rate`，但输入帧率可以与滤镜帧率不同，包装器会在两个时间域之间换算。

例如，一个 59.94 fps non-drop 母版从源时间码 `01:00:00:00` 开始时，按源时间码分段可直接使用绝对时间线值：

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

包装器把所有 `--segment-point` 原样传递给相邻作业。DEE 的时间码区间包含起点、不包含终点，因此同一点同时作为前一作业的 `<end>` 和后一作业的 `<start>`，会形成相邻区间且不重复边界帧。包装器不把分段点换算到音频帧、访问单元或其他编码边界。当前 `HH:MM:SS:FF` 分段语法仅支持 non-drop，不接受 DEE 的 `df` 后缀。拼接、混流、无缝性、音视频同步及最终交付仍须额外 QC。只需要其中一个片段时，同样从分段点入口生成整组作业，完成后保留目标片段即可。

## 二进制补丁、备份和恢复

每次运行在任何可能的二进制修改前都会：

1. 对 DEE 目录加进程锁。
2. 校验 `dee_audio_filter_ddp_atmos.dll` 精确 SHA-256。
3. 将原始组件备份至 `backups/<安装标识>/` 并再次校验。
4. 在内存中校验 P2+P3 补丁字节和预期补丁后哈希。

`5.1+2` 不安装任何 DEE 补丁。`flat-7.1` 才会原子安装 P2+P3 成对补丁；全部 DEE 作业结束、失败或被正常中断时，包装器都会从已验证备份自动还原并校验原始哈希。若上次进程在断电或强制终止下没有机会执行 `finally`，下次启动在发现精确的已知补丁哈希且备份有效时会先恢复原版。任何未知二进制哈希都会被拒绝，不会盲目覆盖。

DEE 5.2.1 自身的插件加载器在安装路径含部分 Windows 合法 Unicode 或标点符号时无法初始化若干音频滤镜。包装器检测到这类路径后，会把可执行目录中的运行时文件复制到独立位置的保守临时目录；只补丁并执行这个临时副本，随后还原其 DLL 并删除临时副本。用户提供的特殊字符 DEE 包仍保留在原路径，在该兼容模式下从不被补丁。

生成的 XML 会保留用户选择的完整母带路径，`run.json` 则同时保留该原始母带路径和每个请求的输出路径；实际启动 DEE 时，包装器还会像原版示例批处理一样显式传入 `-a`、`-o` 与 `--temp`。对于 DEE 可能无法处理的母带路径，包装器优先使用保守的 Windows 8.3 别名；别名不可用时创建临时硬链接，再回退为经过大小校验的副本（包括跨卷情况）。DEE 只写入包装器所有的中间路径，Python 随后把成品原子发布到用户指定的准确输出路径。无论成功或失败，保守暂存区都会删除。这些措施同时绕过插件加载器限制和 XML 本地存储解析器在首个空格处截断路径的问题，不改变 XML 参数或分段边界。DEE 异常退出后，组件还原和临时暂存区删除都会对 Windows 短暂占用的文件句柄进行有限重试。断电或强制终止遗留的暂存根目录可使用 [DEE 暂存区清理工具](tools/DEE-staging-cleaner/README_zh-CN.md)强制清空；工具无需所有权元数据，会删除其中全部内容。

作业 XML、日志、中间码流及运行清单位于 `work/runs/<运行标识>/`。`backups/` 与 `work/` 已被产品自己的 `.gitignore` 排除。

## Surround EX 独立收尾

当且仅当选择 `flat-7.1`，主线会在 DEE 原版组件已经恢复后，以独立进程调用 [patch_dsur_ex.py](tools/DolbySurrEX-flag-patcher-2966e09/patch_dsur_ex.py)。它只设置 AC-3 核心的 `dsurexmod=2` 并重算对应 CRC，不修改 dependent/JOC 帧，也不承担平面 7.1 声道布局的生成。

该脚本保持独立，便于以后单独更新和审计。来源与固定版本：

- 项目：[LumaVistaLab/DolbySurrEX-flag-patcher](https://github.com/LumaVistaLab/DolbySurrEX-flag-patcher)
- commit：`2966e09`（本仓库参考目录名 `DolbySurrEX-flag-patcher-2966e09`）
- 独立说明：[中文](tools/DolbySurrEX-flag-patcher-2966e09/README_zh-CN.md) / [English](tools/DolbySurrEX-flag-patcher-2966e09/README.md)

## 第三类：暂不支持

当前 CLI 不提供以下开关，也不会伪造对应 XML 参数：

- LFE 低通滤波器开关控制。
- 环绕声道 3 dB 衰减开关控制。
- 环绕声道 90 度相移开关控制。

它们继续遵循已验证 DEE Blu-ray Atmos 路径及母带 Trim Mode Record 的既有行为。

## 开发验证

```powershell
python -m py_compile .\dee-ddp71-atmos-wrapper.py `
  .\tools\DolbySurrEX-flag-patcher-2966e09\patch_dsur_ex.py `
  .\tools\DEE-staging-cleaner\cleanup_dee_staging.py
python -m unittest discover -s .\tests -v
```

2026-09-06 的特殊字符路径绝对/相对实机验证记录见 [VALIDATION_zh-CN.md](VALIDATION_zh-CN.md)。

开发阶段只应修改本 `product` 目录。仓库其他目录仅作为逆向结论、样本和测试参考；`release` 保留最新本地打包快照，不属于开发工作区。

## 法律声明与许可证

本产品是独立逆向工程研究的派生实现，与 Dolby Laboratories 没有从属关系，也未获得其认可。Dolby、Dolby Atmos、Dolby Digital Plus 和 Dolby Encoding Engine 是其相应所有者的商标或产品。用户须自行遵守适用的软件许可、法律及合同限制。

本产品原创代码、文档和独立 Surround EX 工具依据 [GNU General Public License v3.0](LICENSE) 发布。该许可不覆盖 Dolby 专有软件、许可证或用户媒体。
