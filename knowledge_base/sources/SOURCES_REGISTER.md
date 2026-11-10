# Knowledge-Base Sources Register (Phase 3 Pilot)

**Status:** Phase 3 pilot dataset. This register documents every source currently backing a record in [`seed_data/approved_uses.json`](../seed_data/approved_uses.json). It is generated/maintained by hand alongside the JSON files — the JSON files are the authoritative machine-readable record; this file is a human-readable index of the same sources.

**Project rule (do not weaken):** no pesticide approval, dosage, application rate, waiting period (PHI), re-entry interval (REI), or PPE requirement is ever entered into `approved_uses.json` without an entry here, a traceable `url`, and a `retrieved_date`. If a safety field (PHI/REI/PPE) is not published by the source, it is recorded as `NOT_PUBLISHED_IN_SOURCE` with an explanatory note — never left blank, never inferred.

---

## 1. Tamil Nadu Agricultural University (TNAU) — Agritech Portal

| Field | Value |
|---|---|
| Authority | Tamil Nadu Agricultural University, a State Agricultural University (SAU) |
| Reliability tier | `state_agricultural_university` |
| Geography | India (content presented as general crop-protection guidance) |
| Why used | ppqs.gov.in (Directorate of Plant Protection, Quarantine & Storage) returned HTTP 403 Forbidden when fetched directly; TNAU Agritech is a recognized, publicly fetchable Indian government agricultural university source consistent with the blueprint's "ICAR/KVK advisories" authoritative-source category (Section 4.4 of the Architecture Blueprint). |
| Limitation | TNAU is Tamil-Nadu-focused and does not publish a wheat pest-management page (wheat is not a major Tamil Nadu crop) — wheat is sourced from NIPHM/DPPQS instead (see below). None of the fetched TNAU pages publish PHI, REI, or PPE values for the listed insecticides. |

Pages used (fetched 2026-11-02):

| Source ID | Crop | Topic | URL |
|---|---|---|---|
| SRC-TNAU-COTTON-BOLLWORM-01 | Cotton | American bollworm / Fruit borer (*Helicoverpa armigera*) | https://agritech.tnau.ac.in/crop_protection/cotton/crop_prot_crop_insectpest%20_cotton_1.html |
| SRC-TNAU-COTTON-PINKBW-01 | Cotton | Pink bollworm (*Pectinophora gossypiella*) | https://agritech.tnau.ac.in/crop_protection/cotton/crop_prot_crop_insectpest%20_cotton_2.html |
| SRC-TNAU-COTTON-SPOTTEDBW-01 | Cotton | Spotted bollworm / Spiny bollworm (*Earias vittella* / *E. insulana*) | https://agritech.tnau.ac.in/crop_protection/cotton/crop_prot_crop_insectpest%20_cotton_3.html |
| SRC-TNAU-RICE-STEMBORER-01 | Rice | Yellow Stem Borer (*Scirpophaga incertulas*) | https://agritech.tnau.ac.in/crop_protection/rice/crop_prot_crop_insectpest%20_cereals_paddy_m1.html |
| SRC-TNAU-RICE-LEAFFOLDER-01 | Rice | Rice Leaf Folder | https://agritech.tnau.ac.in/crop_protection/rice/crop_prot_crop_insectpest%20_cereals_paddy_m5.html |
| SRC-TNAU-MAIZE-FAW-01 | Maize | Fall armyworm (*Spodoptera frugiperda*) — page explicitly dated "Updated on May 2023" | https://agritech.tnau.ac.in/crop_protection/maize/crop_prot_maize_fall_armyworm.html |
| SRC-TNAU-TOMATO-FRUITBORER-01 | Tomato | Fruit Borer (*Helicoverpa armigera*) — page explicitly dated "Updated on Jun, 2023" | https://agritech.tnau.ac.in/crop_protection/tomato/tomato_1.html |

---

## 2. National Institute of Plant Health Management (NIPHM) & Directorate of Plant Protection, Quarantine and Storage (DPPQS)

| Field | Value |
|---|---|
| Authority | NIPHM + DPPQS, Department of Agriculture & Cooperation, Ministry of Agriculture, Government of India |
| Reliability tier | `national_regulator_ipm_package` |
| Geography | India (national) |
| Why used | DPPQS is the Directorate that houses the **Central Insecticides Board & Registration Committee (CIB&RC)** — India's statutory pesticide-registration authority named in the approved Phase-2 geographic scope decision. TNAU does not cover wheat; this joint NIPHM/DPPQS "AESA Based IPM Package" for wheat is the authoritative national alternative, identified via web search of `pau.edu.in`/ICAR/NIPHM wheat IPM resources. |
| Important distinction | This document is **IPM extension/advisory guidance**, not a live CIB&RC product-registration label lookup. It has not been cross-checked against the current CIB&RC product registry. Every wheat record's `verification_note` states this explicitly. |

Page used (fetched 2026-11-02, read via page-by-page PDF rendering):

| Source ID | Crop | Topic | URL |
|---|---|---|---|
| SRC-NIPHM-DPPQS-WHEAT-01 | Wheat | Aphids (*Sitobion avenae* / *S. miscanthi*), Termite (*Odontotermis obesus* / *Microtermes obesi*) | https://niphm.gov.in/IPMPackages/Wheat.pdf |

Document date: the only explicit date found in the fetched pages is the Foreword signature page, dated **6.3.2014** (Additional Secretary, Ministry of Agriculture). No separate per-chapter or whole-document revision date was found in the sections actually fetched (pages 1-10 and 26-35 of 83 total pages).

---

## Explicitly NOT used (and why)

| Source attempted | Result |
|---|---|
| `ppqs.gov.in/divisions/cib-rc/major-uses-of-pesticides.pp12` | HTTP 403 Forbidden — could not fetch. |
| `nfsm.gov.in/ReadyReckoner/NFSM_Package.pdf` | Fetch failed — oversized/binary content not cleanly extractable. |
| `icariivr.org.in` compendium PDF | Fetch failed — oversized/binary content not cleanly extractable. |
| `agritech.tnau.ac.in/.../Pesticide%20list_crop%20wise.pdf` | Fetch failed — raw binary noise, not usable. |

These are recorded here so a future contributor does not re-attempt the same dead ends without reason, and so no one assumes the pilot dataset is more exhaustive than it is.

---

## Coverage summary (Phase 3 pilot)

| Pilot crop | Records | Source(s) |
|---|---|---|
| Rice | 2 (Yellow Stem Borer, Leaf Folder) | TNAU |
| Wheat | 2 (Aphids, Termite) | NIPHM/DPPQS |
| Maize | 1 (Fall armyworm) | TNAU |
| Cotton | 3 (American bollworm, Pink bollworm, Spotted/Spiny bollworm) | TNAU |
| Tomato | 1 (Fruit Borer) | TNAU |
| **Total** | **9 approved_use records, 8 sources** | — |

This is below the blueprint's 10–20 target range (Section 4.4). Per the explicit team decision (DEC-005 in the Decision Log), **this is acceptable and expected** — "a smaller set of fully verified records is preferred over a larger set with gaps." No record in this set was fabricated or padded to reach a target number. Expanding coverage (more pests per crop, more crops' worth of PHI/REI/PPE where publishers provide them) remains an open, explicitly tracked task for a later Phase 3 iteration — see `docs/MILESTONE_1_REPORT.md`-style reporting in the Phase 3 completion report.
