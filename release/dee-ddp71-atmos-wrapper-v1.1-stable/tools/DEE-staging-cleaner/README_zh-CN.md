# DEE 暂存区清理工具

[English](README.md) | 简体中文

`cleanup_dee_staging.py` 用于强制清空兼容暂存根目录，包括包装器异常退出后遗留的不完整、无标记内容。

不带选项运行时，会删除自动发现的全部 `dee-ddp71-wrapper` 根目录及其中所有内容：

```powershell
python .\tools\DEE-staging-cleaner\cleanup_dee_staging.py
```

`--clean` 是同一默认操作的显式别名：

```powershell
python .\tools\DEE-staging-cleaner\cleanup_dee_staging.py --clean
```

如需只查看根目录及其直接条目而不删除：

```powershell
python .\tools\DEE-staging-cleaner\cleanup_dee_staging.py --list
```

强制清空一个已无法自动发现的确切根目录：

```powershell
python .\tools\DEE-staging-cleaner\cleanup_dee_staging.py `
  --staging-root "D:\Temp\dee-ddp71-wrapper"
```

清理器有意不检查所有权标记、运行标识或活动锁。执行前应停止所有仍需保留暂存区的包装器或 DEE 作业。为限制误操作范围，显式指定的根目录名称必须准确为 `dee-ddp71-wrapper`，且链接目录会被拒绝。删除时会针对 Windows 尚未释放的文件句柄进行短暂重试；如果操作系统持续拒绝删除，工具会返回失败。

包装器在正常成功或受控失败后仍会尝试删除自己的暂存区；此工具用于异常终止及用户手动强制清理。
