"""Shared fixtures for prismrag_patch library parity tests."""
from __future__ import annotations

import pytest

from tests.conftest import (
    DOMAIN_CONFIGS,
    FINANCE_MAPPING,
    HEALTHCARE_MAPPING,
    PHARMACY_MAPPING,
)


@pytest.fixture
def healthcare_mapping():
    return HEALTHCARE_MAPPING


@pytest.fixture
def finance_mapping():
    return FINANCE_MAPPING


@pytest.fixture
def pharmacy_mapping():
    return PHARMACY_MAPPING


def inline_records_from_mapping(mapping: dict) -> list[dict]:
    return [
        {"word": r["word"], "text": r["word"].replace("_", " ")}
        for r in mapping["rules"]
    ]


@pytest.fixture
def healthcare_rag(healthcare_mapping):
    from prismrag_patch import PrismRAG

    rag = PrismRAG(mapping=healthcare_mapping, tenant_id="test-healthcare")
    rag.ingest(records=inline_records_from_mapping(healthcare_mapping))
    return rag


@pytest.fixture
def finance_rag(finance_mapping):
    from prismrag_patch import PrismRAG

    rag = PrismRAG(mapping=finance_mapping, tenant_id="test-finance")
    rag.ingest(records=inline_records_from_mapping(finance_mapping))
    return rag


@pytest.fixture
def pharmacy_rag(pharmacy_mapping):
    from prismrag_patch import PrismRAG

    rag = PrismRAG(mapping=pharmacy_mapping, tenant_id="test-pharmacy")
    rag.ingest(records=inline_records_from_mapping(pharmacy_mapping))
    return rag
