# DD+ 7.1 Atmos Patcher for DEE

语言：简体中文 | [English](README.md)

这是一个面向 Dolby Encoding Engine（DEE）5.2.1 的已验证二进制补丁实现与逆向工程项目。配对的 P2+P3 补丁实现可使蓝光 Dolby Digital Plus with Dolby Atmos（DD+ JOC）采用以下平面 7.1 编码/兼容层布局：

```text
L R C LFE Ls Rs Lrs Rrs
```

而不是当前蓝光模式采用的 `5.X+2` / `7.1 Height` 布局：

```text
L R C LFE Ls Rs Tfl Tfr
```

本项目的目标不是普通的基于声道的 E-AC-3 7.1，而是具有平面 7.1 编码布局的蓝光 DD+ JOC / Dolby Atmos 码流。

本项目支持的端到端输出工作流包含两个必需阶段：先使用已验证的 P2+P3
DLL 编码，再用仓库内置的 `DolbySurrEX-flag-patcher` 完成码流收尾。P2+P3
本身已经生成 5.1 Dolby PLIIx 矩阵兼容内核；第二阶段负责补全其缺失的
Surround EX 信令。

> [!WARNING]
> 本补丁实现已在下文所列的特定 DEE 5.2.1 二进制版本及编码/解码链路上完成验证，但不宣称具备通用或生产级兼容性。请务必保留原始二进制文件。

## 已验证的实现状态

| 变体 | 修改 | 结果 |
| --- | --- | --- |
| P1 | AtmosProcessor 渲染格式：`5.1` -> `7.1` | 编码成功，但最终码流仍为 `7.1 Height` |
| P2 | 单个蓝光内部配置位置：`19` -> `21` | 编码阶段发生访问冲突并崩溃 |
| P1+P2 | P1 加单位置 P2 配置修改 | 与 P2 相同的崩溃 |
| P2+P3 | 两个配对内部配置位置：`19` -> `21` | **已验证的补丁实现：生成平面 7.1 DD+ JOC（`L R C LFE Ls Rs Lb Rb`）** |
| P1+P2+P3 | P1 加配对的 P2/P3 修改 | 未测试；P2+P3 已达到目标，当前无需测试 |
| 仅 P3 | 方向相反的单位置不匹配诊断 | 已生成；低优先级诊断版本 |

成功的 P1 实验证明：仅修改 AtmosProcessor 渲染格式不会改变最终 JOC 编码布局。后续 P2+P3 实验则证明，两个 `19 -> 21` 位置必须同步修改；单点修改造成不一致初始化和崩溃，配对修改会产生目标平面 7.1 布局。

自动静态分析还找到了一个独立的 `0x0C / 0x0E / 0x10` 三态 channel-mode 映射，但由于 P2+P3 已达到目标，该候选未被修改或动态测试。

## 正式端到端工作流

```text
ADM/DAMF 母版
  -> DEE 5.2.1 + 已验证的 P2+P3 DLL
  -> 带 5.1 PLIIx 内核的平面 7.1 DD+ JOC（dsurexmod=0）
  -> DolbySurrEX-flag-patcher
  -> 最终平面 7.1 DD+ JOC（dsurexmod=2，AC-3 CRC 已更新）
```

因此，`DolbySurrEX-flag-patcher` 是本项目已验证输出的正式收尾阶段，
而不是用来生成另一种下混的可选工具。它不会合成或修改 PLIIx 矩阵；
该音频矩阵已经由 P2+P3 编码阶段生成。它只把 AC-3 内核的
`dsurexmod` 从 `0` 改为 `2`，并修改相应 CRC 字节；E-AC-3
dependent/JOC 帧必须保持逐字节不变。

只有在确认码流已携带 PLIIx 矩阵内核后，才能使用该 flag patcher。
它不是面向任意 Lo/Ro 或普通 5.1 码流的通用转换器。

## 播放解码验证

已验证的 P2+P3 补丁实现使用 automation 生成的 40 秒 9.1.6 声道识别
主文件完成编码。最终测试码流为 `atmos916_flat71_P2P3_r03.eb3`，其
SHA-256 为
`de0536e1ec495404e5d1a91b82569c1e5ab1ccb8cb50fa2f4de631208906d354`。

| 验证路径 | 解码器 | 结论 |
| --- | --- | --- |
| 平面 7.1 兼容呈现及编码声道渲染 | LAV Audio Decoder 0.82.0 | **通过：** 编码的 7.1 声道按预期的 `L R C LFE Ls Rs Lb Rb` 布局正确呈现 |
| Dolby Atmos 呈现及空间渲染 | Dolby Media Decoder v3.2.0 | **通过：** 9.1.6 测试位置在 Dolby Atmos 呈现中正确完成空间解码 |

