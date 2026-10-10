# Answer key (RBI-only corpus)

Real RBI documents plus Nova Trust Bank's fictional policies. Every regulatory clause below is quoted from the real RBI text.

**Do not feed this folder to the agents.** It is only for scoring.

Machine-readable KYC + NSM mappings and gaps: [expected_mappings_RBI.csv](expected_mappings_RBI.csv).
NSM details and the change-intelligence key: [ANSWER_KEY_NSM_REAL.md](ANSWER_KEY_NSM_REAL.md).

## Corpus
| Document | Type | Real? |
|---|---|---|
| RBI KYC Master Direction 2016 (updated 14 Aug 2025), selected paragraphs | Regulation | Real |
| RBI NSM circular, 30 Oct 2024 (withdrawn 2 Oct 2026) | Regulation (v1) | Real |
| RBI NSM Master Direction, 2 Oct 2026 | Regulation (v2) | Real |
| POL-01, POL-03, POL-04, RCM CSV, EVD-02, EVD-06, EVD-07 | Bank documents | Fictional bank |

## Obligations (19)
- **KYC, 11:** paras 3, 6(d), 18(a)(iv), 18(a)(v), 18(c)(i), 37(a), 38, 46(a), 46(b), 68 (not applicable), 70.
- **NSM v2, 8:** paras 2.2/4, 2.3, 5, 6.1/6.2, 7, Testing Procedure, 8.2 (phase-out), 8.2 (BIS procurement). Plus the applicability scope in para 3.

## Gaps (12)
| Gap | Obligation | Type | Why | Priority |
|---|---|---|---|---|
| G-01 | KYC para 3 (beneficial owner >10%) | Design | Policy uses 25% | P2 |
| G-02 | KYC para 6(d) (PO and DD separate) | Insufficient info | Policy does not say they are different people | P3 |
| G-03 | KYC para 18(a)(iv) (GPS geo-tag) | Design | Not described in the SOP | P2 |
| G-04 | KYC para 18(a)(v) (liveness) | Design | SOP does face match only | P2 |
| G-05 | KYC para 18(c)(i) (India storage) | Insufficient info | Storage location not stated | P3 |
| G-06 | KYC para 37(a) (review every 6 months) | Design | Policy reviews once a year | P2 |
| G-07 | KYC para 38 (High risk every 2 years) | Design + operating | Policy uses 3 years; EVD-02 shows 18.4% overdue and 2,105 accounts not on due list | **P1** |
| G-08 | KYC para 70 (employee training) | Missing | No training programme in POL-01 | P2 |
| NG-01 | NSM para 7 (quarterly testing) | Design + operating | Half-yearly; no test in Jul to Sep 2026 (EVD-07) | **P1** |
| NG-02 | NSM Testing Procedure (2,000-note deck) | Design | Deck is 1,000 notes | P2 |
| NG-03 | NSM para 8.2 (phase out by 30 Jun 2027) | Missing | No phase-out plan; 7 discontinued machines in EVD-06 | **P1** |
| NG-04 | NSM para 3 (agents) | Design | CIT agency machines excluded in POL-04 §1.2 | P2 |

Compliant with evidence: none claimed. Covered on paper but no evidence: KYC 46(a), 46(b); NSM 2.2/4, 2.3, 5, 6, 8.2 (BIS).

## Change intelligence (NSM v1 to v2 only)
See [ANSWER_KEY_NSM_REAL.md](ANSWER_KEY_NSM_REAL.md) §3. The KYC corpus has one version only, so there is no KYC change demo.

## Dropped features
- **Cross-regulation (#13) and contradiction (#14):** the real corpus has no clear overlap or conflict. Do not claim them.

## Accuracy metrics for the dashboard
| Metric | How to compute |
|---|---|
| Obligation recall / precision | extracted vs the 19 obligations above |
| Gap recall | gaps found / 12 |
| Gap type accuracy | gaps with the correct type / gaps found |
| Mapping accuracy | correct (obligation, control) pairs / expected pairs |
| Change detection | NSM v1 to v2 changes found vs ANSWER_KEY_NSM_REAL §3 |
| Citation validity | share of quotes that are exact substrings of the source text (checked by code) |
