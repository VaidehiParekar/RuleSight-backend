# RuleSight demo dataset: answer key

This is the "correct answer" for the synthetic dataset. Use it to:
1. **Measure accuracy** (precision and recall for obligations, mappings, gaps, changes, and conflicts). Show these numbers on the dashboard as proof of D2 reliability.
2. **Check the demo** before going on stage.

**Do not feed this folder to the agents.** It is only for evaluation.

The machine-readable version for obligations, mappings and gaps is [expected_mappings.csv](expected_mappings.csv).

---

## 1. Obligations to extract (27)

- **REG-KYC v2:** 17 obligations (OB-01 to OB-18, excluding OB-07).
- **REG-KYC v1 only:** OB-07 (clause 5.4), which v2 deleted.
- **REG-DPC:** 9 obligations (DP-01 to DP-09).

Sections 1.1, 1.2 and 2.1 of each regulation are administrative or applicability statements. They are **not** obligations. An extractor that returns them as obligations is producing false positives.

## 2. Applicability

| Obligation | Applicable? | Reason |
|---|---|---|
| OB-18 (KYC 2.2, overseas branches) | **Not applicable** | POL-01 §1.2: "The Bank has no branches or subsidiaries outside India." |
| All others | Applicable | Nova Trust is a Scheduled Commercial Bank in India and runs Video KYC (POL-03). |

## 3. Expected gaps (16)

Gap types: **Missing** (no control), **Design** (the control exists but is weaker than the rule), **Operating** (the design is fine but evidence shows failures), **Insufficient info** (we cannot tell), and **Conflict-blocked** (two rules cannot both be met).

| Gap | Obligation | Control | Type | Why | Suggested priority |
|---|---|---|---|---|---|
| G-01 | OB-04 (KYC 4.2) | CTL-02 | Design | Risk review is annual; the rule requires every 6 months | P2 |
| G-02 | OB-06 (KYC 5.3) | CTL-04 | Design, **change-triggered** | BO threshold is 25%; v2 changed it to 10% | P1 |
| G-03 | OB-08 (KYC 5A.1) | CTL-17 | Design, **change-triggered** | No liveness check, no geo-location, generic vendor training | P1 |
| G-04 | OB-09 (KYC 5A.2) | CTL-18 | Insufficient info, **change-triggered** | Recording storage location not stated | P2 |
| G-05 | OB-10 (KYC 6.1) | CTL-05 | Design + Operating | High-risk re-KYC every 3 years vs 2; EVD-02 shows 18.4% overdue **and 2,105 High risk accounts aged 2–3 years that are not on any due list** | P1 |
| G-06 | OB-12 (KYC 7.2) | CTL-06 | Operating | EVD-03: only 82.0% of alerts closed within 30 days | P2 |
| G-07 | OB-13 (KYC 8.1) | CTL-07 | Design, **change-triggered** | CTR filed by the 15th; v2 requires the 7th | P1 |
| G-08 | OB-14 (KYC 8.2) | CTL-08 | Operating | EVD-04: STR-2025-058 (11 days) and STR-2025-088 (9 days) were late | P2 |
| G-09 | OB-17 (KYC 11.1) | none | Missing | No training control; POL-01 §3 says no programme exists | P2 |
| G-10 | DP-01 (DPC 3.1) | none | Missing | No data-minimisation control | P2 |
| G-11 | DP-02 (DPC 3.2) | CTL-09, CTL-18 | **Conflict-blocked** | The bank keeps records for 8 years; DPC allows at most 3. Cannot be fixed by the bank alone; see CF-01 | P1, needs legal review |
| G-12 | DP-04 (DPC 5.1) | CTL-12 | Design + Operating | Annual vs quarterly; EVD-05 shows no review for 14 months and one unsigned system | P1 |
| G-13 | DP-05 (DPC 6.1) | CTL-13 | Design | Incident reporting in 24 hours vs 6 | P1 |
| G-14 | DP-06 (DPC 7.1) | CTL-14 | Design | MFA only for remote VPN, not for on-prem privileged access | P1 |
| G-15 | DP-08 (DPC 9.1) | CTL-16 | Design | Logs kept 90 days vs 180 | P1 |
| G-16 | DP-09 (DPC 10.1) | CTL-18 | Insufficient info | Vendor storage location and annual audit not stated | P2 |

