# DEE_DDPlusJOC_7.1_Patcher

语言：简体中文 | [English](README.md)

这是一个面向 Dolby Encoding Engine（DEE）5.2.1 的实验性二进制补丁与逆向工程项目，目标是确认蓝光 Dolby Digital Plus with Dolby Atmos（DD+ JOC）能否使用以下平面 7.1 编码/兼容层布局：

```text
L R C LFE Ls Rs Lrs Rrs
```

而不是当前蓝光模式采用的 `5.X+2` / `7.1 Height` 布局：

```text
L R C LFE Ls Rs Tfl Tfr
```

本项目的目标不是普通的基于声道的 E-AC-3 7.1，而是具有平面 7.1 编码布局的蓝光 DD+ JOC / Dolby Atmos 码流。

> [!WARNING]
> 本项目仍处于未完成的实验阶段。目前没有任何补丁成功生成目标平面 7.1 JOC 布局。请勿将生成的 DLL 用于生产环境，并务必保留原始二进制文件。

## 当前状态

| 变体 | 修改 | 结果 |
| --- | --- | --- |
| P1 | AtmosProcessor 渲染格式：`5.1` -> `7.1` | 编码成功，但最终码流仍为 `7.1 Height` |
| P2 | 单个蓝光内部配置位置：`19` -> `21` | 编码阶段发生访问冲突并崩溃 |
| P1+P2 | P1 加单位置 P2 配置修改 | 与 P2 相同的崩溃 |
| P2+P3 | 两个配对内部配置位置：`19` -> `21` | 已生成，尚未测试 |
| P1+P2+P3 | P1 加配对的 P2/P3 修改 | 已生成，尚未测试 |
| 仅 P3 | 方向相反的单位置不匹配诊断 | 已生成；低优先级诊断版本 |

成功的 P1 实验证明：仅修改 AtmosProcessor 渲染格式不会改变最终 JOC 编码布局。目前认为数值 `19` 和 `21` 属于内部 Phoenix/空间编码配置层；没有证据表明 `21` 就代表平面 7.1。

当前首要逆向目标是位于下游、负责在概念上的 `5.X`、`7.X` 和 `5.X+2` 配置之间选择最终 JOC 编码/下混布局的选择器。

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
|-- patch_logs/      保留的 P1、P2 和 P1+P2 测试日志
|-- example-flow/    蓝光 DD+ Atmos 示例作业文件
|-- gpt-context/     逆向工程笔记与上下文交接文档
|-- dll_original/    本地原始 DLL；由 Git 忽略
|-- dll_patched/     本地生成的实验性 DLL；由 Git 忽略
|-- dee_copy/        本地 DEE 运行时副本；由 Git 忽略
`-- results/         本地编码测试输出
```

源码分发不包含 Dolby 二进制文件、许可证和大型测试媒体。请从您自己获得授权的安装中提供这些文件。

## 生成 P1/P2 变体

在仓库根目录运行：

```powershell
python .\patchers\make_dee_flat71_patches.py `
  .\dll_original\dee_audio_filter_ddp_atmos.dll `
  --out-dir .\dll_patched
```

脚本会先校验源 DLL 的哈希和原始指令字节，然后生成 P1、P2 和 P1+P2 变体。

较新的 `make_dee_cfg21_patches_v2.py` 会在传入的源 DLL 所在目录生成 P2+P3、P1+P2+P3 和仅 P3 的诊断变体。这些版本仍是未经验证的实验候选。

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

完整研究结论、补丁偏移、字节序列、哈希、崩溃地址映射和后续调查建议见 [CODEX_CONTEXT_TRANSFER.md](gpt-context/CODEX_CONTEXT_TRANSFER.md)。

## 法律声明

本仓库是独立研究项目，与 Dolby Laboratories 没有从属关系，也未获得其认可。Dolby、Dolby Atmos 和 Dolby Encoding Engine 是其相应所有者的商标或产品。

本项目不授予任何 Dolby 专有软件、许可证或测试媒体。分析或修改软件时，您有责任遵守所有适用的许可证、法律和合同限制。

## 许可证

本仓库中的原创代码与文档依据 [GNU General Public License v3.0](LICENSE) 发布。该许可证不适用于第三方专有二进制文件或媒体。
