-- Pharmacy QA Domain Seed Data
-- Tenant: qa-pharmacy | Mapping: pharma-standard
-- Run after schema.sql

BEGIN;

-- ── QA Tenant ─────────────────────────────────────────────────────────────────
INSERT INTO prismrag.tenant (id, name, plan, owner_user_id)
VALUES ('10000000-0000-0000-0000-000000000002', 'QA PharmaCo', 'professional', '20000000-0000-0000-0000-000000000002')
ON CONFLICT (id) DO NOTHING;

-- ── Mapping ────────────────────────────────────────────────────────────────────
INSERT INTO prismrag.mapping (id, tenant_id, name, strategy, version, is_active)
VALUES ('30000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000002', 'pharma-standard', 'rules', 1, true)
ON CONFLICT (id) DO NOTHING;

-- ── Categories ────────────────────────────────────────────────────────────────
INSERT INTO prismrag.mapping_category (mapping_id, category_slug, category_label, sort_order) VALUES
('30000000-0000-0000-0000-000000000002', 'drug_interactions',   'Drug Interactions',             1),
('30000000-0000-0000-0000-000000000002', 'dosage',              'Dosing & Administration',       2),
('30000000-0000-0000-0000-000000000002', 'contraindications',   'Contraindications & Warnings',  3),
('30000000-0000-0000-0000-000000000002', 'adverse_effects',     'Adverse Effects & Toxicity',    4),
('30000000-0000-0000-0000-000000000002', 'pharmacokinetics',    'Pharmacokinetics & Metabolism', 5),
('30000000-0000-0000-0000-000000000002', 'mechanisms',          'Mechanism of Action',           6),
('30000000-0000-0000-0000-000000000002', 'storage',             'Storage & Stability',           7)
ON CONFLICT DO NOTHING;

-- ── Mapping Rules ─────────────────────────────────────────────────────────────
INSERT INTO prismrag.mapping_rule (mapping_id, word, category_slug, weight) VALUES
-- Drug Interactions
('30000000-0000-0000-0000-000000000002', 'cyp450',                  'drug_interactions', 1.0),
('30000000-0000-0000-0000-000000000002', 'cyp3a4',                  'drug_interactions', 1.0),
('30000000-0000-0000-0000-000000000002', 'inhibitor',               'drug_interactions', 0.8),
('30000000-0000-0000-0000-000000000002', 'inducer',                 'drug_interactions', 0.8),
('30000000-0000-0000-0000-000000000002', 'warfarin_interaction',    'drug_interactions', 1.0),
('30000000-0000-0000-0000-000000000002', 'polypharmacy',            'drug_interactions', 1.0),
('30000000-0000-0000-0000-000000000002', 'drug_drug_interaction',   'drug_interactions', 1.0),
('30000000-0000-0000-0000-000000000002', 'synergistic',             'drug_interactions', 0.9),
-- Dosage
('30000000-0000-0000-0000-000000000002', 'loading_dose',            'dosage',            1.0),
('30000000-0000-0000-0000-000000000002', 'maintenance_dose',        'dosage',            1.0),
('30000000-0000-0000-0000-000000000002', 'maximum_daily_dose',      'dosage',            1.0),
('30000000-0000-0000-0000-000000000002', 'pediatric_dose',          'dosage',            1.0),
('30000000-0000-0000-0000-000000000002', 'renal_dose_adjustment',   'dosage',            1.0),
('30000000-0000-0000-0000-000000000002', 'hepatic_dose_adjustment', 'dosage',            1.0),
('30000000-0000-0000-0000-000000000002', 'titration',               'dosage',            0.9),
-- Contraindications
('30000000-0000-0000-0000-000000000002', 'contraindicated',         'contraindications', 1.0),
('30000000-0000-0000-0000-000000000002', 'pregnancy_category',      'contraindications', 1.0),
('30000000-0000-0000-0000-000000000002', 'renal_failure',           'contraindications', 0.9),
('30000000-0000-0000-0000-000000000002', 'hepatic_impairment',      'contraindications', 0.9),
('30000000-0000-0000-0000-000000000002', 'black_box_warning',       'contraindications', 1.0),
('30000000-0000-0000-0000-000000000002', 'absolute_contraindication','contraindications',1.0),
-- Adverse Effects
('30000000-0000-0000-0000-000000000002', 'hepatotoxicity',          'adverse_effects',   1.0),
('30000000-0000-0000-0000-000000000002', 'nephrotoxicity',          'adverse_effects',   1.0),
('30000000-0000-0000-0000-000000000002', 'qt_prolongation',         'adverse_effects',   1.0),
('30000000-0000-0000-0000-000000000002', 'agranulocytosis',         'adverse_effects',   1.0),
('30000000-0000-0000-0000-000000000002', 'anaphylaxis',             'adverse_effects',   1.0),
('30000000-0000-0000-0000-000000000002', 'serotonin_syndrome',      'adverse_effects',   1.0),
('30000000-0000-0000-0000-000000000002', 'adverse_drug_reaction',   'adverse_effects',   1.0),
-- Pharmacokinetics
('30000000-0000-0000-0000-000000000002', 'half_life',               'pharmacokinetics',  1.0),
('30000000-0000-0000-0000-000000000002', 'bioavailability',         'pharmacokinetics',  1.0),
('30000000-0000-0000-0000-000000000002', 'volume_of_distribution',  'pharmacokinetics',  1.0),
('30000000-0000-0000-0000-000000000002', 'protein_binding',         'pharmacokinetics',  1.0),
('30000000-0000-0000-0000-000000000002', 'clearance',               'pharmacokinetics',  1.0),
('30000000-0000-0000-0000-000000000002', 'first_pass_metabolism',   'pharmacokinetics',  1.0),
('30000000-0000-0000-0000-000000000002', 'peak_plasma_concentration','pharmacokinetics', 1.0),
-- Mechanisms
('30000000-0000-0000-0000-000000000002', 'receptor_agonist',        'mechanisms',        1.0),
('30000000-0000-0000-0000-000000000002', 'receptor_antagonist',     'mechanisms',        1.0),
('30000000-0000-0000-0000-000000000002', 'enzyme_inhibition',       'mechanisms',        1.0),
('30000000-0000-0000-0000-000000000002', 'ion_channel_blockade',    'mechanisms',        1.0),
('30000000-0000-0000-0000-000000000002', 'beta_blocker',            'mechanisms',        1.0),
('30000000-0000-0000-0000-000000000002', 'ace_inhibitor',           'mechanisms',        1.0),
('30000000-0000-0000-0000-000000000002', 'ssri',                    'mechanisms',        1.0),
-- Storage
('30000000-0000-0000-0000-000000000002', 'refrigerate',             'storage',           1.0),
('30000000-0000-0000-0000-000000000002', 'light_sensitive',         'storage',           1.0),
('30000000-0000-0000-0000-000000000002', 'expiry_date',             'storage',           1.0),
('30000000-0000-0000-0000-000000000002', 'cold_chain',              'storage',           1.0),
('30000000-0000-0000-0000-000000000002', 'room_temperature',        'storage',           1.0)
ON CONFLICT DO NOTHING;

