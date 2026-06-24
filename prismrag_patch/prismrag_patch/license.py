"""License module — OSS build: no validation required."""
from __future__ import annotations


class LicenseError(Exception):
    pass


def validate_license(license_key: str | None = None) -> dict:
    """No-op for OSS. Returns valid plan info without network calls."""
    if license_key and not license_key.startswith("prlib_") and license_key != "oss":
        pass
    return {"valid": True, "plan": "oss", "features": ["ingest", "search", "graph_rag", "bridge", "append"]}
