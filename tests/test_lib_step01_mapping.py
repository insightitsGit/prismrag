"""Step 1 — mapping / projection parity."""
import numpy as np
import pytest

from prismrag_patch.core import PrismRAGPatch
from prismrag_patch.mapping.projection import project_sem_to_personal, projection_matrix
from prismrag_patch.mapping.rules import RulesStrategy
from tests.conftest import HEALTHCARE_MAPPING
from tests.fixtures.lib_conftest import inline_records_from_mapping


class TestStep01Mapping:
    def test_no_license_required(self):
        patch = PrismRAGPatch(mapping=HEALTHCARE_MAPPING)
        assert patch.category_for("diabetes medication metformin") is not None

    def test_rules_strategy_assigns_category(self):
        strat = RulesStrategy(HEALTHCARE_MAPPING)
        res = strat.assign("metformin", "metformin for diabetes")
        assert res.category_slug == "medication"
        assert res.embedding.shape == (256,)
        assert res.sem_embedding.shape == (768,)

    def test_projection_matrix_stable(self):
        m1 = projection_matrix()
        m2 = projection_matrix()
        assert np.allclose(m1, m2)
        assert m1.shape == (256, 768)

    def test_category_hint_fallback(self):
        strat = RulesStrategy(HEALTHCARE_MAPPING)
        res = strat.assign("unknown_word_xyz", "some text", category_hint="lab_results")
        assert res.category_slug == "lab_results"

    def test_batch_assign(self):
        strat = RulesStrategy(HEALTHCARE_MAPPING)
        records = [(r["word"], r["word"], None) for r in HEALTHCARE_MAPPING["rules"][:5]]
        out = strat.assign_batch(records)
        assert len(out) == 5

    def test_768d_remap_uses_rules_projection(self):
        strat = RulesStrategy(HEALTHCARE_MAPPING)
        sem = strat.assign("insulin", "insulin therapy").sem_embedding
        patch = PrismRAGPatch(mapping=HEALTHCARE_MAPPING)
        remapped = np.array(patch.remap_vector(sem.tolist(), "insulin therapy"))
        expected = project_sem_to_personal(
            sem, "medication", [c["slug"] for c in HEALTHCARE_MAPPING["categories"]]
        )
        assert np.allclose(remapped, expected, atol=1e-5)

    @pytest.mark.parametrize("word,expected", [
        ("metformin", "medication"),
        ("troponin", "lab_results"),
        ("drug_allergy", "patient_safety"),
    ])
    def test_infer_category(self, word, expected):
        strat = RulesStrategy(HEALTHCARE_MAPPING)
        assert strat.lookup_category(word) == expected
