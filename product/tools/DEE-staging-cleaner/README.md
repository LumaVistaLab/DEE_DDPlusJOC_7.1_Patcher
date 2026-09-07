# DEE staging cleaner

English | [简体中文](README_zh-CN.md)

`cleanup_dee_staging.py` force-clears compatibility staging roots, including incomplete and unmarked content left when the wrapper exits abnormally.

Run it with no options to delete every automatically discovered `dee-ddp71-wrapper` root and everything below it:

```powershell
python .\tools\DEE-staging-cleaner\cleanup_dee_staging.py
```

`--clean` is an explicit alias for the same default operation:

```powershell
python .\tools\DEE-staging-cleaner\cleanup_dee_staging.py --clean
```

Preview the roots and their direct entries without deleting:

```powershell
python .\tools\DEE-staging-cleaner\cleanup_dee_staging.py --list
```

Force-clear one exact root that is no longer automatically discoverable:

```powershell
python .\tools\DEE-staging-cleaner\cleanup_dee_staging.py `
  --staging-root "D:\Temp\dee-ddp71-wrapper"
```

The cleaner deliberately does not inspect ownership markers, run IDs, or activity locks. Stop any wrapper/DEE job whose stage must be retained before running it. To limit accidental scope, an explicit root must be named exactly `dee-ddp71-wrapper`; linked roots are rejected. Deletion retries briefly for Windows handles that have not yet closed and returns a failure if the operating system continues to deny removal.

The normal wrapper still attempts to remove its own stage after success or handled failure. This tool covers abnormal termination and manual forced cleanup.
