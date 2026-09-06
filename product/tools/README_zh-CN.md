# patch_dsur_ex.py

[English](README.md) | 简体中文

这是主封装器调用的独立 Dolby Surround EX 标志处理脚本。它没有集成进 `dee-ddp71-atmos-wrapper.py`，以便后续单独更新、测试和审计。

来源：

- [https://github.com/LumaVistaLab/DolbySurrEX-flag-patcher](https://github.com/LumaVistaLab/DolbySurrEX-flag-patcher)
- 固定 commit：`2966e09`
- 本仓库参考版本：`DolbySurrEX-flag-patcher-2966e09`

脚本扫描交织 Blu-ray DD+ 码流中的 AC-3 核心和 E-AC-3 dependent/JOC 帧，把符合严格结构要求的 AC-3 核心 `dsurexmod` 改为目标值并重算两处 AC-3 CRC。它不修改 dependent/JOC 帧，不生成 PLIIx 矩阵，也不把任意 Lo/Ro 或普通 5.1 码流转换成平面 7.1。

## 用法

只检查结构、帧计数、现有标志和 CRC：

```powershell
python .\patch_dsur_ex.py --check input.eb3
```

写入新的输出，默认将 `dsurexmod` 设为 `2`（Dolby Surround EX）：

```powershell
python .\patch_dsur_ex.py input.eb3 output.dsur-ex.eb3
```

显式选择目标值：

```powershell
python .\patch_dsur_ex.py input.eb3 output.eb3 --target 0
python .\patch_dsur_ex.py input.eb3 output.eb3 --target 1
python .\patch_dsur_ex.py input.eb3 output.eb3 --target 2
```

`--target` 允许值：`0` = not indicated，`1` = not EX，`2` = EX。`--no-strict` 会跳过不符合预期的 AC-3 帧；正式封装器不使用该选项，而是保留严格检查。

输入和输出必须是不同路径。脚本不会原地覆盖输入。只应对已经确认含有 PLIIx 矩阵兼容核心的平面 7.1 DEE 输出使用它。

许可证见产品的 [GNU GPL v3 许可证](../LICENSE)。