-- ── Sample knowledge chunks ───────────────────────────────────────────────────
INSERT INTO prismrag.chunk (id, tenant_id, mapping_id, chunk_ref, source_ref, text_snippet, category_slug) VALUES
('40000000-0000-0000-0000-000000000201', '10000000-0000-0000-0000-000000000002', '30000000-0000-0000-0000-000000000002',
 'ph-chunk-001', 'drug-monographs', 'Warfarin: CYP2C9 substrate with narrow therapeutic index. Interactions with amiodarone (CYP2C9 inhibitor) significantly increase INR. Monitor INR closely when co-administering.', 'drug_interactions'),
('40000000-0000-0000-0000-000000000202', '10000000-0000-0000-0000-000000000002', '30000000-0000-0000-0000-000000000002',
 'ph-chunk-002', 'drug-monographs', 'Metformin dosage: loading dose not required. Start 500mg BD with meals, titrate to max 2g/day. Reduce dose when eGFR 30-45 mL/min/1.73m2. Contraindicated if eGFR <30.', 'dosage'),
('40000000-0000-0000-0000-000000000203', '10000000-0000-0000-0000-000000000002', '30000000-0000-0000-0000-000000000002',
 'ph-chunk-003', 'drug-monographs', 'SSRIs contraindicated with MAOIs — risk of life-threatening serotonin syndrome. Minimum 14-day washout period required between MAOI and SSRI initiation.', 'contraindications'),
('40000000-0000-0000-0000-000000000204', '10000000-0000-0000-0000-000000000002', '30000000-0000-0000-0000-000000000002',
 'ph-chunk-004', 'drug-monographs', 'Acetaminophen hepatotoxicity: maximum daily dose 4g adults, 2g in hepatic impairment. Risk increases with alcohol co-ingestion. ALT elevation signals early toxicity.', 'adverse_effects'),
('40000000-0000-0000-0000-000000000205', '10000000-0000-0000-0000-000000000002', '30000000-0000-0000-0000-000000000002',
 'ph-chunk-005', 'drug-monographs', 'Amoxicillin pharmacokinetics: oral bioavailability 90%, half-life 1.0–1.5 hours, renal excretion 60–80% unchanged. Protein binding 17%. Extend dosing interval in renal failure.', 'pharmacokinetics'),
('40000000-0000-0000-0000-000000000206', '10000000-0000-0000-0000-000000000002', '30000000-0000-0000-0000-000000000002',
 'ph-chunk-006', 'drug-monographs', 'Beta-blockers mechanism: competitive antagonism of beta-1 and beta-2 adrenergic receptors. Reduce heart rate, decrease myocardial contractility, lower blood pressure.', 'mechanisms'),
('40000000-0000-0000-0000-000000000207', '10000000-0000-0000-0000-000000000002', '30000000-0000-0000-0000-000000000002',
 'ph-chunk-007', 'drug-monographs', 'Insulin storage: refrigerate at 2-8 degrees C unopened. Once opened, vials can be kept at room temperature up to 28 days. Protect from light and freezing. Check expiry date.', 'storage')
ON CONFLICT DO NOTHING;

COMMIT;