Priority bands are a guide. They match the formula in TEAM_PLAN_ONE_NIGHT.md §6 exactly. Accept small differences if the criticality rubric is applied differently, as long as the formula is documented.

**Compliant (no gap) with evidence:** OB-01, OB-02, DP-07 (EVD-01).
**Covered by design but no evidence provided:** OB-03, OB-05, OB-11, OB-15, OB-16, DP-03. The system should say **"Insufficient evidence"** for these, not "Compliant".

## 4. Regulatory changes, v1 to v2 (feature 2)

| Change | Clause | Type | Detail |
|---|---|---|---|
| CH-01 | 5.2 | Modified | V-CIP added as a third verification method |
| CH-02 | 5.3 | Modified | Beneficial ownership threshold 25% → **10%** |
| CH-03 | 5.4 | **Deleted** | Physical self-attested copy after e-KYC no longer required |
| CH-04 | 5A (5A.1, 5A.2) | **Added** | New V-CIP section: liveness, geo-location, trained official, India storage |
| CH-05 | 8.1 | Modified | CTR deadline 15th → **7th** of the following month |
| CH-06 | Header, 1.2 | Modified (administrative) | Amendment reference and 1 October 2025 effective date; low significance |

Unchanged clauses (3.x, 4.x, 6.1, 7.x, 8.2, 9.1, 10.1, 11.1) must **not** be reported as changed.

## 5. Impact analysis of the v2 amendment (feature 11)

| Change | Affected controls | Impact |
|---|---|---|
| CH-02 | CTL-04 | New gap G-02 |
| CH-03 | CTL-03 | **Positive impact:** the physical-copy step can be retired. No longer a regulatory requirement (simplification opportunity) |
| CH-04 | CTL-17, CTL-18 | New gaps G-03, G-04; also links to DPC 10.1 (G-16) |
| CH-05 | CTL-07 | New gap G-07 |
| CH-01, CH-06 | none | Informational |

## 6. Cross-regulation links (feature 13)

| Link | Clauses | Relationship |
|---|---|---|
| X-01 | KYC 5A.2 ↔ DPC 10.1(a) | **Overlap.** Both require V-CIP recordings to be stored in India. One fix to CTL-18 closes G-04 and part of G-16 |
| X-02 | KYC 9.1 ↔ DPC 3.2 | **Conflict** (see CF-01) |
| X-03 | KYC 5A.2 ↔ DPC 3.2 | **Conflict.** KYC 5A.2 says to preserve recordings per §9 (5+ years); DPC says at most 3 |
| X-04 | KYC 3.1 ↔ DPC 8.1 | **Related, not equivalent.** Same governance pattern (Board approval plus annual review), different policies |

## 7. Contradictions (feature 14)

| ID | Clauses | Status | Explanation |
|---|---|---|---|
| CF-01 | KYC 9.1 (and 5A.2) vs DPC 3.2 | **Potential conflict, needs legal review** | KYC requires identity records to be kept **at least 5 years** after closure. DPC requires the same identity data to be kept **no more than 3 years**. DPC 3.2 has no "unless required by law" exception, so both cannot be satisfied. |

**Decoy (should NOT be flagged as a conflict):** DPC 9.1 (security logs at least 180 days) vs KYC 9.1 (transaction records at least 5 years). These are different kinds of records, and both minimums can be met together. If the system flags this, it is a false positive.

## 8. Suggested accuracy metrics for the dashboard

| Metric | How to compute |
|---|---|
| Obligation extraction recall | extracted obligations matching the 27 expected / 27 |
| Obligation extraction precision | matched / total extracted |
| Mapping accuracy | correct (obligation, control) pairs / expected pairs |
| Gap detection recall | gaps found / 16 |
| Gap type accuracy | gaps with the correct type / gaps found |
| Change detection | correct changes / 6, plus false positives on unchanged clauses |
| Conflict detection | CF-01 found (yes/no), decoy not flagged (yes/no) |
| Citation validity | share of outputs whose quoted source text is an exact substring of the document (checked automatically) |
