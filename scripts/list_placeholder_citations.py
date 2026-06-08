#!/usr/bin/env python3
"""
List Placeholder Citations
==========================
Parse paper/refs.bib for todo_* keys and report where each is used in paper/sections/*.tex.
No web access, no replacement — scaffold only.

Output:
  - Console table: key | used_in | note
  - docs/placeholder_citation_report.md
"""

import re
from pathlib import Path

BIB = Path("paper/refs.bib")
SECTIONS = Path("paper/sections")
REPORT = Path("docs/placeholder_citation_report.md")

bib_content = BIB.read_text()
todo_keys = set(re.findall(r'@\w+\{(todo_\w+),', bib_content))

usage = {k: [] for k in sorted(todo_keys)}
for tex_file in SECTIONS.glob("*.tex"):
    content = tex_file.read_text()
    # find \cite{key} and \citep{key} and \citet{key}
    cited = re.findall(r'\\cite[pt]?\{([^}]+)\}', content)
    for key in cited:
        for todo_key in todo_keys:
            if todo_key in key.split(","):
                usage[todo_key].append(tex_file.name)

# Determine suggested action based on usage
SUGGESTED_ACTIONS = {
    "todo_ntn_iot": "Find authoritative 3GPP NTN / 3GPP Release 17+ NTN IoT overview paper",
    "todo_ntn_positioning": "Find 3GPP NTN positioning or 5G positioning literature",
    "todo_doppler_localization": "Find GNSS/Doppler-based terrestrial or satellite localization",
    "todo_doppler_positioning": "See todo_doppler_localization (may be same)",
    "todo_lora_phy": "Find LoRa/LoRaWAN PHY layer analysis paper",
    "todo_lr1121": "Find Semtech LR1121 datasheet or application note",
    "todo_usrp_b210": "Find Ettus/USRP B210 specifications or SDR localization work",
    "todo_sgp4": "Find Vallado et al. SGP4/SDP4 canonical reference (AIAA 2006)",
    "todo_oscillator_nuisance": "Find oscillator drift / clock bias estimation in range-rate literature",
}

lines = [
    "# Placeholder Citation Report",
    "",
    f"Generated: {__import__('datetime').date.today().isoformat()}",
    "",
    "## Summary",
    "",
    f"Found **{len(todo_keys)}** placeholder citations in `paper/refs.bib`.",
    "",
    "## Citation Table",
    "",
    "| Key | Used In | Suggested Replacement Action |",
    "|-----|---------|-------------------------------|",
]

for key in sorted(todo_keys):
    files = usage[key]
    used_in = ", ".join(files) if files else "(unused — consider removing)"
    action = SUGGESTED_ACTIONS.get(key, "Find appropriate peer-reviewed reference")
    lines.append(f"| `{key}` | {used_in} | {action} |")

lines += [
    "",
    "## Unused Placeholders",
    "",
    "The following placeholders are defined in refs.bib but not cited in any",
    "section. Before submission, either replace with a real citation or remove",
    "the entry from refs.bib:",
    "",
]
unused = [k for k, v in usage.items() if not v]
if unused:
    for k in unused:
        lines.append(f"- `{k}`")
else:
    lines.append("None — all placeholders are used at least once.")

lines += [
    "",
    "## Action Items",
    "",
    "1. Replace each `todo_*` entry with a verified peer-reviewed citation.",
    "2. Do not use datasheet URLs as primary citations — use conference/journal",
    "   papers that cite or reference the relevant standard.",
    "3. For SGP4: Vallado et al. (2006) *Revisiting Spacetrack Report #3* is the",
    "   canonical reference for SGP4/SDP4.",
    "4. For NTN IoT context: 3GPP Release 17 NTN work is documented in 3GPP TS",
    "   38.821, TS 22.261, and related papers in IEEE Communications Magazine or",
    "   IEEE IoT Journal.",
    "5. For LoRa PHY: Semtech AN1200.22 or academic papers analyzing LR-FHSS PHY.",
    "6. For LR1121: Semtech LR1121 product page is the source; academic papers",
    "   evaluating LR-FHSS over satellite are the preferred citation.",
    "",
    "See also: `docs/bibliography_todo.md` for categorized checklist.",
]

report_content = "\n".join(lines) + "\n"
REPORT.write_text(report_content)

# Print to stdout
for line in lines:
    print(line)

print(f"\nReport written to {REPORT}")