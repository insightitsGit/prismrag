"""Unit tests for ingest request validation (no database required)."""
import uuid

import pytest
from pydantic import ValidationError

from prismrag.models import JobRequest, MappingConfigIn, SourceType


TENANT = uuid.uuid4()

VALID_MAPPING = {
    "categories": [
        {"slug": "risk", "label": "Risk"},
        {"slug": "growth", "label": "Growth"},
    ],
    "rules": [
        {"word": "volatility", "category_slug": "risk"},
        {"word": "alpha", "category_slug": "growth"},
    ],
}


class TestMappingConfigIn:
    def test_valid_mapping(self):
        m = MappingConfigIn.model_validate(VALID_MAPPING)
        assert len(m.rules) == 2

    def test_empty_categories_rejected(self):
        with pytest.raises(ValidationError) as exc:
            MappingConfigIn.model_validate({"categories": [], "rules": VALID_MAPPING["rules"]})
        assert "categories" in str(exc.value)

    def test_empty_rules_rejected(self):
        with pytest.raises(ValidationError) as exc:
            MappingConfigIn.model_validate({
                "categories": VALID_MAPPING["categories"],
                "rules": [],
            })
        assert "rules" in str(exc.value)

    def test_unknown_category_slug_rejected(self):
        with pytest.raises(ValidationError) as exc:
            MappingConfigIn.model_validate({
                "categories": VALID_MAPPING["categories"],
                "rules": [{"word": "foo", "category_slug": "nonexistent"}],
            })
        assert "unknown category_slug" in str(exc.value)

    def test_duplicate_words_rejected(self):
        with pytest.raises(ValidationError) as exc:
            MappingConfigIn.model_validate({
                "categories": VALID_MAPPING["categories"],
                "rules": [
                    {"word": "alpha", "category_slug": "risk"},
                    {"word": "alpha", "category_slug": "growth"},
                ],
            })
        assert "duplicate words" in str(exc.value)

    def test_invalid_slug_format_rejected(self):
        with pytest.raises(ValidationError) as exc:
            MappingConfigIn.model_validate({
                "categories": [{"slug": "Bad-Slug", "label": "Bad"}],
                "rules": [{"word": "x", "category_slug": "bad-slug"}],
            })
        assert "slug" in str(exc.value).lower()


class TestJobRequest:
    def _inline_job(self, **overrides):
        base = {
            "tenant_id": str(TENANT),
            "source_type": "inline",
            "strategy": "rules",
            "mapping": VALID_MAPPING,
            "inline_config": {
                "records": [{"word": "volatility", "text": "market volatility"}],
            },
        }
        base.update(overrides)
        return JobRequest.model_validate(base)

    def test_valid_inline_job(self):
        job = self._inline_job()
        assert job.source_type == SourceType.inline

    def test_api_without_config_rejected(self):
        with pytest.raises(ValidationError) as exc:
            JobRequest.model_validate({
                "tenant_id": str(TENANT),
                "source_type": "api",
                "strategy": "rules",
                "mapping": VALID_MAPPING,
            })
        assert "api_config" in str(exc.value)

    def test_api_with_config_accepted(self):
        job = JobRequest.model_validate({
            "tenant_id": str(TENANT),
            "source_type": "api",
            "strategy": "rules",
            "mapping": VALID_MAPPING,
            "api_config": {"url": "https://example.com/data"},
        })
        assert job.api_config.url == "https://example.com/data"

    def test_cross_config_pollution_rejected(self):
        with pytest.raises(ValidationError) as exc:
            JobRequest.model_validate({
                "tenant_id": str(TENANT),
                "source_type": "inline",
                "strategy": "rules",
                "mapping": VALID_MAPPING,
                "inline_config": {"records": [{"word": "a"}]},
                "api_config": {"url": "https://example.com"},
            })
        assert "api_config" in str(exc.value)

    def test_mapping_required_for_rules(self):
        with pytest.raises(ValidationError) as exc:
            JobRequest.model_validate({
                "tenant_id": str(TENANT),
                "source_type": "inline",
                "strategy": "rules",
                "inline_config": {"records": [{"word": "a"}]},
            })
        assert "mapping is required" in str(exc.value)
