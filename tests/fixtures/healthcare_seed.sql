-- Healthcare QA Domain Seed Data
-- Tenant: qa-healthcare | Mapping: clinical-standard
-- Run after schema.sql and auth_schema.sql

BEGIN;

-- ── QA Tenant + User ──────────────────────────────────────────────────────────
INSERT INTO prismrag.tenant (id, name, plan, owner_user_id)
VALUES ('10000000-0000-0000-0000-000000000001', 'QA Healthcare Clinic', 'professional', '20000000-0000-0000-0000-000000000001')
ON CONFLICT (id) DO NOTHING;

-- ── Mapping ────────────────────────────────────────────────────────────────────
INSERT INTO prismrag.mapping (id, tenant_id, name, strategy, version, is_active)
VALUES ('30000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'clinical-standard', 'rules', 1, true)
ON CONFLICT (id) DO NOTHING;

-- ── Categories ────────────────────────────────────────────────────────────────
INSERT INTO prismrag.mapping_category (mapping_id, category_slug, category_label, sort_order) VALUES
('30000000-0000-0000-0000-000000000001', 'diagnosis',       'Diagnosis & Classification',    1),
('30000000-0000-0000-0000-000000000001', 'symptoms',        'Symptoms & Clinical Signs',     2),
('30000000-0000-0000-0000-000000000001', 'treatment',       'Treatment & Therapy',           3),
('30000000-0000-0000-0000-000000000001', 'medication',      'Medication & Pharmacotherapy',  4),
('30000000-0000-0000-0000-000000000001', 'procedures',      'Clinical Procedures',           5),
('30000000-0000-0000-0000-000000000001', 'lab_results',     'Laboratory Results',            6),
('30000000-0000-0000-0000-000000000001', 'patient_safety',  'Patient Safety & Risk',         7)
ON CONFLICT DO NOTHING;

-- ── Mapping Rules ─────────────────────────────────────────────────────────────
INSERT INTO prismrag.mapping_rule (mapping_id, word, category_slug, weight) VALUES
-- Diagnosis
('30000000-0000-0000-0000-000000000001', 'hypertension',        'diagnosis',      1.0),
('30000000-0000-0000-0000-000000000001', 'diabetes',            'diagnosis',      1.0),
('30000000-0000-0000-0000-000000000001', 'pneumonia',           'diagnosis',      1.0),
('30000000-0000-0000-0000-000000000001', 'sepsis',              'diagnosis',      1.0),
('30000000-0000-0000-0000-000000000001', 'myocardial_infarction','diagnosis',     1.0),
('30000000-0000-0000-0000-000000000001', 'stroke',              'diagnosis',      1.0),
('30000000-0000-0000-0000-000000000001', 'asthma',              'diagnosis',      1.0),
('30000000-0000-0000-0000-000000000001', 'copd',                'diagnosis',      1.0),
('30000000-0000-0000-0000-000000000001', 'atrial_fibrillation', 'diagnosis',      1.0),
-- Symptoms
('30000000-0000-0000-0000-000000000001', 'dyspnea',             'symptoms',       1.0),
('30000000-0000-0000-0000-000000000001', 'chest_pain',          'symptoms',       1.0),
('30000000-0000-0000-0000-000000000001', 'tachycardia',         'symptoms',       1.0),
('30000000-0000-0000-0000-000000000001', 'hypotension',         'symptoms',       1.0),
('30000000-0000-0000-0000-000000000001', 'fever',               'symptoms',       1.0),
('30000000-0000-0000-0000-000000000001', 'altered_consciousness','symptoms',      1.0),
('30000000-0000-0000-0000-000000000001', 'cyanosis',            'symptoms',       1.0),
('30000000-0000-0000-0000-000000000001', 'edema',               'symptoms',       1.0),
-- Treatment
('30000000-0000-0000-0000-000000000001', 'antibiotics',         'treatment',      1.0),
('30000000-0000-0000-0000-000000000001', 'dialysis',            'treatment',      1.0),
('30000000-0000-0000-0000-000000000001', 'oxygen_therapy',      'treatment',      1.0),
('30000000-0000-0000-0000-000000000001', 'mechanical_ventilation','treatment',    1.0),
('30000000-0000-0000-0000-000000000001', 'physiotherapy',       'treatment',      1.0),
('30000000-0000-0000-0000-000000000001', 'chemotherapy',        'treatment',      1.0),
('30000000-0000-0000-0000-000000000001', 'radiotherapy',        'treatment',      1.0),
-- Medication
('30000000-0000-0000-0000-000000000001', 'metformin',           'medication',     1.0),
('30000000-0000-0000-0000-000000000001', 'lisinopril',          'medication',     1.0),
('30000000-0000-0000-0000-000000000001', 'warfarin',            'medication',     1.0),
('30000000-0000-0000-0000-000000000001', 'heparin',             'medication',     1.0),
('30000000-0000-0000-0000-000000000001', 'amoxicillin',         'medication',     1.0),
('30000000-0000-0000-0000-000000000001', 'insulin',             'medication',     1.0),
('30000000-0000-0000-0000-000000000001', 'aspirin',             'medication',     1.0),
('30000000-0000-0000-0000-000000000001', 'statins',             'medication',     1.0),
-- Procedures
('30000000-0000-0000-0000-000000000001', 'ecg',                 'procedures',     1.0),
('30000000-0000-0000-0000-000000000001', 'echocardiogram',      'procedures',     1.0),
('30000000-0000-0000-0000-000000000001', 'biopsy',              'procedures',     1.0),
('30000000-0000-0000-0000-000000000001', 'endoscopy',           'procedures',     1.0),
('30000000-0000-0000-0000-000000000001', 'ct_scan',             'procedures',     1.0),
('30000000-0000-0000-0000-000000000001', 'mri',                 'procedures',     1.0),
('30000000-0000-0000-0000-000000000001', 'coronary_angiography','procedures',     1.0),
-- Lab Results
('30000000-0000-0000-0000-000000000001', 'hba1c',               'lab_results',    1.0),
('30000000-0000-0000-0000-000000000001', 'creatinine',          'lab_results',    1.0),
('30000000-0000-0000-0000-000000000001', 'troponin',            'lab_results',    1.0),
('30000000-0000-0000-0000-000000000001', 'white_blood_cell',    'lab_results',    1.0),
('30000000-0000-0000-0000-000000000001', 'hemoglobin',          'lab_results',    1.0),
('30000000-0000-0000-0000-000000000001', 'inr',                 'lab_results',    1.0),
('30000000-0000-0000-0000-000000000001', 'blood_glucose',       'lab_results',    1.0),
-- Patient Safety
('30000000-0000-0000-0000-000000000001', 'drug_allergy',        'patient_safety', 1.0),
('30000000-0000-0000-0000-000000000001', 'fall_risk',           'patient_safety', 1.0),
('30000000-0000-0000-0000-000000000001', 'pressure_ulcer',      'patient_safety', 1.0),
('30000000-0000-0000-0000-000000000001', 'medication_error',    'patient_safety', 1.0),
('30000000-0000-0000-0000-000000000001', 'hospital_acquired_infection','patient_safety',1.0),
('30000000-0000-0000-0000-000000000001', 'anaphylaxis',         'patient_safety', 1.0)
ON CONFLICT DO NOTHING;

-- ── Sample knowledge chunks (for retrieval testing) ───────────────────────────
-- These are synthetic clinical note excerpts, not real patient data

INSERT INTO prismrag.chunk (id, tenant_id, mapping_id, chunk_ref, source_ref, text_snippet, category_slug) VALUES
('40000000-0000-0000-0000-000000000101', '10000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001',
 'hc-chunk-001', 'clinical-notes', 'Patient presents with hypertension and elevated blood glucose (HbA1c 9.2%). Prescribed metformin 500mg BD. Advised low-sodium diet.', 'diagnosis'),
('40000000-0000-0000-0000-000000000102', '10000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001',
 'hc-chunk-002', 'clinical-notes', 'ECG shows atrial fibrillation with rapid ventricular rate. Initiated rate control with beta-blockers. INR 2.5 on warfarin therapy.', 'procedures'),
('40000000-0000-0000-0000-000000000103', '10000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001',
 'hc-chunk-003', 'clinical-notes', 'Post-operative patient with fever 38.9C and elevated WBC 14,000. Suspicion of hospital-acquired pneumonia. Started amoxicillin IV empirically.', 'symptoms'),
('40000000-0000-0000-0000-000000000104', '10000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001',
 'hc-chunk-004', 'clinical-notes', 'STEMI confirmed by troponin elevation and ECG changes. Patient transferred for emergency coronary angiography. Aspirin 300mg loading dose administered.', 'lab_results'),
('40000000-0000-0000-0000-000000000105', '10000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001',
 'hc-chunk-005', 'clinical-notes', 'Drug allergy flagged: patient has documented penicillin allergy (anaphylaxis). Switching to azithromycin. Fall risk assessment score 4/6 — bed rails up.', 'patient_safety'),
('40000000-0000-0000-0000-000000000106', '10000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001',
 'hc-chunk-006', 'clinical-notes', 'Mechanical ventilation initiated for ARDS. PEEP 8 cmH2O, FiO2 60%. Daily spontaneous breathing trials. Creatinine rising — consider nephrology consult.', 'treatment'),
('40000000-0000-0000-0000-000000000107', '10000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001',
 'hc-chunk-007', 'clinical-notes', 'Type 2 diabetes management: HbA1c reduced from 9.2% to 7.1% over 6 months. Insulin dose titrated down. Referral to physiotherapy for peripheral neuropathy.', 'medication')
ON CONFLICT DO NOTHING;

COMMIT;
