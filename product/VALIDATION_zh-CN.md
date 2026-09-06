# 特殊字符路径实机验证

验证日期：2026-09-06  
产品版本：`0.1.0-dev`  
编码器：Dolby Encoding Engine `5.2.1-5994839`

## 范围

本次在 `product/work/` 内从 `dee_copy` 建立了一个 85 文件、810,751,824 字节的临时 DEE 包。目录名故意同时包含中文、空格、`[]`、`+`、`&`、`'`、`#`、`,`、`;`、`=`、`!`、`@`、`%` 与 `()`：

```text
work/路径验证 [Win+&' #,;=!@%]/DEE v5.2.1 临时包 [A+B] &(原版)' #,;=!@%
```

临时包的原始 `dee_audio_filter_ddp_atmos.dll` SHA-256 为：

```text
3d66bcec36031fd48e6565d15f05fea656642377ca4f8c98cdce1cce8b7e95d2
```

绝对路径和相对路径各运行一次平面 7.1 分段批量编码。两次均设置：

- `timecode_frame_rate=24`
- `time_base=file_position`
- 首段 `start=0`（`file_start`）
- 分段点 `00:00:10:00`、`00:00:20:00`、`00:00:30:00`
- `compatibility_layout=flat-7.1`
- 默认 `data_rate=1152`、`preferred_downmix_mode=ltrt`

绝对路径运行清单：`work/runs/20260906-232420-573c8c10/run.json`。  
相对路径运行清单：`work/runs/20260906-232726-50d2fdc9/run.json`。

相对路径测试从 `product` 启动，包装器脚本、DEE 目录、母带和输出基础路径均以相对路径传入；绝对路径测试中四者均以绝对路径传入。

## XML 边界

两次运行生成的四个作业完全一致：

| 段 | `<start>` | `<end>` |
|---:|---|---|
| 1 | `0` | `00:00:10:00` |
| 2 | `00:00:10:00` | `00:00:20:00` |
| 3 | `00:00:20:00` | `00:00:30:00` |
| 4 | `00:00:30:00` | `end_of_file` |

## 输出一致性与结构

绝对路径与相对路径的对应输出逐字节一致：

| 段 | 字节数 | SHA-256 | AC-3 核心帧 | E-AC-3 dependent 帧 |
|---:|---:|---|---:|---:|
| 1 | 1,442,304 | `1fcde1061c8b8b20ecff33af6104bc3f74865f9475230bf8443bbb7011d84c2d` | 313 | 313 |
| 2 | 1,442,304 | `384acfd3f8c106a90be8e425ecd6b87a009a4b5cda8b21222a7d296ad96fcff5` | 313 | 313 |
| 3 | 1,442,304 | `ec48308f4a2f8ad4186833c3f4106dac0150b52ecee4e6b99588cd8bad550e8f` | 313 | 313 |
| 4 | 33,564,672 | `477e8ff735a68844a62226ae75f25ca3ec0c7ea87e6126d1025909edc745c85f` | 7,284 | 7,284 |

对全部 8 个文件运行独立 `patch_dsur_ex.py --check`：

- 每个 AC-3 核心帧均为 `dsurexmod=2`；
- 全部文件 AC-3 CRC mismatch 均为 0；
- 每个核心帧和 dependent 帧均为 2,304 字节；
- `ffprobe` 对四个唯一输出均报告 `eac3`、`Dolby Digital Plus + Dolby Atmos`、8 声道、`7.1`、48 kHz、1,152,000 bit/s；
- MediaInfo 对四段均报告 `Blu-ray Disc`、`L R C LFE Ls Rs Lb Rb` 和 `Dolby Surround EX`。MediaInfo 仅在第 1、4 段的商业名称中附加 `with Dolby Atmos`，但 `ffprobe` 和逐帧扫描在四段中均识别 Atmos dependent/JOC 数据。

## 恢复结果

两份 `run.json` 均为 `status=complete`、`safe_runtime_stage_removed=true`，并记录恢复后的 DLL SHA-256 为原始哈希。最终再次读取特殊字符路径源包，哈希仍为 `3d66bcec...e95d2`；特殊字符源包本身未被补丁。

验证使用普通 Windows 进程上下文。受限测试沙箱会令这些专有编码插件统一返回 Windows 1114；相同 `dee_copy --print-stages` 在普通进程上下文中退出 0，因此该现象不属于路径或包装器故障。
