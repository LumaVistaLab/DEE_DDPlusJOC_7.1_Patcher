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

## 环境要求

- 合法取得的 Dolby Encoding Engine 5.2.1 安装和有效许可证
- 与本项目完全匹配的 `dee_audio_filter_ddp_atmos.dll`
- Python 3
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
|-- patchers/        补丁生成脚本
|-- automation/      隔离的补丁构建、逆向、测试和码流验证脚本
|-- patch_logs/      保留的完整测试日志
|-- example-flow/    蓝光 DD+ Atmos 示例作业文件
|-- gpt-context/     逆向工程笔记与上下文交接文档
|-- dll_original/    本地原始 DLL；由 Git 忽略
|-- dll_patched/     本地生成的补丁 DLL；由 Git 忽略
|-- dee_copy/        本地 DEE 运行时副本；由 Git 忽略
`-- results/         本地编码测试输出
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
```

自动化流程不修改 `example-flow`，不覆盖既有证据，并会保留所有声明的输出，包括崩溃产生的 0 字节文件。Dolby Surround EX 标志补丁不属于当前平面 7.1 阶段。

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
- 自动化运行前后 `example-flow` 的完整文件哈希清单一致。

完整历史研究结论见 [CODEX_CONTEXT_TRANSFER.md](gpt-context/CODEX_CONTEXT_TRANSFER.md)；已验证的补丁实现结果见 [自动化平面 7.1 结论](automation/FLAT71_FINDINGS.md) 和 [P2+P3 完整日志](patch_logs/flat71_P2P3.log)。

## 法律声明

本仓库是独立研究项目，与 Dolby Laboratories 没有从属关系，也未获得其认可。Dolby、Dolby Atmos 和 Dolby Encoding Engine 是其相应所有者的商标或产品。

本项目不授予任何 Dolby 专有软件、许可证或测试媒体。分析或修改软件时，您有责任遵守所有适用的许可证、法律和合同限制。

## 许可证

本仓库中的原创代码与文档依据 [GNU General Public License v3.0](LICENSE) 发布。该许可证不适用于第三方专有二进制文件或媒体。
