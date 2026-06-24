# PyPI publish — prismrag-patch

## Current release

| Version | Status | URL |
|---------|--------|-----|
| **0.2.1** | ✅ Published on PyPI (2026-06-17, local CLI) | https://pypi.org/project/prismrag-patch/0.2.1/ |

```bash
pip install "prismrag-patch[graph]==0.2.1"
```

---

## One-time setup

1. Create an API token at [pypi.org/manage/account/token/](https://pypi.org/manage/account/token/) (scope: entire account or project `prismrag-patch`).

2. *(Optional)* Add GitHub repository secret for CI publishes:

```bash
gh secret set PYPI_API_TOKEN -R aminparva84/InsightPrismRAG
```

---

## Publish (manual — recommended)

```powershell
cd prismrag_patch
pip install build twine
Remove-Item -Recurse -Force dist -ErrorAction SilentlyContinue
python -m build

$env:TWINE_USERNAME = "__token__"
$env:TWINE_PASSWORD = "pypi-YOUR_TOKEN"
twine upload dist/*
```

Use `__token__` as username and your PyPI API token as password.

---

## Publish (GitHub Actions)

Push a tag matching `pyproject.toml` version **only if that version is not already on PyPI**:

```bash
git tag v0.2.2
git push origin v0.2.2
```

Workflow: `.github/workflows/publish-pypi.yml`

---

## Verify

```bash
pip install "prismrag-patch[graph]==0.2.1"
python -c "from prismrag_patch import PrismRAG; print(PrismRAG)"
```

---

## Next release

1. Bump `version` in `prismrag_patch/pyproject.toml`
2. Build + `twine upload` (or push new `v*` tag)
3. Update `INFO.md` / README version line if needed
