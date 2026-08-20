# Possible Grant / Funding Targets

Compiled 2026-08-20. Updated 2026-08-20 (session 2): completed the "not yet
researched" pass and verified AAG/Simons deadlines. Verified items link the actual
solicitation page; unverified items are flagged and need a direct check before
relying on them.

## Primary target

### NSF CSSI — Cyberinfrastructure for Sustained Scientific Innovation (NSF 22-632)
- **Track:** Elements (smaller scope; ~$10M pool across many awards — right size for
  this project. Framework Implementations, ~$20M, is multi-institution consortium
  scale and not the right fit here.)
- **Deadline:** December 1, annually. Next: **December 1, 2026** (~3.5 months from
  today).
- **Fit:** Strong. SNANA is community cyberinfrastructure (DES, LSST-DESC, Roman,
  Euclid all depend on it); CSSI explicitly funds tools/software infrastructure for
  science.
- **Framing:** Align with the NSF Genesis Mission Dear Colleague Letter — title the
  proposal "Genesis Mission: ..." and frame around AI-enabled scientific workflows.
  This is not a separate solicitation; it's DCL-level guidance to submit through
  existing programs (CSSI included) with this framing.
- **Eligibility — UNVERIFIED, check before investing real time:** NSF's own
  solicitation states no PI restrictions. Whatever governs whether a CAPS Fellow
  appointment at NCSA/UIUC counts as PI-eligible is an *institutional* rule, not an
  NSF one — needs a direct check with UIUC/NCSA's Office of Sponsored Programs.
- **What strengthens the proposal:** Phase 1 (working v1, see `ROADMAP.md`) as
  preliminary results/proof-of-concept. A letter of collaboration from Rick Kessler
  or LSST DESC would help establish community-scale relevance (reviewers want
  infrastructure for the field, not a personal tool).
- Sources: [CSSI program page](https://www.nsf.gov/funding/opportunities/cssi-cyberinfrastructure-sustained-scientific-innovation), [NSF 22-632 solicitation](https://www.nsf.gov/funding/opportunities/cssi-cyberinfrastructure-sustained-scientific-innovation/nsf22-632/solicitation), [Genesis Mission DCL](https://www.nsf.gov/funding/information/dcl-unleashing-new-age-ai-enabled-scientific-discovery-through)

## Secondary / worth checking

### NSF AAG — Astronomy and Astrophysics Research Grants (NSF 22-624)
- Explicitly considers "proposals for projects and tools that enable or enhance
  astronomical research" — plausible alternate/complementary vehicle.
- **Deadline — VERIFIED:** annual submission window **October 1 - mid-November**
  (most recent window closed Nov 17, 2025). Next window: opens **October 1, 2026**.
- **STILL NOT VERIFIED:** PI eligibility for a CAPS Fellow, and whether an
  AI-tooling proposal (vs. a straight science-analysis proposal) fits reviewer
  expectations for this program — AAG panels skew toward science results, CSSI
  panels skew toward infrastructure, so this is likely a secondary/complementary
  vehicle rather than the primary one.
- Source: [AAG solicitation](https://www.nsf.gov/funding/opportunities/aag-astronomy-astrophysics-research-grants/nsf22-624/solicitation)

### DOE ASCR — Genesis Mission RFA (DE-FOA-0003612)
- DOE co-leads the Genesis Mission (you're already a NERSC/Perlmutter user, which is
  a DOE facility — natural institutional fit).
- FY26 round: Phase I awards $500K-750K/9 months, Phase II $6-15M/3 years across 21
  topic areas including "discovery science." **This round's deadlines already
  passed** (Phase I due 2026-04-28, Phase II 2026-05-19) — 278 projects were funded
  and announced 2026-07-22.
- **Action:** watch for an FY27 round rather than treat as currently open.
- Source: [DOE Genesis Mission RFA](https://science.osti.gov/-/media/grants/pdf/foas-resources/2026/Genesis-Mission-RFA-Informational-Webinar-v2-public--clean--ASCR.pdf)

### Simons Foundation — Scientific Software Research Faculty Award
- Directly funds scientific software development/maintenance work — good conceptual
  fit for this project's substance.
- **Eligibility blocker, confirmed:** requires a faculty appointment (award funds
  new faculty hires starting no later than Sept 1, 2027). Only actionable if/when a
  faculty position (e.g., Westlake, or elsewhere) comes through.
- **Deadline — VERIFIED, and already closed for this cycle:** LOI was due
  **January 21, 2026, noon EST** (for Sept 2027 faculty starts). Watch for the next
  annual cycle, likely opening around January 2027.
- Source: [Simons SSRF Award](https://www.simonsfoundation.org/grant/scientific-software-research-faculty-award/)

## Newly researched (previously "not yet researched")

### Alfred P. Sloan Foundation — "Open Source in Science" (Digital Technology program)
- **Strong fit, and the lowest-friction entry point on this whole list.** Funds
  "tools, norms, and institutions that support the distributed development,
  adoption, and maintenance of discovery-enabling software" — exactly this
  project's category. Current focus areas explicitly include institutional support
  for open source and researcher roles/career paths around it.
- **Deadline — VERIFIED: rolling, through December 31, 2026.**
- **Entry format: a 2-page letter of inquiry** to technology@sloan.org — much
  lighter weight than a full NSF proposal, and a good way to test interest before
  committing to a full CSSI proposal write-up.
- PI eligibility not explicitly restricted to faculty in what's public — foundation
  LOI processes are typically more flexible than NSF on career stage, though the
  award would still need to flow through an institutional fiscal sponsor (UIUC/NCSA).
- Related, but likely not the right fit: Sloan also funds **university OSPO
  (Open Source Program Office) launches** (up to $750K/2yr) — that's institutional-
  scale (standing up an office), not a single-project grant, so probably not this
  project's vehicle unless UIUC/NCSA wants to pursue it separately.
- Could not independently verify the "Better Software for Science" program page
  (site blocked automated access) — worth a manual look at sloan.org directly.
- Source: [Sloan Open Source in Science](https://sloan.org/programs/digital-technology/open-source-in-science)

### Schmidt Sciences — AI in Science and Society / AI2050
- Funds development of AI tools that accelerate progress in engineering, physical
  sciences, and complex system design — good conceptual fit.
- **Funding: $100,000-$500,000.** Beyond direct funding, offers software
  engineering support via their Virtual Institute for Scientific Software, API
  credits with frontier model providers, and compute access — notably useful for
  this specific project (an LLM tool that needs API access).
- **Eligibility — promising:** stated as open to "individual researchers, research
  teams, research institutions, and multi-institution collaborations," globally,
  with no faculty/tenure-track restriction mentioned — unlike Simons SSRF, this one
  doesn't appear to be blocked by current CAPS Fellow status.
- **Deadline: NOT CONFIRMED** — could not verify against schmidtsciences.org
  directly (fetch blocked); details above are from secondary aggregator sources.
  Check schmidtsciences.org directly before relying on this.

### Gordon and Betty Moore Foundation
- **Low priority / likely not actionable right now.** Grants are mostly by
  invitation; found no open call matching scientific software/cyberinfrastructure.
  Current open RFP (Symbiosis in Aquatic Systems, due 2026-07-31, already passed)
  is unrelated. Revisit only if a Moore program officer contact emerges.

## Notes
- This list is shareable with collaborators (e.g., for a CSSI letter of collaboration
  ask) — it contains no personal career-strategy content.
