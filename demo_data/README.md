# RuleSight demo data

**Regulator: RBI only.** Every regulation in this demo is real RBI text.
**Bank: Nova Trust Bank Ltd. is fictional.** Its policies, control matrix and evidence cite real RBI paragraphs, and they are the test subject.

```
demo_data/
  1_regulations_rbi/                 REAL regulation text (the rules the system reads)
    RBI_KYC_MD_2016_updated_2025-08-14.txt
    NSM_v1_RBI_circular_2024-10-30_WITHDRAWN.pdf
    NSM_v2_RBI_Master_Direction_2026-10-02.pdf
    README.md                        which paragraphs to use and which to skip

  2_bank_nova_trust/                 FICTIONAL bank documents (what the system checks)
    policies/   POL-01 KYC/AML policy, POL-03 Video KYC SOP, POL-04 Currency/NSM SOP
    rcm/        RCM_Nova_Trust_Risk_Control_Matrix.csv (10 controls, each with its RBI paragraph)
    evidence/   EVD-02 re-KYC overdue report, EVD-06 machine inventory, EVD-07 test log

  3_answer_key/                      NEVER feed to the agents. Used only for scoring.
    ANSWER_KEY.md                    KYC + NSM summary, dashboard metrics
    expected_mappings_RBI.csv        19 obligations, mappings, 12 gaps
    ANSWER_KEY_NSM_REAL.md           NSM details and the v1 to v2 change key

  _archive_not_used/                 old synthetic CBA/DPC files. NOT used. Safe to delete.
```

## What the system must find
- **KYC (8 gaps):** top gap G-07. Re-KYC for High risk is every 2 years under RBI para 38; Nova Trust uses 3. P1, backed by EVD-02 (18.4% overdue).
- **NSM v2 (4 gaps):** NG-01 quarterly testing (P1) and NG-03 phase-out of 7 discontinued machines by 30 June 2027 (P1).
- **Change:** NSM v1 is withdrawn by v2. The system must note that the 24 April 2025 circular in the v2 Annex is not in the corpus.

## Demo rules
1. Say "RBI" for every regulation. Say "fictional bank" for Nova Trust.
2. Do not claim any regulation that is not in `1_regulations_rbi/`.
3. `is_synthetic = true` marks the bank documents only. Regulations are always `false`.