上述播放结果完成了本项目预定的两项验证：平面 7.1 编码兼容层和
Dolby Atmos 空间呈现。结论范围仍限定于此处明确记录的 DEE 二进制版本、
补丁、测试码流及解码器版本。

## 5.1 Dolby PLIIx 内核验证

对同一条 40 秒 P2+P3 码流拆分出 640 kb/s AC-3 兼容内核与 E-AC-3
dependent/JOC 帧，再用 FFmpeg 解码 AC-3 内核，并按测试主文件中隔离的
`Lss`、`Rss`、`Lrs`、`Rrs` 事件测量。实测 7.1 到 5.1 系数与 Dolby
手册给出的 PLIIx 矩阵一致，最大误差为 0.254 dB：

| 矩阵路径 | 手册值 | 实测值 |
| --- | ---: | ---: |
| Lrs -> Ls | -1.2 dB | -1.447 dB |
| Lrs -> Rs | -6.2 dB | -6.447 dB |
| Rrs -> Ls | -6.2 dB | -6.454 dB |
| Rrs -> Rs | -1.2 dB | -1.454 dB |

两个后环绕事件也保持手册公式所示的正相求和关系。因此可以确认：P2+P3
输出已包含 5.1 Dolby PLIIx 矩阵兼容内核，无需 P1 才能得到该结果。

编码器生成的 AC-3 `dsurexmod` 元数据仍为 `0`（未指示）。因此，正式
工作流要使用仓库内置的 Surround EX 后处理器完成编码码流收尾：它把
全部 1,250 个核心帧改为 `2`、重算并通过 CRC，同时使全部 1,250 个
dependent/JOC 帧逐字节不变。处理后的码流仍是平面 7.1 DD+ Atmos，且
MediaInfo 报告 Dolby Surround EX。哈希、测量值与结论边界见
[PLIIx 验证结论](automation/PLIIX_FINDINGS.md)。

## 下混相位与蓝光编码预处理行为

二进制控制流和解码内核测量表明，7.1→5.1 矩阵与面向后续 5.1→2.0
兼容下混的编码预处理是两个独立阶段：

| 范围 | 已验证行为 |
| --- | --- |
| PLIIx 7.1→5.1 矩阵 | 系数矩阵本身不施加相移。隔离的 `Lrs` 或 `Rrs` 分量到达两个 `Ls`/`Rs` 目标时，相对相位差均为 0.0°。 |
| 编码后的 5.1 AC-3 内核 | 编码器对环绕声道施加一次 Surround Phase Shift。补偿 256 samples 公共编解码延迟后，`Lss`、`Rss`、`Lrs`、`Rrs` 相对源信号实测为 −88.402° 至 −90.448°。 |
| 流媒体 Preferred Stereo Downmix | 选择 Pro Logic II 等价于 `Lt/Rt (Pro Logic II) w/Phase 90`；该路径负责 5.1→2.0 所需的单次环绕 90° 相移。 |
| 蓝光 Preferred Stereo Downmix | 蓝光允许 Lo/Ro 或传统 Lt/Rt，本项目默认保持 Lo/Ro；蓝光不接受 Pro Logic II 选择器（`ltrt-pl2`）。环绕 90° 相移由码流编码器预处理独立提供，不取决于此偏好选择。 |
| LFE 低通滤波器 | 默认启用，并在蓝光 Atmos 路径中传递给编码器；它是 Dolby 定义的 120 Hz、8 阶编码前低通滤波器。 |
| 环绕通道 −3 dB 衰减 | 普通 DD+ 编码器把此选项初始化为启用，但带有 Trim Mode Record 的 Atmos 输入会覆盖该通用开关。当前母版所有布局的 `Surround trim` 均为 `0 dB`，所以实际没有额外 −3 dB 衰减；其他 Atmos 母版按各自的 TMR 决定。 |

因此，当前 `encode_to_atmos_ddp` 作业有意保持
`preferred_downmix_mode=loro`。其 XML 不暴露普通 PCM DD+ 编码器所用的
LFE 低通、Surround Phase Shift 和环绕衰减开关：LFE 低通仍在内部启用，
编码内核中可以实测到环绕 90° 相移，而环绕衰减取自 Atmos 母版，不会
被强制设为 −3 dB。

