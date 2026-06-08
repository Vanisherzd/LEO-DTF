# Bibliography TODO

This file lists all placeholder citation keys in `paper/refs.bib` and what real references they should be replaced with. **Do not fabricate citation details.** Verify each replacement before inserting.

---

## `todo_ntn_iot`

**Used in:** Section 1 (Introduction), Section 2 (Background)
**Needed:** Survey or 3GPP specification on direct-to-satellite IoT and NTN architectures
**Suggested search:** `3GPP NTN IoT Rel-18 non-terrestrial network direct-to-device survey`
**Suggested source:** 3GPP TR 38.821, or IEEE ComMag article on NTN for IoT

---

## `todo_sgp4`

**Used in:** Section 3 (System Model)
**Needed:** Reference to SGP4 orbit propagator (Vallado, etc.)
**Suggested search:** `Vallado sgp4 orbit determination 2005 fundamentals of astrodynamics`
**Note:** The original SGP4 reference is Vallado and Crawford (2008), but Vallado (2005) "Fundamentals of Astrodynamics and Applications" is the standard textbook reference. Use the verified published DOI.

---

## `todo_doppler_localization`

**Used in:** Section 2 (Background)
**Needed:** Prior work on LEO Doppler-based geolocation
**Suggested search:** `doppler-based localization LEO satellite positioning`
**Note:** The placeholder author "Kannan, B. B. and Shea, J. M." was not verified. Find the real authors of relevant papers in this space.

---

## `todo_doppler_positioning`

**Used in:** Section 2 (Doppler-Aided Localization)
**Needed:** Survey or review of LEO Doppler positioning approaches
**Suggested search:** `doppler positioning LEO satellite survey`
**Note:** Same unverified author pair as above. Replace with a real survey paper.

---

## `todo_oscillator_nuisance`

**Used in:** Section 2, Section 3
**Needed:** Paper on CFO/drift modeling for low-cost IoT oscillators in LEO SATCOM
**Suggested search:** `carrier frequency offset oscillator drift LEO satellite IoT synchronization`
**Note:** The placeholder "Cao, C. and McNeil, M. and G. P. Ascheid" (with typo in Ascheid) was fabricated. Find real authors.

---

## `todo_ntn_positioning`

**Used in:** Section 2 (Doppler-Aided Localization)
**Needed:** NTN positioning from 5G New Radio perspective
**Suggested search:** `3GPP NTN positioning 5G NR LEO satellite`
**Suggested source:** 3GPP TR 38.811 (NTN study), or Lin et al. (IEEE Access, 2022) on NTN positioning

---

## `todo_lr1121`

**Used in:** Section 6 (HIL Plan), docs/hardware/
**Needed:** Semtech LR1121 datasheet or product brief
**Suggested search:** `Semtech LR1121 transceiver datasheet`
**Suggested source:** semtech.com LNDR (official datasheet), last verified 2024
**Note:** Verify the URL and publication date before using.

---

## `todo_lora_phy`

**Used in:** Section 6 (HIL Plan), docs/hardware/
**Needed:** LoRa and LR-FHSS physical layer specification
**Suggested search:** `LoRaWAN physical layer LR-FHSS Semtech specification`
**Note:** The placeholder used "Sornin, N. et al." which is the LoRaWAN authors. Verify if the specific paper is the right reference (it may be the LoRaWAN 1.0 spec from 2015).

---

## `todo_usrp_b210`

**Used in:** Section 6 (HIL Plan), docs/hardware/
**Needed:** USRP B210 product reference
**Suggested search:** `Ettus USRP B210 product overview`
**Suggested source:** ettus.com or NI.com product page
**Note:** Verify year of current product page.

---

## How to Replace

1. Search for the real reference using the queries above.
2. Obtain the verified: author names, title, year, journal/URL, DOI.
3. In `paper/refs.bib`, replace the `todo_*` entry with the verified `@misc` or `@article` entry.
4. In the manuscript, keep `\cite{todo_xxx}` keys as-is (they map to the same key in `refs.bib`).
5. Remove the `note` field before final submission.

## Important

- **Never fabricate author names, titles, or years.**
- **Use only references you can verify through a DOI, official URL, or published DOI.**
- **"Kannan, B. B. and Shea, J. M." and "Cao, C. and McNeil, M. and G. P. Ascheid" were not verified — treat these as unknown and do not reuse them.**