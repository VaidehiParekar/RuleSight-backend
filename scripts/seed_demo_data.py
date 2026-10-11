"""Seed benchmark demo data for RuleSight.

Loads the benchmark RBI corpus (KYC Master Direction 2016, NSM v1/v2),
Nova Trust bank policies, Risk Control Matrix, and audit evidence into PostgreSQL
via raw parameterized SQL INSERT statements.
"""

from sqlalchemy import create_engine, text

from app.core.config import get_settings


def seed_database() -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url.get_secret_value())

    print("Seeding database via raw SQL...")

    with engine.begin() as conn:
        # 1. Documents
        conn.execute(
            text("""
                INSERT INTO documents (
                    id, doc_type, title, reference, regulator, version_label, supersedes_id,
                    is_synthetic, status, withdrawn_note, created_at
                ) VALUES
                ('doc-kyc', 'regulation', 'Master Direction – Know Your Customer (KYC) Direction, 2016',
                 'Selected paragraphs · updated as on 14 Aug 2025', 'RBI', 'Updated 14 Aug 2025', NULL,
                 FALSE, 'ready', NULL, '2026-10-11T13:41:00+05:30'),
                ('doc-nsm-v2', 'regulation', 'Master Direction on Note Sorting Machines',
                 'RBI/DCM/2026-27/473 · DCM(NPD) No.S2154/18.00.014/2026-27', 'RBI', 'v2 · 2 Oct 2026', 'doc-nsm-v1',
                 FALSE, 'ready', NULL, '2026-10-11T13:52:00+05:30'),
                ('doc-nsm-v1', 'regulation', 'Note Sorting Machines: Standards issued by the Bureau of Indian Standards',
                 'RBI/2024-2025/86 · DCM (NPD) No.S2193/09.45.000/2024-25', 'RBI', 'v1 · 30 Oct 2024', NULL,
                 FALSE, 'superseded', 'Withdrawn from 2 Oct 2026 by Master Direction DCM(NPD) No.S2154/18.00.014/2026-27, Annex row 4.', '2026-10-11T13:42:00+05:30'),
                ('doc-pol-01', 'policy', 'POL-01 Nova Trust KYC/AML Policy', 'POL-01', NULL, 'Policy document', NULL,
                 TRUE, 'ready', NULL, '2026-10-11T13:43:00+05:30'),
                ('doc-pol-03', 'policy', 'POL-03 Nova Trust Digital Onboarding SOP (Video KYC)', 'POL-03', NULL, 'SOP', NULL,
                 TRUE, 'ready', NULL, '2026-10-11T13:44:00+05:30'),
                ('doc-pol-04', 'policy', 'POL-04 Nova Trust Currency Operations & Note Sorting SOP', 'POL-04', NULL, 'SOP', NULL,
                 TRUE, 'ready', NULL, '2026-10-11T13:45:00+05:30')
                ON CONFLICT (id) DO NOTHING;
            """)
        )

        # 2. Controls
        conn.execute(
            text("""
                INSERT INTO controls (
                    id, code, name, description, owner, frequency, control_type, automation,
                    source_document, source_section, source_quote, evidence_expected, rbi_reference, topic
                ) VALUES
                ('ctl-02', 'CTL-02', 'Customer risk categorisation review',
                 'Risk category assigned at onboarding; Compliance reviews categories once a year.',
                 'Compliance - KYC Unit', 'Annual', 'Detective', 'Semi-automated', 'POL-01', '§2 CTL-02',
                 'Risk categories are reviewed once every calendar year.', 'Risk review sign-off', 'RBI KYC para 37(a)', 'CDD'),
                ('ctl-04', 'CTL-04', 'Beneficial ownership identification',
                 'Identify and verify natural persons with more than 25% ownership in corporate customers.',
                 'Corporate Banking Operations', 'Per event', 'Preventive', 'Manual', 'POL-01', '§2 CTL-04',
                 'The threshold for controlling ownership interest is 25%.', 'BO declaration forms', 'RBI KYC para 3', 'Beneficial Ownership'),
                ('ctl-05', 'CTL-05', 'Periodic KYC updation tracking',
                 'Re-KYC every 3 years (High), 8 years (Medium), 10 years (Low); monthly due list generated.',
                 'Compliance - KYC Unit', 'Monthly', 'Detective', 'Semi-automated', 'POL-01', '§2 CTL-05',
                 'High-risk customers shall undergo periodic updation once every three years.', 'Periodic KYC status report', 'RBI KYC para 38', 'CDD Periodic Updation'),
                ('ctl-09', 'CTL-09', 'Record retention',
                 'Transaction and identity records kept 8 years after account closure.',
                 'Records Management', 'Continuous', 'Preventive', 'Automated', 'POL-01', '§2 CTL-09',
                 'All transaction records preserved for eight years.', 'Retention configuration', 'RBI KYC para 46(a) and 46(b)', 'Record Retention'),
                ('ctl-10', 'CTL-10', 'Principal Officer & Designated Director appointment',
                 'PO and DD appointed and communicated to FIU-IND; separation of the two roles not stated in policy.',
                 'Company Secretary', 'Per event', 'Preventive', 'Manual', 'POL-01', '§2 CTL-10',
                 'The Bank shall appoint a Principal Officer and a Designated Director.', 'FIU communication letter', 'RBI KYC para 6(d)', 'Governance'),
                ('ctl-17', 'CTL-17', 'Video KYC session verification',
                 'Agent checks OVD on camera, face match, three security questions; no live GPS geo-tagging or liveness check.',
                 'Digital Banking Operations', 'Per event', 'Preventive', 'Manual', 'POL-03', '§2 CTL-17',
                 'Agent verifies photograph and identity document via video interface.', 'Session checklist', 'RBI KYC para 18(a)(iv) and 18(a)(v)', 'V-CIP'),
                ('ctl-18', 'CTL-18', 'Video KYC recording cloud storage',
                 'Recordings stored on vendor cloud for 8 years; storage location not stated.',
                 'Digital Banking Operations', 'Per event', 'Preventive', 'Automated', 'POL-03', '§2 CTL-18',
                 'Recordings encrypted and stored with third-party cloud partner.', 'Vendor contract', 'RBI KYC para 18(c)(i)', 'V-CIP Storage'),
                ('ctl-19', 'CTL-19', 'NSM testing and calibration',
                 'Half-yearly accuracy test with a 1,000-note test deck; vendor recalibrates above 5% error.',
                 'Branch Operations', 'Half-yearly', 'Detective', 'Manual', 'POL-04', '§2 CTL-19',
                 'Machines tested half-yearly with 1,000 test notes.', 'Test certificates', 'NSM v2 para 7 and Testing Procedure', 'NSM Testing'),
                ('ctl-20', 'CTL-20', 'NSM BIS-certified procurement',
                 'Only BIS-certified (IS 18663:2024) NSM models purchased since 1 May 2025.',
                 'Procurement', 'Per event', 'Preventive', 'Manual', 'POL-04', '§2 CTL-20',
                 'All new machines require valid BIS licence.', 'Purchase orders with BIS licence', 'NSM v2 para 8.2', 'NSM Procurement'),
                ('ctl-21', 'CTL-21', 'Note sorting machine fitness configuration',
                 'Vendor configures machines to RBI authentication and fitness parameters.',
                 'Currency Management', 'Per event', 'Preventive', 'Automated', 'POL-04', '§2 CTL-21',
                 'Machines configured per current RBI fitness standards.', 'Vendor configuration certificate', 'NSM v2 paras 2.2, 2.3, 4, 5', 'NSM Configuration')
                ON CONFLICT (id) DO NOTHING;
            """)
        )

        # 3. Obligations
        conn.execute(
            text("""
                INSERT INTO obligations (
                    id, code, document_id, source_label, clause_ref, page, source_quote, key_phrase,
                    quote_verified, summary, actor, action, condition, frequency, deadline, threshold,
                    topic, criticality, applicability, applicability_reason, coverage, review_status, created_at
                ) VALUES
                ('ob-01', 'OB-01', 'doc-kyc', 'RBI KYC MD 2016', 'para 3', 8,
                 'Controlling ownership interest for the purpose of identifying beneficial owner means ownership of or entitlement to more than 10 per cent of shares or capital or profits of the juridical person.',
                 'more than 10 per cent', TRUE, 'Identify beneficial owners holding >10% of shares or capital',
                 'Regulated Entity', 'identify beneficial owners', 'corporate customers', 'Onboarding', NULL, '> 10%',
                 'Beneficial Ownership', 2, 'applicable', NULL, 'partial', 'accepted', now()),
                ('ob-02', 'OB-02', 'doc-kyc', 'RBI KYC MD 2016', 'para 6(d)', 12,
                 'The Designated Director shall not be the Principal Officer.',
                 'shall not be the Principal Officer', TRUE, 'Designated Director and Principal Officer must be separate individuals',
                 'Regulated Entity', 'ensure role separation', NULL, 'Continuous', NULL, 'Different persons',
                 'Governance', 1, 'applicable', NULL, 'insufficient_info', 'suggested', now()),
                ('ob-03', 'OB-03', 'doc-kyc', 'RBI KYC MD 2016', 'para 18(a)(iv)', 21,
                 'Live GPS geo-tagging shall be incorporated in the video recording to ascertain the physical location of the customer in India.',
                 'Live GPS geo-tagging', TRUE, 'V-CIP video onboarding must incorporate live GPS geo-tagging',
                 'Regulated Entity', 'incorporate live GPS geo-tagging', 'during V-CIP', 'Per session', NULL, 'Live GPS coordinate match',
                 'V-CIP', 2, 'applicable', NULL, 'none', 'suggested', now()),
                ('ob-04', 'OB-04', 'doc-kyc', 'RBI KYC MD 2016', 'para 18(a)(v)', 22,
                 'The application shall employ software for face liveness / spoof detection to prevent fraudulent onboarding.',
                 'face liveness / spoof detection', TRUE, 'Employ face liveness / spoof detection software in V-CIP',
                 'Regulated Entity', 'employ spoof and liveness detection', 'during V-CIP', 'Per session', NULL, 'Liveness verification score',
                 'V-CIP', 2, 'applicable', NULL, 'partial', 'suggested', now()),
                ('ob-05', 'OB-05', 'doc-kyc', 'RBI KYC MD 2016', 'para 18(c)(i)', 24,
                 'The video recordings and customer identification data shall be stored safely in server locations strictly within the territory of India.',
                 'strictly within the territory of India', TRUE, 'V-CIP audio-visual recordings must reside on servers in India',
                 'Regulated Entity', 'store V-CIP data within India', NULL, 'Continuous', NULL, 'India server jurisdiction',
                 'V-CIP Storage', 2, 'applicable', NULL, 'insufficient_info', 'suggested', now()),
                ('ob-06', 'OB-06', 'doc-kyc', 'RBI KYC MD 2016', 'para 37(a)', 34,
                 'Regulated Entities shall review customer risk categorisation at least once in every six months.',
                 'at least once in every six months', TRUE, 'Review customer risk categorisation at least once every 6 months',
                 'Regulated Entity', 'review customer risk categories', NULL, 'Half-yearly', NULL, 'Every 6 months',
                 'CDD', 2, 'applicable', NULL, 'partial', 'suggested', now()),
                ('ob-07', 'OB-07', 'doc-kyc', 'RBI KYC MD 2016', 'para 38', 35,
                 'Periodic updation of KYC shall be carried out at least once in every two years for high-risk customers, eight years for medium-risk customers and ten years for low-risk customers.',
                 'once in every two years for high-risk customers', TRUE, 'Periodic KYC updation every 2 years for high-risk customers',
                 'Regulated Entity', 'carry out Periodic Updation of KYC', 'for high-risk accounts', 'Every 2 years', NULL, '2 years (High risk)',
                 'CDD Periodic Updation', 2, 'applicable', NULL, 'partial', 'accepted', now()),
                ('ob-10', 'OB-10', 'doc-kyc', 'RBI KYC MD 2016', 'para 70', 58,
                 'Regulated Entities shall have an on-going employee training programme so that the staff members are adequately trained in KYC procedures.',
                 'on-going employee training programme', TRUE, 'Maintain ongoing employee KYC/AML training programme',
                 'Regulated Entity', 'conduct ongoing employee training', NULL, 'Annual', NULL, '100% staff covered',
                 'Training', 1, 'applicable', NULL, 'none', 'suggested', now()),
                ('ob-11', 'OB-11', 'doc-kyc', 'RBI KYC MD 2016', 'para 68', 56,
                 'Primary Co-operative Banks shall adhere to special provisions when providing at-par cheque facilities.',
                 'Primary Co-operative Banks', TRUE, 'At-par cheque provisions applicable only to cooperative banks',
                 'Primary Co-operative Banks', 'comply with at-par cheque facility', 'if cooperative bank', 'Continuous', NULL, 'Co-op banks only',
                 'Governance', 1, 'not_applicable', 'Nova Trust Bank is a Scheduled Commercial Bank, not a primary co-operative bank.', 'not_applicable', 'accepted', now()),
                ('ob-nsm-01', 'NG-01-OB', 'doc-nsm-v2', 'RBI NSM v2 2026', 'para 7', 14,
                 'The sorting machines shall be tested for detection of counterfeit notes and sorting accuracy at quarterly intervals.',
                 'at quarterly intervals', TRUE, 'Test sorting machines for accuracy and counterfeit detection quarterly',
                 'Bank', 'test machines for accuracy', NULL, 'Quarterly', NULL, 'Quarterly test log',
                 'NSM Testing', 2, 'applicable', NULL, 'partial', 'accepted', now()),
                ('ob-nsm-03', 'NG-03-OB', 'doc-nsm-v2', 'RBI NSM v2 2026', 'para 8.2', 17,
                 'All existing note sorting machines that do not conform to BIS standard IS 18663:2024 shall be phased out by 30 June 2027.',
                 'phased out by 30 June 2027', TRUE, 'Phase out non-BIS sorting machines by 30 June 2027',
                 'Bank', 'phase out non-compliant machines', 'fleet machines', 'One-time', '2027-06-30', '100% BIS compliant fleet',
                 'NSM Fleet', 2, 'applicable', NULL, 'none', 'accepted', now())
                ON CONFLICT (id) DO NOTHING;
            """)
        )

        # 4. Gaps
        conn.execute(
            text("""
                INSERT INTO gaps (
                    id, code, obligation_id, gap_type, title, description, control_ids, evidence_ids,
                    origin, change_id, risk_factors, risk_score, priority, status, created_at
                ) VALUES
                ('g-07', 'G-07', 'ob-07', 'design_operating',
                 'High-risk Periodic Updation cycle set to 3 years instead of 2; 18.4% accounts overdue',
                 'Nova Trust POL-01 sets high-risk re-KYC cycle to 3 years instead of RBI-mandated 2 years. Evidence EVD-02 shows 18.4% of high-risk customer accounts overdue and 2,105 unlisted accounts.',
                 '["ctl-05"]'::jsonb, '["evd-02"]'::jsonb, 'initial', NULL,
                 '{"criticality": 2, "severity": 3.0, "urgency": 1.0, "rule_version": "v1"}'::jsonb,
                 6.00, 'P1', 'potential', now()),
                ('ng-01', 'NG-01', 'ob-nsm-01', 'design_operating',
                 'Machine accuracy testing conducted half-yearly instead of quarterly; Q3 2026 missing',
                 'POL-04 mandates half-yearly testing with 1,000 notes instead of RBI-mandated quarterly testing with 2,000 notes. Evidence EVD-07 confirms no accuracy test was conducted in Q3 2026.',
                 '["ctl-19"]'::jsonb, '["evd-07"]'::jsonb, 'initial', NULL,
                 '{"criticality": 2, "severity": 3.0, "urgency": 1.0, "rule_version": "v1"}'::jsonb,
                 6.00, 'P1', 'potential', now()),
                ('ng-03', 'NG-03', 'ob-nsm-03', 'missing',
                 'Seven discontinued note sorting machines operating without phase-out plan',
                 'RBI Master Direction mandates phase-out of non-BIS sorting machines by 30 June 2027. Nova Trust currently operates 7 discontinued machines across 5 currency chests with no active replacement plan.',
                 '[]'::jsonb, '["evd-06"]'::jsonb, 'change', 'chg-01',
                 '{"criticality": 2, "severity": 3.0, "urgency": 1.5, "rule_version": "v1"}'::jsonb,
                 9.00, 'P1', 'potential', now()),
                ('g-01', 'G-01', 'ob-01', 'design',
                 'Beneficial ownership threshold in policy set to 25% instead of RBI-mandated 10%',
                 'Nova Trust POL-01 identifies beneficial owners at 25% ownership threshold, failing RBI para 3 mandate of 10%.',
                 '["ctl-04"]'::jsonb, '[]'::jsonb, 'initial', NULL,
                 '{"criticality": 2, "severity": 2.0, "urgency": 1.0, "rule_version": "v1"}'::jsonb,
                 4.00, 'P2', 'potential', now()),
                ('g-08', 'G-08', 'ob-10', 'missing',
                 'No documented ongoing employee KYC/AML training programme in POL-01',
                 'POL-01 contains no formal curriculum, frequency or attendance threshold for employee KYC/AML training.',
                 '[]'::jsonb, '[]'::jsonb, 'initial', NULL,
                 '{"criticality": 1, "severity": 3.0, "urgency": 1.0, "rule_version": "v1"}'::jsonb,
                 3.00, 'P2', 'potential', now()),
                ('g-02', 'G-02', 'ob-02', 'insufficient_info',
                 'Policy does not explicitly require Designated Director and Principal Officer to be different persons',
                 'POL-01 §2 CTL-10 notes appointment of both roles but does not document that they must be separate individuals.',
                 '["ctl-10"]'::jsonb, '[]'::jsonb, 'initial', NULL,
                 '{"criticality": 1, "severity": 1.0, "urgency": 1.0, "rule_version": "v1"}'::jsonb,
                 1.00, 'P3', 'potential', now())
                ON CONFLICT (id) DO NOTHING;
            """)
        )

        # 5. Remediations
        conn.execute(
            text("""
                INSERT INTO remediations (
                    id, gap_id, action, owner_team, target_days, closure_evidence, status, created_at
                ) VALUES
                ('rem-07', 'g-07',
                 'Amend POL-01 §2 CTL-05 to mandate 2-year re-KYC for High-risk accounts; clear 18.4% overdue backlog.',
                 'Compliance - KYC Unit', 45, 'Revised policy approval and zero-delinquency status report', 'draft', now()),
                ('rem-ng-01', 'ng-01',
                 'Update POL-04 §2 CTL-19 to quarterly testing with 2,000-note test decks; execute immediate branch calibration.',
                 'Currency Management / Branch Operations', 15, 'Signed quarterly calibration test certificates', 'draft', now()),
                ('rem-ng-03', 'ng-03',
                 'Issue RFP for replacing 7 discontinued note sorting machines; ensure delivery before 30 June 2027.',
                 'Procurement / Currency Management', 90, 'Vendor purchase orders with BIS certification licences', 'draft', now())
                ON CONFLICT (id) DO NOTHING;
            """)
        )

        # 6. Evidence
        conn.execute(
            text("""
                INSERT INTO evidence (
                    id, code, title, file_name, control_codes, columns, rows, flagged_cells, summary, created_at
                ) VALUES
                ('evd-02', 'EVD-02', 'High-Risk Periodic Updation Delinquency Report (Sep 2026)',
                 'EVD-02_Periodic_KYC_Overdue_Report_Sep2026.csv',
                 '["CTL-05"]'::jsonb,
                 '["Risk Category", "Total Accounts", "Overdue > 2 Yrs", "Overdue %", "Accounts Unlisted"]'::jsonb,
                 '[["High Risk", "12,450", "2,291", "18.4%", "2,105"], ["Medium Risk", "84,200", "1,120", "1.3%", "0"], ["Low Risk", "310,000", "2,450", "0.8%", "0"]]'::jsonb,
                 '[[0, 2], [0, 3], [0, 4]]'::jsonb,
                 '18.4% of High-Risk accounts are overdue beyond the 2-year RBI limit. 2,105 customer accounts are completely missing from the automated due list.',
                 now()),
                ('evd-06', 'EVD-06', 'Currency Chest Machine Fleet Inventory (Oct 2026)',
                 'EVD-06_Machine_Inventory_Oct2026.csv',
                 '["CTL-20"]'::jsonb,
                 '["Chest Branch", "Machine Model", "Units", "BIS Status", "Phase-out Required"]'::jsonb,
                 '[["Mumbai Main", "Glory USF-51", "3", "Discontinued", "Yes (by 30 Jun 2027)"], ["Delhi Central", "Kisan K2", "2", "Discontinued", "Yes (by 30 Jun 2027)"], ["Bengaluru", "G&D ProNote", "2", "Discontinued", "Yes (by 30 Jun 2027)"], ["Kolkata", "Glory UW-F4", "4", "BIS Certified", "No"]]'::jsonb,
                 '[[0, 3], [1, 3], [2, 3]]'::jsonb,
                 'Seven sorting machines across Mumbai, Delhi, and Bengaluru are discontinued models requiring phase-out by 30 June 2027.',
                 now()),
                ('evd-07', 'EVD-07', 'Branch Note Sorting Machine Calibration Log (Q3 2026)',
                 'EVD-07_NSM_Calibration_Log_Q3_2026.csv',
                 '["CTL-19"]'::jsonb,
                 '["Branch Code", "Machine ID", "Test Date", "Test Deck Size", "Accuracy %", "Signed Certificate"]'::jsonb,
                 '[["B-0101", "NSM-MUM-01", "2026-03-15", "1,000", "99.2%", "Yes"], ["B-0101", "NSM-MUM-01", "2026-06-20", "1,000", "99.1%", "Yes"], ["B-0101", "NSM-MUM-01", "None", "None", "Lapsed", "Missing"]]'::jsonb,
                 '[[2, 2], [2, 4], [2, 5]]'::jsonb,
                 'Branch NSM testing was not performed for Q3 2026 (Jul-Sep 2026). Test deck used in prior quarters was 1,000 notes instead of RBI-required 2,000 notes.',
                 now())
                ON CONFLICT (id) DO NOTHING;
            """)
        )

        # 7. Regulatory Changes
        conn.execute(
            text("""
                INSERT INTO changes (
                    id, old_document_id, new_document_id, clause_ref, change_type, title,
                    old_text, new_text, summary, significance, carried_over, impact, created_at
                ) VALUES
                ('chg-01', 'doc-nsm-v1', 'doc-nsm-v2', 'para 8.2', 'modified',
                 'Phase-out deadline for discontinued note sorting machines',
                 'Banks may continue using existing machines while maintaining manufacturer maintenance contracts.',
                 'All existing note sorting machines that do not conform to BIS standard IS 18663:2024 shall be phased out by 30 June 2027.',
                 'Introduces a hard deadline of 30 June 2027 to replace discontinued machines. Affects 7 machines in Nova Trust inventory.',
                 'high',
                 '["Authentication standards (para 2.2)", "Fitness criteria (para 5)"]'::jsonb,
                 '{"controls": ["CTL-20"], "gaps": ["NG-03"]}'::jsonb,
                 now())
                ON CONFLICT (id) DO NOTHING;
            """)
        )

        # 8. Missing circulars
        conn.execute(
            text("""
                INSERT INTO missing_circulars (
                    id, document_id, row_num, reference, circular_date, subject, created_at
                ) VALUES
                ('mc-01', 'doc-nsm-v2', 1, 'RBI/2024-25/86 · DCM(NPD) No.S2193/09.45.000/2024-25', '30 Oct 2024',
                 'Note Sorting Machines: Standards issued by the Bureau of Indian Standards', now()),
                ('mc-02', 'doc-nsm-v2', 2, 'RBI/2025-26/18 · DCM(NPD) No.S342/09.45.000/2025-26', '24 Apr 2025',
                 'Revised Timeline for Implementation of Note Sorting Machine Standards', now()),
                ('mc-03', 'doc-nsm-v2', 3, 'RBI/2025-26/45 · DCM(NPD) No.S812/09.45.000/2025-26', '12 Jun 2025',
                 'Clarification on Machine Testing Protocols for Remote Branches', now()),
                ('mc-04', 'doc-nsm-v2', 4, 'RBI/2025-26/92 · DCM(NPD) No.S1402/09.45.000/2025-26', '19 Sep 2025',
                 'Standard Operating Procedures for Note Sorting Machine Recalibration', now())
                ON CONFLICT (id) DO NOTHING;
            """)
        )

        # 9. Audit Log
        conn.execute(
            text("""
                INSERT INTO audit_log (
                    id, at, actor, actor_role, action, entity_type, entity_code, reason, before, after
                ) VALUES
                ('au-001', '2026-10-11T13:46:00+05:30', 'Priya Sharma', 'Compliance Officer',
                 'Reviewed baseline gap', 'gap', 'G-07', 'Confirmed P1 priority based on EVD-02 evidence.',
                 '{"status": "potential"}'::jsonb, '{"status": "confirmed"}'::jsonb),
                ('au-002', '2026-10-11T13:48:00+05:30', 'Rahul Mehta', 'Analyst',
                 'Accepted obligation quote', 'obligation', 'OB-07', 'Verbatim quote verified against RBI KYC para 38.',
                 '{"review_status": "suggested"}'::jsonb, '{"review_status": "accepted"}'::jsonb),
                ('au-003', '2026-10-11T13:52:00+05:30', 'Priya Sharma', 'Compliance Officer',
                 'Evaluated regulatory change', 'change', 'chg-01', 'Approved cascade creation of P1 gap NG-03.',
                 NULL, '{"created_gap": "NG-03"}'::jsonb)
                ON CONFLICT (id) DO NOTHING;
            """)
        )

        # 10. Agent Runs
        conn.execute(
            text("""
                INSERT INTO agent_runs (
                    id, run_id, started_at, trigger, cache_hits, status, nodes, created_at
                ) VALUES
                ('run-7f3a', '7f3a', '2026-10-11T13:59:21+05:30',
                 'Upload of NSM Master Direction (supersedes v1)', 0, 'done',
                 '[{"node": "extract_obligations", "status": "done", "offset_ms": 0, "duration_ms": 11500, "llm_calls": 3, "input_tokens": 8200, "output_tokens": 1420, "note": "Extracted obligations from KYC MD and NSM texts with verbatim quotes", "conditional": false}, {"node": "check_applicability", "status": "done", "offset_ms": 11500, "duration_ms": 2200, "llm_calls": 1, "input_tokens": 2800, "output_tokens": 450, "note": "Evaluated scope against Scheduled Commercial Bank profile", "conditional": false}, {"node": "extract_controls", "status": "done", "offset_ms": 13700, "duration_ms": 3800, "llm_calls": 2, "input_tokens": 5100, "output_tokens": 980, "note": "Ingested 10 controls from RCM CSV and internal policies", "conditional": false}, {"node": "map_candidates", "status": "done", "offset_ms": 17500, "duration_ms": 9400, "llm_calls": 5, "input_tokens": 12400, "output_tokens": 2100, "note": "Traversed NetworkX graph across shared topics and evaluated coverage", "conditional": false}, {"node": "critic_verify", "status": "done", "offset_ms": 26900, "duration_ms": 1600, "llm_calls": 0, "input_tokens": 0, "output_tokens": 0, "note": "Code assertion verified 100% of quotes are exact substrings in source text", "conditional": false}, {"node": "assess_evidence", "status": "done", "offset_ms": 28500, "duration_ms": 6200, "llm_calls": 4, "input_tokens": 9800, "output_tokens": 1650, "note": "Parsed EVD-02, EVD-06, EVD-07 audit tables and flagged delinquency cells", "conditional": false}, {"node": "detect_gaps", "status": "done", "offset_ms": 34700, "duration_ms": 400, "llm_calls": 0, "input_tokens": 0, "output_tokens": 0, "note": "Evaluated 5-category deterministic decision tree across all obligations", "conditional": false}, {"node": "score_risk", "status": "done", "offset_ms": 35100, "duration_ms": 200, "llm_calls": 0, "input_tokens": 0, "output_tokens": 0, "note": "Calculated Criticality * Severity * Urgency into P1/P2/P3 priority bands", "conditional": false}, {"node": "draft_remediation", "status": "done", "offset_ms": 35300, "duration_ms": 4600, "llm_calls": 2, "input_tokens": 6400, "output_tokens": 1100, "note": "Drafted corrective action plans with SLA targets", "conditional": false}, {"node": "diff_versions", "status": "done", "offset_ms": 39900, "duration_ms": 3800, "llm_calls": 2, "input_tokens": 7200, "output_tokens": 1250, "note": "Change intelligence: NSM v1 to v2 comparison & Annex circular audit", "conditional": true}, {"node": "impact_analysis", "status": "done", "offset_ms": 43700, "duration_ms": 1800, "llm_calls": 1, "input_tokens": 3100, "output_tokens": 580, "note": "Cascaded changed clauses through graph to flag NG-03 as P1 gap", "conditional": true}]'::jsonb,
                 '2026-10-11T13:59:21+05:30')
                ON CONFLICT (id) DO NOTHING;
            """)
        )

        print("Successfully seeded all benchmark demo tables!")


if __name__ == "__main__":
    seed_database()
