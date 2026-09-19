# PromiseWatch

**Satellite-verified tracking of politically promised infrastructure in Kenya — dams, roads, and stadiums that were announced but may never have been delivered.**

Built for the OSF × Andela Hackathon (Transparency & Accountability track), October 2026.

---

## The problem

Public institutions and political offices in Kenya regularly announce large infrastructure projects — dams, roads, stadiums, boreholes — with a stated location, scope, and completion target. Years later, many of these projects have stalled, been quietly cancelled, or never broken ground at all, while the original announcement remains the only public record most citizens ever see. Tracking which commitments were kept requires either trusting official reporting (which has an obvious incentive problem) or physically visiting the site.

**PromiseWatch checks a different kind of evidence: what's actually on the ground, from space.** Public satellite imagery (Sentinel-2, 10m resolution, revisited every ~5 days, free and open) can directly observe whether a claimed reservoir has filled, whether a road corridor shows new construction, or whether a stadium footprint exists — independent of what any press release says.

## How it works

Every case follows the same four-step framework:

1. **Claim** — a specific public infrastructure commitment: a public institution or political office announced a project with a stated location, scope, and/or completion target (e.g., "Kimwarer Dam will be completed by 2020," sourced from public reporting or project documents).
2. **Evidence** — satellite imagery pulled for that exact location, compared between a baseline period (before the claim) and the current period.
3. **Assurance** — a verdict: **Supported**, **Not Delivered / Conflicted**, or **Underdetermined**, based on a specific, stated evidentiary rule (not a subjective read of the imagery).
4. **Action** — what a citizen or journalist can actually do with the result (not implemented yet — see Roadmap).

### Methodology: dam detection (built and validated)

For a claimed dam/reservoir project:

