"""PrismRAG — API-level job validation (submit-time business rules)."""
from __future__ import annotations

from fastapi import HTTPException

from prismrag.metering.quota import check_feature
from prismrag.models import JobRequest, SourceType, StrategyType


def validate_job_submit(
    request: JobRequest,
    user: dict,
    *,
    allow_file_source: bool = False,
) -> None:
    """
    Enforce plan and routing rules that Pydantic models cannot express alone.
    Raises HTTPException before a job is queued.
    """
    plan = user.get("plan", "free")

    if request.strategy == StrategyType.mlp:
        check_feature(plan, "mlp_train")

    if request.strategy == StrategyType.cluster:
        raise HTTPException(
            status_code=422,
            detail="strategy 'cluster' is not yet available. Use 'rules' or 'mlp'.",
        )

    if request.strategy == StrategyType.external_api:
        raise HTTPException(
            status_code=422,
            detail="strategy 'external_api' is not yet available. Use 'rules' or 'mlp'.",
        )

    if request.source_type == SourceType.file and not allow_file_source:
        raise HTTPException(
            status_code=422,
            detail=(
                'source_type "file" must be submitted via multipart '
                "POST /api/prismrag/jobs/upload with a CSV or Excel file."
            ),
        )

    if request.source_type == SourceType.file and allow_file_source:
        fname = (request.file_config.filename if request.file_config else "").lower()
        if not fname:
            raise HTTPException(status_code=422, detail="file_config.filename is required.")
        if not any(fname.endswith(ext) for ext in (".csv", ".tsv", ".xlsx", ".xls")):
            raise HTTPException(
                status_code=422,
                detail="Unsupported file type. Accepted: .csv, .tsv, .xlsx, .xls",
            )


def validate_file_columns(upload_bytes: bytes, file_config: "FileSourceConfig") -> None:
    """Ensure uploaded CSV/Excel contains required word (and optional text) columns."""
    from prismrag.models import FileSourceConfig

    if not isinstance(file_config, FileSourceConfig):
        return

    from prismrag.adapters.file import FileAdapter

    adapter = FileAdapter(upload_bytes, file_config)
    rows = adapter._load()
    if not rows:
        raise HTTPException(status_code=422, detail="Uploaded file contains no data rows.")

    headers = {k.strip().lower() for k in rows[0].keys()}
    wcol = file_config.word_column.lower()
    if wcol not in headers:
        raise HTTPException(
            status_code=422,
            detail=f"Uploaded file is missing required column '{file_config.word_column}'. "
            f"Found columns: {sorted(headers)}",
        )
    if file_config.category_column:
        ccol = file_config.category_column.lower()
        if ccol not in headers:
            raise HTTPException(
                status_code=422,
                detail=f"category_column '{file_config.category_column}' not found in file headers.",
            )


def validate_file_category_hints(
    upload_bytes: bytes,
    file_config: "FileSourceConfig",
    mapping: "MappingConfigIn",
) -> None:
    """Reject file rows whose category_column values are not in mapping.categories."""
    from prismrag.adapters.file import FileAdapter

    if not file_config.category_column:
        return

    slug_set = {c.slug for c in mapping.categories}
    adapter = FileAdapter(upload_bytes, file_config)
    ccol = file_config.category_column
    bad: set[str] = set()
    for row in adapter._load():
        hint = str(row.get(ccol) or "").strip().lower()
        if hint and hint not in slug_set:
            bad.add(hint)
    if bad:
        raise HTTPException(
            status_code=422,
            detail=(
                f"File column '{ccol}' contains category values not in mapping.categories: "
                f"{sorted(bad)}. Valid slugs: {sorted(slug_set)}"
            ),
        )


def parse_mapping_json(raw: str) -> "MappingConfigIn":
    """Parse mapping JSON from multipart form field."""
    import json

    from prismrag.models import MappingConfigIn

    if not raw or not raw.strip():
        raise HTTPException(
            status_code=422,
            detail="mapping is required (JSON string with categories and rules).",
        )
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"mapping must be valid JSON: {exc.msg}",
        ) from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="mapping must be a JSON object.")
    try:
        return MappingConfigIn.model_validate(data)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
