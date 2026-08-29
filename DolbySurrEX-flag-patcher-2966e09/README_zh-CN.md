# Dolby Surround EX 标志补丁工具

语言：简体中文 | [English](README.md)

本仓库包含一个 Python 补丁工具，用于处理 Dolby Media Producer Suite v2.0
（DMPS v2.0）的一种特定输出情况：Blu-ray Dolby Digital Plus with Dolby
Atmos `.eb3` 码流，其 7.1 Lrs/Rrs 音频核心使用 `5.1 Dolby PLIIx`
进行 7.1 到 5.1 下混，但 AC-3 核心元数据没有声明 Dolby Surround EX。

该工具会把 AC-3 核心中的 `dsurexmod` 字段改为 MediaInfo 报告
`Format settings: Dolby Surround EX` 时对应的值，并重新计算 AC-3 CRC 字。

---

## 目录

- [项目结构](#项目结构)
- [使用场景与前提](#使用场景与前提)
- [已观察到的码流结构](#已观察到的码流结构)
- [使用方法](#使用方法)
- [验证运行](#验证运行)
- [参考资料](#参考资料)

---

## 项目结构

```text
DolbySurrEX-flag-patcher/
|-- patch_dsur_ex.py                         AC-3 核心 dsurexmod 补丁与扫描工具。
|-- README.md                                英文文档。
|-- README_zh-CN.md                          简体中文文档。
|-- LICENSE
|-- .gitignore                               排除本地安装包、工作区文件和 Python 缓存输出。
|-- Dolby_Media_Encoder_User's_Manual.pdf    Dolby Media Encoder 手册，用于文档中的参考资料。
|-- Sol Levante.png                          PLIIx 样例编码所用的 DMPS v2.0 设置截图。
|-- Encoder Setup.png                        当前样例编码所用的 DMPS v2.0 Encoder Setup 截图。
|-- Escape.eb3                               参考 DD+ Atmos 样例，其 AC-3 核心已声明 EX。
|-- Sol Levante.eb3                          补丁前的源 DD+ Atmos 样例。
`-- Sol Levante.dsur-ex.eb3                  dsurexmod 已设为 EX 的补丁后样例输出。
```

`Dolby Media Producer Suite 2.0-2976134.pkg`、`Dolby Media Producer Suite 2.5-5200991.dmg`、
`DolbySurrEX-flag-patcher.code-workspace` 和 `__pycache__/` 已被有意忽略。这些路径只用于
本地安装包、编辑器设置或生成缓存；上方结构描述的是当前受跟踪的活动补丁工具包。

## 使用场景与前提

仅在同时满足以下条件时使用本补丁工具：

- 源文件是 Blu-ray profile Dolby Digital Plus with Dolby Atmos / E-AC-3
  JOC `.eb3` 码流。
- 音频核心声道配置为 `7.1 - L,R,C,LFE,Ls,Rs,Lrs,Rrs`。
- DMPS v2.0 任务使用的 `7.1 to 5.1 Downmix` 为 `5.1 Dolby PLIIx`，
  而不是 `5.1 Standard`。
- 目标是把向后兼容的 5.1 表示标记为包含矩阵编码的后环绕信息。

`5.1 Dolby PLIIx` 这个前提很重要。Dolby 手册把 PLIIx 描述为一种矩阵系统，
可从 5.1 信号导出后环绕声道；手册也说明 Dolby Digital Surround EX 的码流标志会被复用于
Dolby TrueHD、Dolby Digital Plus 或 Dolby Digital 5.1 声道表示，用来指示矩阵编码的
后环绕信号，也包括 7.1 码流在仅支持 5.1 的系统上解码时听到的 5.1 表示。见参考资料 [3]
和 [4]。

`Sol Levante.png` 展示了样例输出所用的 DMPS v2.0 设置：

![DMPS v2.0 声道设置：7.1 Lrs/Rrs 核心与 5.1 Dolby PLIIx 下混](Sol%20Levante.png)

当前 `Sol Levante.eb3` 样例已使用启用
`Encoder Setup > Preprocessing > Apply Magnetic Centroid` 的设置重新编码。
该设置见 `Encoder Setup.png`：

![DMPS v2.0 Encoder Setup 预处理设置：启用 Apply Magnetic Centroid](Encoder%20Setup.png)

不要把本工具当成通用 DD+ 或 Atmos 修复工具。如果编码使用的是
`5.1 Standard (Lo, Ro)` 下混，设置 EX 标志会错误描述该码流。

## 已观察到的码流结构

两个样例文件都是 Blu-ray profile DD+ Atmos 码流。每个 1536-sample access unit
为 6656 字节：

- 2560 字节 AC-3 核心 syncframe，640 kb/s
- 4096 字节 E-AC-3 dependent/JOC syncframe，1024 kb/s

这与 DMPS v2.0 呈现 Dolby Digital Plus Blu-ray 任务的方式一致：在 Channels 页面选择
向后兼容的 audio core；对于 Atmos DD+ 码流，5.1 核心是先把 Atmos 渲染到 7.1，再把四个
环绕声道下混到两个 5.1 环绕声道生成的。手册列出了相关选项：
`5.1 Dolby Standard (Lo, Ro)` 和 `5.1 Dolby PLIIx`。见参考资料 [1] 和 [2]。

相关标志位位于 AC-3 核心的 extended bitstream information：

```text
bsid=6
acmod=7
lfeon=1
xbsi1e=1
dmixmod=1
xbsi2e=1
dsurexmod=<target>
```

`Escape.eb3` 每个 AC-3 核心帧中的 `dsurexmod=2`，MediaInfo 会报告为
`Format settings: Dolby Surround EX`。

`Sol Levante.eb3` 每个 AC-3 核心帧中的 `dsurexmod=0`。由于其 DMPS v2.0 任务使用了
`5.1 Dolby PLIIx`，本仓库把 `Escape.eb3` 视为参考写入行为，并把 `Sol Levante.eb3`
补丁到相同的 `dsurexmod=2` 状态。

对于当前样例，`dsurexmod` 从每个 AC-3 核心帧的第 90 bit 开始。在字节层面上，这会把核心
byte 11 从 `0x40` 改为 `0x60`，并同时更新核心 bytes 2-3 处的 AC-3 CRC1 字。
E-AC-3 dependent/JOC 帧不会被修改。

## 使用方法

仅扫描：

```powershell
python .\patch_dsur_ex.py --check "Sol Levante.eb3"
```

补丁到新文件：

```powershell
python .\patch_dsur_ex.py "Sol Levante.eb3" "Sol Levante.dsur-ex.eb3"
```

如果某个 AC-3 核心帧不符合预期的 `bsid=6`、`acmod=7`、`lfeon=1`、`xbsi2e=1`
结构，或者输入 AC-3 CRC 已经无效，工具会拒绝补丁。

## 验证运行

当前本地验证结果：

```text
Escape.eb3:
  AC-3 core frames: 7013
  E-AC-3 dependent frames: 7013
  dsurexmod counts: {2: 7013}
  AC-3 CRC mismatches: 0

Sol Levante.eb3:
  AC-3 core frames: 8222
  E-AC-3 dependent frames: 8222
  dsurexmod counts: {0: 8222}
  AC-3 CRC mismatches: 0

Sol Levante.dsur-ex.eb3:
  AC-3 core frames: 8222
  E-AC-3 dependent frames: 8222
  dsurexmod counts: {2: 8222}
  AC-3 CRC mismatches: 0
```

MediaInfo 会对 `Sol Levante.dsur-ex.eb3` 报告
`Format settings: Dolby Surround EX`。

## 参考资料

[1] Dolby Media Encoder User's Manual，4.1.3 节，"Selecting Source Material
(Encoding Configurations) for Encoding"，印刷页 p. 18 / PDF p. 28。对于 Dolby
Digital Plus with Dolby Atmos，手册说明向后兼容表示由 `Audio Core Channel Configuration`
设置。

[2] Dolby Media Encoder User's Manual，4.1.4 节，"Setting the 5.1 Downmix
Type on the Channels Page"，印刷页 pp. 18-19 / PDF pp. 28-29，以及 4.5 节
Dolby Digital Plus workflow，印刷页 p. 33 / PDF p. 43。这些章节说明 5.1 核心会在需要时
先把 Atmos 渲染到 7.1，再把 7.1 环绕声道下混到 5.1；相关选项为
`5.1 Dolby Standard (Lo, Ro)` 和 `5.1 Dolby PLIIx`。

[3] Dolby Media Encoder User's Manual，11.11 节，"Dolby Pro Logic IIx"，
印刷页 pp. 94-95 / PDF pp. 104-105。该节把 PLIIx 定义为一种矩阵解码系统，可导出后环绕声道，
包括从独立 Ls/Rs 声道进行 5.1 到 7.1 的操作。

[4] Dolby Media Encoder User's Manual，11.13 节，"Dolby Digital Surround EX"，
印刷页 p. 96 / PDF p. 106。该节说明 EX 码流标志表示矩阵编码的后环绕信号，并被复用于
Dolby TrueHD、Dolby Digital Plus 和 Dolby Digital 5.1 表示，也包括 7.1 码流在 5.1-capable
系统上得到的 5.1 表示。
