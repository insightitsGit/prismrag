# PyPI publish — prismrag-patch

## One-time setup

1. Create an API token at [pypi.org/manage/account/token/](https://pypi.org/manage/account/token/) (scope: entire account or project `prismrag-patch`).

2. Add GitHub repository secret:

```bash
gh secret set PYPI_API_TOKEN -R aminparva84/InsightPrismRAG
# paste token when prompted
```

## Publish (automated)

Push a tag matching `pyproject.toml` version:

```bash
git tag v0.2.1
git push origin v0.2.1
```

GitHub Actions workflow **Publish — PyPI** builds and uploads the wheel.

## Publish (manual)

```bash
cd prismrag_patch
pip install build twine
python -m build
twine upload dist/*
```

Use `__token__` as username and your PyPI API token as password.

## Verify

```bash
pip install "prismrag-patch[graph]==0.2.1"
python -c "from prismrag_patch import PrismRAG; print(PrismRAG)"
```