- Pull a cloud-masked Sentinel-2 composite for a **baseline window** (90 days after the claimed construction start) and a **current window** (the most recent 90 days).
- Compute **MNDWI** (Modified Normalized Difference Water Index) on each composite and classify pixels as water above a threshold.
- Sum water-classified pixel area within a buffer around the claimed site to get **hectares of water extent**, for both periods.
- Compute the **delta**: `current_extent_ha − pre_extent_ha`. This is the key methodological choice — **raw current extent is not used directly**, because many sites have real, pre-existing water (a natural river, a wetland, or in several of our own cases, small unrelated community water pans) that has nothing to do with the claimed project. Only water added *since baseline* counts as evidence the project exists.
- Apply a **guardrail**: if the delta is below a small threshold (set per-case, well above typical small-pan sizes but well below the claimed project's design scale), the verdict is **Not Delivered / Conflicted** — there may be water at the site, but not at a scale consistent with the claim.
- If the delta clears the guardrail, compute **percent of design capacity newly filled** (delta ÷ the project's actual engineering design reservoir area) — this is a **Supported** verdict, reported as a hydrological fill percentage, explicitly *not* the same thing as a contractor's reported "percent construction complete" (these lag each other and measure different things).

**What a verdict does and doesn't claim.** "Supported" and "Not Delivered / Conflicted" describe what the satellite evidence establishes, not a legal or investigative finding. "Not Delivered / Conflicted" means: no observable physical development consistent with the claimed project's scale — it does not by itself establish *why* (cancelled, delayed, defunded, or relocated all look similar from orbit). Where corroborating source documentation exists (as it does for Arror/Kimwarer), the verdict is stronger; where it doesn't, treat the label as evidence, not a verdict of fact.

**Current implementation vs. extensible architecture.** Dam/reservoir detection is built, run, and validated on three real cases. Road and stadium detection are deliberately *not* implemented in this submission — three half-working detectors would be a weaker proof of concept than one fully validated methodology. The architecture is designed to extend to them (see Roadmap), and the case file documents all three project types with sourced claims now, ready for that extension.

### Why the guardrail exists — a real example, not a hypothetical

Early in building this, one of our test cases (Arror and Kimwarer dams, Elgeyo Marakwet) turned out to have small, pre-existing community water pans near — but unrelated to — the claimed mega-dam sites. A naive "is there water present" check would have misread pond ~1-2 ha in size as partial evidence of a Sh66.5 billion reservoir project. The delta/guardrail approach exists specifically to catch this. See `evidence/Kimwarer_Dam.png` — a small pond is visible near a settlement cluster, but it's roughly two orders of magnitude smaller than the claimed project's 215-hectare design reservoir, and the pipeline correctly classifies it as below the guardrail rather than as supporting evidence.

## Case results (as of this submission)

| Project | Claimed | Design reservoir | Pre-baseline (ha) | Current (ha) | Delta (ha) | Verdict |
|---|---|---|---|---|---|---|
| **Thwake Dam** | Construction started 2018, phase 1 largely complete by 2026 | 2,900 ha | 16.91 | 63.03 | 46.13 | **SUPPORTED** — reservoir forming, ~1.6% of design surface area newly filled. Confirmed visually: large water body and active dam construction visible in satellite imagery. |
| **Arror Dam** | Contracted 2017, Sh38.5bn | 280 ha | 0.00 | 0.00 | 0.00 | **NOT DELIVERED / CONFLICTED** — no water at any scale. Confirmed visually: no water body of any kind visible in the AOI. |
| **Kimwarer Dam** | Contracted 2017, Sh28bn | 215 ha | 0.00 | 0.00 | 0.00 | **NOT DELIVERED / CONFLICTED** — no water above the small-pan guardrail. A small pond (~1-2 ha, unrelated to the claimed project) is visible nearby in imagery but correctly falls below the 20 ha threshold. |

Three additional cases (Rironi–Mau Summit Highway, the cancelled Modogashe–Habasweini–Mandera road, Kabarnet Stadium, Bomet IAAF Stadium) are documented with sourced claims in `promisewatch_cases_v4.csv` but **not yet run** — see Roadmap.

### A note on Thwake's low percentage

63 hectares against a 2,900-hectare design target sounds like a low number, and it is — but that's expected, not a red flag. Public reporting places Thwake's phase-1 construction at roughly 94% complete as of mid-2026, with the dam gates and upstream concrete face still outstanding. A dam typically can't hold back significant water until its gates are functional; water is routed around the site through diversion tunnels during this phase. A small but real delta above baseline is consistent with a nearly-complete dam that hasn't started impounding at scale yet — this is a genuinely different, more specific claim than either "delivered" or "not delivered," and the tool is built to say so rather than force a binary answer.

## What this can and can't detect (read this before trusting any result)

This is a hackathon proof of concept, not a finished verification system. Specific, known limitations:

- **Resolution floor.** Sentinel-2 is 10m/pixel. A large reservoir is unambiguous; a narrow river channel or a small structure can fail to register at all after cloud-masked compositing, producing a 0.0 ha result that means "undetectable at this resolution," not necessarily "doesn't exist." We validated this distinction for Arror/Kimwarer with a manual visual check of the raw imagery (see `evidence/`) — **every automated verdict in this repo should be treated as provisional until visually cross-checked**, which is a real bottleneck for scaling this beyond a handful of hand-verified cases.
- **Boreholes are out of scope.** A borehole is a few meters across — far below what free satellite imagery can resolve directly. This case type was deliberately excluded from this submission rather than faked with a weak proxy signal.
- **Roads and stadiums are not yet implemented.** The detection functions (`evaluate_road_case`, `evaluate_stadium_case`) exist as stubs with a documented approach (SAR backscatter change along a route corridor for roads; built-up footprint change for stadiums) but were not built in time for this submission — see Roadmap.
- **Coordinates matter enormously and are easy to get wrong.** Over the course of building this, the Arror and Kimwarer coordinates were revised three times from different sources before landing on values that were visually confirmed against real imagery. A wrong AOI silently produces a wrong verdict with no error message. Every case's location should be treated as needing independent confirmation, not taken from a single source.
- **"Design surface area" figures are approximate.** Thwake's 2,900 ha figure comes from Ministry of Water/press reporting; Arror's 280 ha and Kimwarer's 215 ha are reconstructed from NEMA environmental impact assessment engineering descriptions (dam height, crest length, reservoir area), not pulled from a single authoritative table. These should be verified against primary EIA documents before being cited as precise figures in any public-facing claim.

## AI-assisted development

We used an AI coding assistant (Claude) to write and iterate on the Earth Engine pipeline — cloud masking, the water index, the delta/guardrail logic — and to debug real errors as they surfaced (an unquoted project-ID string, a missing-variable error, a methodology gap where the guardrail initially compared raw extent instead of delta-over-baseline). The core idea, the choice to build a delta/guardrail-based verifier, case selection, and every accuracy judgment were made by us; every AI-assisted claim was independently verified against primary evidence (satellite thumbnails, source articles, NEMA engineering specs) before being trusted. Full detail in `written_summary.md`.

## Scalability

Three separate axes, not one:
- **Geographic** — Sentinel-2 covers the whole planet at the same free resolution; the method transfers to any region without new infrastructure.
- **Infrastructure type** — dams are proven; roads and stadiums follow the same claim→evidence→delta pattern with different indices (SAR backscatter change, built-up footprint change), not a different architecture.
- **Evidence source** — Sentinel-2 today; Sentinel-1 SAR (cloud-robust, planned for road detection) and higher-resolution commercial imagery are natural extensions where free optical imagery hits its resolution floor.

## Repository structure

```
promisewatch/
├── README.md                      # this file
├── app.py                         # Streamlit frontend — case browser + case detail, EN/SW toggle
├── requirements.txt                # streamlit, pandas
├── resolved_results.json          # real pipeline output the frontend reads (see note below)
├── promisewatch_pipeline.py       # full evidence pipeline — dam detection built, road/stadium stubbed
├── promisewatch_cases_v4.csv      # sourced case data: claims, locations, dates, design specs, sources, action links
├── deck/                          # pitch deck source + exports
└── evidence/
    ├── Thwake_Dam.png             # current-period Sentinel-2 composite, visual confirmation
    ├── Arror_Dam.png              # current-period Sentinel-2 composite, visual confirmation
    └── Kimwarer_Dam.png           # current-period Sentinel-2 composite, visual confirmation
```

## Frontend — try the actual demo

`app.py` is a Streamlit case browser and case-detail app — search/filter projects by county and status, then drill into a case to see the claim, the satellite evidence, the guardrail reasoning, and a real next-step action. English/Swahili interface toggle in the sidebar (translates UI labels; sourced case content stays in its original language — see the app's own sidebar note on this).

**It reads `resolved_results.json`, not live Earth Engine** — this is deliberate, not a shortcut: a public-facing app can't require every visitor to have Earth Engine credentials, and live per-visit satellite queries would work against the low-bandwidth goal this frontend exists to serve. `resolved_results.json` is the real output of `promisewatch_pipeline.py`'s actual run (see the Case results table above) — re-run the pipeline and update this file to refresh it, it isn't fabricated data.

**One honest gap in the app itself:** the case-detail page shows a current-period evidence image but not a baseline image — only the current-period thumbnails were exported for this submission. The baseline hectare *value* is real and displayed; the baseline *image* isn't included. The app says this explicitly rather than duplicating the current image and mislabeling it.

Run locally:
```
pip install -r requirements.txt
streamlit run app.py
```

Deploy a live link (recommended for judges — this is what makes the difference between "here's a Colab notebook" and an actual demo):
1. Push this repo to GitHub (public).
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with GitHub, and deploy `app.py` from the repo.
3. You get a public URL in about a minute — put that link in your written summary and pitch deck alongside the repo link.

## Running the evidence pipeline yourself

1. Open [Google Colab](https://colab.research.google.com) and create a new notebook.
2. In the first cell: `!pip install earthengine-api geemap pandas`
3. You'll need a Google Earth Engine account with a linked Cloud project — sign up at [code.earthengine.google.com](https://code.earthengine.google.com) if you don't have one, and update the `project=` value in the script to your own project ID.
4. Upload `promisewatch_cases_v4.csv` into the Colab session (folder icon in the sidebar → upload).
5. Paste the full contents of `promisewatch_pipeline.py` into a cell and run it. It will prompt a browser authentication flow on first run.
6. Results print as a summary table; thumbnail URLs for each case's current-period imagery print at the end for visual spot-checking.
7. Update `resolved_results.json` with any new numbers so the frontend reflects the latest run.

## Operating constraints — what's real vs. roadmap

The hackathon brief names seven conditions a solution should account for. Honest status on each, checked against what's actually built rather than planned:

| Constraint | Status |
|---|---|
| **Trust and verification** | Partially built. Every claim is sourced and cited; the delta/guardrail method and every verdict were visually cross-checked against raw imagery. Every pipeline result now carries a `checked_on_utc` timestamp, so a user always knows when a verdict was last generated — Sentinel-2 updates every ~5 days, so a stale timestamp should prompt a re-check, not be trusted indefinitely. |
| **Low bandwidth** | Partially built. `app.py` replaces the Colab-only pipeline with a Streamlit frontend, which is far lighter than a full React build and reads pre-computed results (no live Earth Engine calls per visit). Still needs a stable connection to hold its session — not optimized for 2G or genuinely unreliable connectivity, and that's a real remaining gap, not solved. |
| **Accessibility and inclusion** | Partially built. `app.py` uses plain-language verdict labels (not just jargon), pairs every status with an icon *and* text so color isn't the only signal, and passes proper labels to screen-reader-relevant elements rather than empty ones (caught and fixed via automated testing, not assumed). Not yet addressed: no testing with actual screen readers, no plain-language mode for low-literacy users beyond avoiding jargon, no disability-specific user testing. |
| **Privacy and security** | Not yet applicable — the current PoC collects no personal data. The roadmap's crowd-corroboration feature (see below) will involve people submitting reports and needs an anonymity design *before* it's built, not after. |
| **Multilingual access** | Partially built. `app.py` has an English/Swahili toggle for interface labels (buttons, section headers, status text). Sourced case content — claims, source citations, verdict reasoning — remains English-only; translating that would require either a verified human translation per case or a machine-translation step we chose not to ship without a way to verify its accuracy against the source. |
| **Local relevance** | Built and genuinely strong — every case is a sourced, real Kenyan project, cross-checked against NEMA documents and local reporting rather than a generic template. |
| **Clear next steps** | Partially built. This is the "Action" step of the Claim→Evidence→Assurance→Action framework, and until now it was the one pillar that was pure roadmap. `promisewatch_cases_v4.csv` includes a `suggested_action_if_not_delivered` column with a real, sourced contact (Kenya's Ethics and Anti-Corruption Commission — toll-free 1551, report@integrity.go.ke, anonymous whistleblower system) for every case where non-delivery is confirmed or suspected, and `app.py` now surfaces it directly on each case page rather than leaving it in a CSV a user would never see. Still minimal — no in-app routing, no case-specific escalation paths (e.g. a specific County Assembly's petition process), no tracking of what happens after a report is filed. |

## Roadmap (post-hackathon)

- Implement road corridor detection (SAR backscatter change along a route, using Sentinel-1 for cloud robustness) and stadium footprint detection.
- Replace circular AOI buffers with proper polygons following actual river courses / road routes — a circle is a rough approximation that either clips or over-includes terrain depending on the site's real shape.
- Build the "Action" layer: route low-confidence or contested cases to a crowd-corroboration channel (community reporting) rather than leaving satellite evidence as the only word, and link confirmed non-delivery cases to concrete next steps — e.g. a template petition to the relevant county assembly, or a link to Kenya's Auditor-General or EACC reporting channels.
- Low-bandwidth, multilingual (English/Swahili) frontend for browsing cases without needing to run the pipeline.
- Independent, sourced verification of every design-capacity figure against primary EIA/engineering documents rather than press reporting.

## Data sources

Claim dates, locations, and project status are sourced from public Kenyan reporting (Nation, Kenyans.co.ke, Newsroom, Pulse Sports, Wikipedia) and NEMA environmental impact assessment engineering descriptions, cited per-case in `promisewatch_cases_v4.csv`. Satellite imagery: Copernicus Sentinel-2 (ESA), accessed via Google Earth Engine.

## License

Free MIT Licence
