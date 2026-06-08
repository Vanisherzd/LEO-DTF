# Bibliography TODO

This document tracks placeholder citation replacement status and remaining
verification items in `paper/refs.bib`. **Do not fabricate citation details.**

---

## Status: Citation Replacement Complete — Verification Pass Done

All `todo_*` placeholder keys have been replaced with real citation keys.
The following report documents what has been verified and what still
needs attention.

---

## Verification Summary

| Key | Status | Verification Source |
|-----|--------|---------------------|
| `liu_geometric_2026` | **Verified** | arXiv API (2603.19499) |
| `dureppagari_leo_2024` | **Verified** | arXiv API (2410.18301) + IEEE ComMag acceptance |
| `kodheli_nb_iot_2021` | **Verified** | arXiv API (full author list confirmed) |
| `ettefagh_integrated_2025` | **Verified** | arXiv API (2509.18727) |
| `vallado_spacetrack_2006` | **Verified** | AIAA 2006-6753 (canonical SGP4 reference) |
| `semtech_lr1121_datasheet` | **[UNVERIFIED]** | Vendor site inaccessible (404/403) |
| `semtech_lr_fhss_phy` | **[UNVERIFIED]** | Vendor site inaccessible (404/403) |
| `ettus_usrp_b210` | **[UNVERIFIED]** | Vendor site inaccessible (403) |

---

## Entries Removed (Orphaned — Not Cited in Manuscript)

The following entries were in `refs.bib` but are not cited in any section.
They have been removed to avoid confusion:

- `3gpp_tr_38811` — 3GPP TR 38.811 (Release 15 NR-NTN); not cited in text
- `3gpp_tr_38821` — 3GPP TR 38.821 (Release 17 NTN); not cited in text
- `vallado_fundamentals_2001` — Vallado textbook; `vallado_spacetrack_2006` is the active SGP4 reference
- `karthik_clock_2018` — IEEE Trans. Commun. clock estimation; not cited in text
- `song_certifiably_2025` — arXiv:2503.11200; not cited in text

If needed as background references for a specific venue, they can be restored
from git history and verified.

---

## Hardware Entries: [UNVERIFIED] — Why and What to Do

Three entries in `refs.bib` are cited in Section 6 (HIL Plan) but carry
`[UNVERIFIED]` status because vendor web sites returned errors at
verification time:

| Key | Vendor Site | Error | Action Needed |
|-----|-------------|-------|---------------|
| `semtech_lr1121_datasheet` | semtech.com (LR1121 product page) | 404/403 | Visit semtech.com, find LR1121 page, copy URL and check year |
| `semtech_lr_fhss_phy` | semtech.com (LoRa/LR-FHSS docs) | 404/403 | Visit semtech.com LoRa page, find AN1200.22, verify URL/year |
| `ettus_usrp_b210` | ettusresearch.com | 403 | Visit NI/Ettus USRP B210 page, verify current URL and product year |

These are product datasheets, not academic papers. They can remain in the
bibliography as reference material for the HIL hardware description without
replacing them with peer-reviewed papers, provided the notes accurately
describe their status.

---

## Remaining Actions Before Final Submission

1. **[High]** Visit semtech.com and confirm the LR1121 product page URL and
   publication date. Update the `year` and `url` fields in
   `semtech_lr1121_datasheet`.

2. **[High]** Visit semtech.com and confirm the AN1200.22 LR-FHSS spec URL and
   year. Update `semtech_lr_fhss_phy`.

3. **[High]** Visit ettusresearch.com (or ni.com) and confirm the USRP B210
   product page URL and current year. Update `ettus_usrp_b210`.

4. **[Low]** If the above cannot be resolved, consider whether to cite academic
   papers that reference these products instead of the datasheets directly.
   For example, the LR-FHSS papers (de Souza Sant Ana 2024, Maleki 2022) on
   arXiv provide academic references for LR-FHSS PHY.

---

## Key Rules

- **Never fabricate author names, titles, or years.**
- **Entries marked [UNVERIFIED] must be confirmed before final submission.**
- **Do not remove [UNVERIFIED] markers until the vendor site is accessible.**
- **Orphaned entries (not cited in text) have been removed but remain in git history.**