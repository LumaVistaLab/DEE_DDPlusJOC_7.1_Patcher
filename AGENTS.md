# Repository working rules

These rules apply to all future development and release work in this repository.

## Internal and product version maintenance

- The agent is responsible for maintaining the internal version in `product/dee-ddp71-atmos-wrapper.py`.
- Increase the internal version when development reaches an appropriate version boundary. Use semantic intent: patch for compatible fixes, minor for compatible features, and major for incompatible behavior or interface changes. Documentation-only edits normally do not require an internal-version bump.
- The internal version identifies the development stream. The product version identifies a packaged release and does not have to match the internal version.
- Do not change historical validation metadata merely to make it match a newer internal or product version. Update validation metadata only when the corresponding validation is actually rerun for that product state.

## Independent README maintenance

- `product/README.md` and `product/README_zh-CN.md` describe the active development product.
- The English and Chinese README files inside `release/` describe the packaged release snapshot.
- Product README files and release README files are independent documents. Neither set is subordinate to, generated from, or automatically synchronized with the other.
- Update each set deliberately for its own context. Do not overwrite one set by copying the other without reviewing every release-specific or development-specific statement and link.
- Record the product version in both release README files. Do not change the embedded internal version solely to match a product version.

## Local release policy

- Build releases only under the repository-local `release/` directory unless the user explicitly requests another destination.
- Do not create, edit, upload, or delete a GitHub Release unless the user explicitly requests it.
- Keep only the newest local release in `release/`. Older releases are recovered from Git history rather than retained as parallel directories or archives.
- Before replacing an old local release, inspect Git status and ensure the old release state is recoverable from Git. Preserve unrelated or uncommitted user changes.
- Do not use a version-only directory such as `release/v1.0-stable/`.
- For product version `<version>`, use package name `dee-ddp71-atmos-wrapper-<version>` consistently:
  - unpacked directory: `release/dee-ddp71-atmos-wrapper-<version>/`
  - archive: `release/dee-ddp71-atmos-wrapper-<version>.zip`
  - archive checksum: `release/dee-ddp71-atmos-wrapper-<version>.zip.sha256`
- The ZIP must contain exactly one top-level directory named `dee-ddp71-atmos-wrapper-<version>`. Do not place release files directly at the ZIP root.

## Release package contents

The runtime release should contain only the files needed by users:

```text
dee-ddp71-atmos-wrapper.py
LICENSE
README.md
README_zh-CN.md
RELEASE_NOTES.md
SHA256SUMS.txt
templates/
  atmos_mezz_encode_to_atmos_ddp_ec3.xml
tools/
  DEE-staging-cleaner/
    cleanup_dee_staging.py
    README.md
    README_zh-CN.md
  DolbySurrEX-flag-patcher-2966e09/
    patch_dsur_ex.py
    README.md
    README_zh-CN.md
```

Do not include development or generated material, including:

- `.gitignore`
- `tests/`
- `VALIDATION.md`
- `VALIDATION_zh-CN.md`
- `__pycache__/`
- `backups/`
- `work/`
- Dolby proprietary binaries, licenses, test media, or user media

Release README files and release notes may summarize completed validation, but must not link to or instruct users to run files excluded from the package.

## Release procedure

1. Inspect Git status and the current contents of `release/`.
2. Decide whether the internal version should be increased for the accumulated development changes; update it when appropriate.
3. Run the product compilation checks and automated tests from `product/` before packaging.
4. Remove the previous local release artifacts after confirming they are recoverable from Git.
5. Create the correctly named release directory and copy only the approved runtime files.
6. Maintain the release README files independently and record the product version in them. Update the bilingual `RELEASE_NOTES.md` for the packaged snapshot.
7. Scan release documentation for stale links or references to excluded development files.
8. Generate `SHA256SUMS.txt` after all packaged files are final.
9. Create the correctly named ZIP with the matching single top-level directory, then generate its `.zip.sha256` file.
10. Inspect the ZIP file list, verify all per-file and archive checksums, and confirm that no excluded or proprietary files are present.
