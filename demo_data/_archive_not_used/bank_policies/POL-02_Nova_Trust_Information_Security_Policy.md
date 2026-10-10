> **SYNTHETIC DEMO DOCUMENT.** "Nova Trust Bank Ltd." is a fictional bank created for the RuleSight hackathon demo.

# Nova Trust Bank Ltd.
## Information Security Policy

**Document ID:** POL-02
**Version:** 5.0
**Owner:** Chief Information Security Officer (CISO)
**Approved by:** Board of Directors, 20 February 2025
**Next review due:** February 2026

---

### 1. Purpose and scope

1.1 This Policy sets the minimum information security controls for all systems that store or process customer data at Nova Trust Bank Ltd. ("the Bank").

### 2. Controls

**CTL-11 — Encryption of customer data**
All customer data is encrypted at rest using AES-256 in the core banking and document management systems. All network traffic that carries customer data uses TLS 1.2 or later.
*Owner:* IT Infrastructure. *Frequency:* Continuous.

**CTL-12 — Privileged access review**
The Information Security team reviews all privileged user accounts on production systems **once a year** and revokes access that is no longer needed. Each system owner signs an attestation.
*Owner:* Information Security. *Frequency:* Annual.

**CTL-13 — Cyber incident reporting**
The Security Operations Centre (SOC) classifies every incident. Incidents that affect customer data or critical services are reported to the CBA **within 24 hours** of detection.
*Owner:* CISO / SOC. *Frequency:* Event-driven.

**CTL-14 — Multi-factor authentication**
All **remote access** to the Bank's network through VPN requires multi-factor authentication. *(On-premises privileged access to production systems uses username and password.)*
*Owner:* IT Infrastructure. *Frequency:* Continuous.

**CTL-15 — Information Security Policy governance**
This Policy is approved by the Board of Directors and reviewed by the Board once a year.
*Owner:* CISO. *Frequency:* Annual.

**CTL-16 — Security log retention**
Security and audit logs from production systems are sent to the SIEM and retained for **ninety (90) days**.
*Owner:* SOC. *Frequency:* Continuous.

---
*End of Policy.*
