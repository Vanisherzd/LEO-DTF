# Bibliography TODO

This document tracks placeholder citation replacements in `paper/refs.bib`.
**Do not fabricate citation details.** Entries marked [VERIFY] need additional
verification before final submission.

---

## Status: Phase 33 Complete — Citation Replacement Pass

The following `todo_*` placeholders have been replaced with real citation keys.
Not all replacements are fully verified; see individual entries below.

---

## Replaced `todo_*` Entries

| Old Key | New Key(s) | Status |
|---------|-----------|--------|
| `todo_ntn_iot` | `kodheli_nb_iot_2021` | Partially verified [VERIFY] |
| `todo_sgp4` | `vallado_spacetrack_2006` | Verified (arXiv/cited paper) |
| `todo_doppler_localization` | `liu_geometric_2026` | Verified (arXiv:2603.19499) |
| `todo_doppler_positioning` | `liu_geometric_2026`, `dureppagari_leo_2024` | Verified |
| `todo_oscillator_nuisance` | `ettefagh_integrated_2025` | Verified (arXiv:2509.18727) |
| `todo_ntn_positioning` | `dureppagari_leo_2024` | Verified (arXiv:2410.18301) |
| `todo_lr1121` | `semtech_lr1121_datasheet` | [VERIFY] URL/year not confirmed |
| `todo_lora_phy` | `semtech_lr_fhss_phy` | [VERIFY] URL/year not confirmed |
| `todo_usrp_b210` | `ettus_usrp_b210` | [VERIFY] URL/year not confirmed |

---

## Entries Still Needing Verification

### `kodheli_nb_iot_2021` — [VERIFY]
- **Used in:** Section 1 (Introduction), Section 2 (Background)
- **Issue:** Full author list not confirmed from search; arXiv search returned
  O. Kodheli, N. Maturo, S. Chatzinotas only
- **Needed:** Confirm full author list, journal volume/pages from IEEE Access
- **Action:** Access IEEE Xplore or CrossRef to verify author list

### `semtech_lr1121_datasheet` — [VERIFY]
- **Used in:** Section 6 (HIL Plan)
- **Issue:** URL and year need verification via semtech.com
- **Needed:** Confirm current year and exact URL

### `semtech_lr_fhss_phy` — [VERIFY]
- **Used in:** Section 6 (HIL Plan)
- **Issue:** AN1200.22 URL and year need verification
- **Needed:** Confirm URL and publication year

### `ettus_usrp_b210` — [VERIFY]
- **Used in:** Section 6 (HIL Plan)
- **Issue:** URL and year need verification via ettus.com or NI.com
- **Needed:** Confirm current product page URL

### `3gpp_tr_38821` — [VERIFY]
- **Used in:** Not currently cited in text (background reference)
- **Issue:** URL needs confirmation and accessed date

### `3gpp_tr_38811` — [VERIFY]
- **Used in:** Not currently cited in text (background reference)
- **Issue:** URL needs confirmation and accessed date

### `vallado_fundamentals_2001` — [VERIFY]
- **Used in:** Not currently cited in text (textbook reference)
- **Issue:** Publisher and edition details need confirmation

### `karthik_clock_2018` — [VERIFY]
- **Used in:** Not currently cited in text
- **Issue:** Journal volume/pages from IEEE Xplore (blocked at time of search)
  May not be the best fit for low-cost LEO oscillator modeling

### `song_certifiably_2025` — [VERIFY]
- **Used in:** Not currently cited in text
- **Issue:** Journal/venue not confirmed (only arXiv:2503.11200 seen)

---

## Verified Entries (No [VERIFY] tag)

| Key | Why Verified |
|-----|-------------|
| `liu_geometric_2026` | arXiv:2603.19499 — Title, authors, year confirmed via arXiv API |
| `dureppagari_leo_2024` | arXiv:2410.18301 — Accepted for IEEE Communications Magazine; authors confirmed |
| `ettefagh_integrated_2025` | arXiv:2509.18727 — Authors confirmed via arXiv API; focuses on LEO positioning with clock/frequency offsets |
| `vallado_spacetrack_2006` | AIAA 2006-6753 — Canonical SGP4 reference; widely cited |
| `semtech_lr1121_datasheet` | **Needs URL/year verification** |
| `semtech_lr_fhss_phy` | **Needs URL/year verification** |
| `ettus_usrp_b210` | **Needs URL/year verification** |

---

## Remaining Work

1. **[High]** Confirm `kodheli_nb_iot_2021` full author list via CrossRef or IEEE Xplore
2. **[High]** Verify `semtech_lr1121_datasheet`, `semtech_lr_fhss_phy`, `ettus_usrp_b210` URL/year
3. **[Medium]** Add `3gpp_tr_38811` or `3gpp_tr_38821` citation to NTN background section if appropriate
4. **[Medium]** Decide whether to cite `vallado_fundamentals_2001` textbook in system model
5. **[Low]** Remove or relocate orphaned entries (`karthik_clock_2018`, `song_certifiably_2025`)
   if they are not needed for the manuscript

---

## Key Rules

- **Never fabricate author names, titles, or years.**
- **Entries marked [VERIFY] must be confirmed before final submission.**
- **Do not replace these notes until every [VERIFY] item is resolved.**