这一区分避免两种错误理解：不能把实测 −90° 归因于 PLIIx 7.1→5.1
系数矩阵，也不能把普通 DD+ 的 `surround_3db_attenuation=true` 默认值
直接解释为所有 Atmos 母版最终都会实际衰减 −3 dB。二进制地址、逐声道
测量值和 profile 映射见
[相移验证结论](automation/PHASE_SHIFT_FINDINGS.md)。Dolby 对这些控制项的
说明见 [Dolby Metadata 指南](https://professionalsupport.dolby.com/s/article/A-Guide-to-Dolby-Metadata?language=en_US)
和 [5.1 与立体声下混设置说明](https://professionalsupport.dolby.com/s/article/How-do-the-5-1-and-Stereo-downmix-settings-work?language=en_US)。

## 环境要求

- 合法取得的 Dolby Encoding Engine 5.2.1 安装和有效许可证
- 与本项目完全匹配的 `dee_audio_filter_ddp_atmos.dll`
- Python 3
- 用于解码内核 PLIIx 系数分析的 NumPy 和 FFmpeg
- 固定一致的 ADM/DAMF 测试源和 DEE 作业 XML
- MediaInfo 或其他合适的 E-AC-3/JOC 码流检查工具

支持的原始 DLL 必须具有以下 SHA-256：

```text
3d66bcec36031fd48e6565d15f05fea656642377ca4f8c98cdce1cce8b7e95d2
```

补丁脚本会拒绝修改不受支持的二进制文件，并会在写入输出文件前检查每个补丁位置的原始字节。

## 仓库结构

```text
DEE_DDPlusJOC_7.1_Patcher/
|-- patchers/                            补丁生成脚本
|-- DolbySurrEX-flag-patcher-2966e09/   正式的 dsurexmod/CRC 收尾阶段
|-- automation/                          隔离的构建、逆向、测试和验证脚本
|-- patch_logs/                          保留的完整测试日志
|-- example-flow/                        蓝光 DD+ Atmos 示例作业文件
|-- gpt-context/                         逆向工程笔记与上下文交接文档
|-- dll_original/                        本地原始 DLL；由 Git 忽略
|-- dll_patched/                         本地生成的补丁 DLL；由 Git 忽略
|-- dee_copy/                            本地 DEE 运行时副本；由 Git 忽略
`-- results/                             本地编码测试输出
```

源码分发不包含 Dolby 二进制文件、许可证和大型测试媒体。请从您自己获得授权的安装中提供这些文件。

## 生成已验证的平面 7.1 补丁

在仓库根目录运行：

```powershell
python .\automation\build_flat71_patch.py
```

脚本只生成已验证的配对 P2+P3 版本；它会校验源 DLL 哈希、两个位置的原始字节、PE 校验和以及最终输出哈希。已存在的输出默认不会被覆盖。

## 生成旧诊断变体

在仓库根目录运行：

```powershell
python .\patchers\make_dee_flat71_patches.py `
  .\dll_original\dee_audio_filter_ddp_atmos.dll `
  --out-dir .\dll_patched
```

脚本会先校验源 DLL 的哈希和原始指令字节，然后生成 P1、P2 和 P1+P2 变体。

较早的 `make_dee_cfg21_patches_v2.py` 会在传入的源 DLL 所在目录生成 P2+P3、P1+P2+P3 和仅 P3 的诊断变体。其中只有配对 P2+P3 已在当前固定测试源上验证。

## 自动化验证

```powershell
python .\automation\tests\test_automation.py
python .\automation\validate.py baseline
python .\automation\run.py preflight flat71_P2P3
python .\automation\run.py run flat71_P2P3
python .\automation\pliix_core_analysis.py `
  .\results\atmos916_flat71_P2P3_r03.eb3 `
  --schedule .\automation\work\test_audio\atmos_916_channel_id_adm.wav.json `
  --output-dir .\automation\evidence\pliix\atmos916_flat71_P2P3
python .\DolbySurrEX-flag-patcher-2966e09\patch_dsur_ex.py --check `
  .\results\atmos916_flat71_P2P3_r03.eb3
python .\DolbySurrEX-flag-patcher-2966e09\patch_dsur_ex.py `
  .\results\atmos916_flat71_P2P3_r03.eb3 `
  .\results\atmos916_flat71_P2P3_r03.dsur-ex.eb3
python .\DolbySurrEX-flag-patcher-2966e09\patch_dsur_ex.py --check `
  .\results\atmos916_flat71_P2P3_r03.dsur-ex.eb3
python .\automation\validate.py stream `
  .\results\atmos916_flat71_P2P3_r03.dsur-ex.eb3
```

编码自动化不修改 `example-flow`，不覆盖既有证据，并会保留所有声明的
输出，包括崩溃产生的 0 字节文件。PLIIx 内核分析是只读操作。Surround EX
收尾在实现上仍由 `patch_dsur_ex.py` 显式、独立执行，以便单独审计；但它
属于正式已验证工作流中必需的第二阶段。前置检查与最终检查必须通过，
且验证必须确认 dependent/JOC 帧没有变化。

## 测试建议

1. 将原始 DEE 运行时和 DLL 设为只读并妥善备份。
2. 每次测试前校验原始文件和候选文件的 SHA-256。
3. 每次只向一次性运行时副本安装一个候选 DLL。
4. 始终复用同一 ADM/DAMF 源、XML 作业、码率和临时目录设置。
5. 保存完整 DEE 日志和进程退出码。
6. 对每个成功输出记录 MediaInfo 声道布局，并保留码流以便比较。
7. 对每次崩溃记录运行时地址、DLL 加载基址、RVA/静态 VA、准确指令和相关对象状态。

切勿覆盖 DLL 中全局的 `"5.1"` 字符串。P1 只修改两个预定的 RIP 相对引用，从而保持解析器比较表不变。

## 已确认的证据

- DEE 5.2.1 包含普通的基于声道的 `ddp71` 路径，其平面顺序为 `L R C LFE Ls Rs Lrs Rrs`。
- 独立 DD+ 编码器包含真实存在的隐藏 `bluray` 和 `bluray_secondary` 模式。
- Atmos 滤镜提供隐藏的 `encoding_backend` 和 `encoder_mode` 参数；蓝光模式使用 AtmosProcessor 后端。
- P1 能完成两个编码阶段并产生有效的非零码流，但编码布局仍为 `7.1 Height`。
- P2 和 P1+P2 均在测量阶段完成后，以相同的首帧访问冲突确定性失败。这表明发生的是配对初始化不一致，而不是已确认的布局切换。
- P2+P3 完成测量和编码阶段，退出码为 0；输出 SHA-256 为 `cb8b7cad90c722ea41437344be711e83def72af019b731a86bee4786cfb0343c`。
- P2+P3 输出包含 8222 个 2560 字节 AC-3 核心帧和 8222 个 4096 字节 E-AC-3 dependent/JOC 帧，无尾随字节。MediaInfo 报告 `L R C LFE Ls Rs Lb Rb`，FFprobe 报告 8 声道 Dolby Digital Plus + Dolby Atmos。
- 使用 LAV Audio Decoder 0.82.0 播放验证了平面 7.1 兼容呈现编码声道渲染正确。
- 使用 Dolby Media Decoder v3.2.0 播放验证了 9.1.6 声道识别码流的 Dolby Atmos 空间呈现解码正确。
- 正式 Surround EX 收尾生成 8,320,000 字节的 `atmos916_flat71_P2P3_r03.dsur-ex.eb3`，SHA-256 为 `28042cc8d51c23f6f63345771685f9c04cb188e02f0c355b174f5c0f088b90ad`。全部 1,250 个 AC-3 核心帧均带有 `dsurexmod=2` 且 CRC 有效，全部 1,250 个 dependent/JOC 帧保持逐字节不变。
- 自动化运行前后 `example-flow` 的完整文件哈希清单一致。

完整历史研究结论见 [CODEX_CONTEXT_TRANSFER.md](gpt-context/CODEX_CONTEXT_TRANSFER.md)；
已验证的补丁实现结果见 [自动化平面 7.1 结论](automation/FLAT71_FINDINGS.md)，
矩阵及收尾证据见 [PLIIx 验证结论](automation/PLIIX_FINDINGS.md)，工具专用
安全检查见 [Surround EX patcher 指南](DolbySurrEX-flag-patcher-2966e09/README_zh-CN.md)，
完整编码日志见 [P2+P3 完整日志](patch_logs/flat71_P2P3.log)。

## 法律声明

本仓库是独立研究项目，与 Dolby Laboratories 没有从属关系，也未获得其认可。Dolby、Dolby Atmos 和 Dolby Encoding Engine 是其相应所有者的商标或产品。

本项目不授予任何 Dolby 专有软件、许可证或测试媒体。分析或修改软件时，您有责任遵守所有适用的许可证、法律和合同限制。

## 许可证

本仓库中的原创代码与文档依据 [GNU General Public License v3.0](LICENSE) 发布。该许可证不适用于第三方专有二进制文件或媒体。
