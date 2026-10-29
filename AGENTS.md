<!-- ============================================================
     👋 HUMAN-READ SECTION — read this yourself first. Delete this
     whole block (down to the divider) once you're done, or leave
     it — agents will just skip past an HTML comment either way.
     ============================================================ -->

# For DS3 Students: What Is AGENTS.md and Why Does This Repo Have One?

## The problem it solves

Every AI coding tool invented its own file for "here's context about my
project, please read this first": Cursor uses `.cursorrules`, Claude Code
uses `CLAUDE.md`, GitHub Copilot uses `.github/copilot-instructions.md`,
and so on. If you used more than one tool, you had to write the same
instructions multiple times in multiple formats.

**`AGENTS.md`** is the fix: a single, open, cross-tool standard — think of
it as **a README, but written for an AI agent instead of a human**. It was
put together by the teams behind OpenAI Codex, Cursor, Google, and others
specifically so you write your project instructions *once* and every
major coding agent (Claude Code, Cursor, Codex, Copilot, and more) reads
the same file. As of writing, tens of thousands of repos use it and
~20+ tools support it natively.

## What it's for

When an agent opens your repo, it has no idea:
- what the project actually does or who it's for
- how to install dependencies and run things
- where "real" code lives vs. scratch/exploration code
- how your team runs tests
- what conventions you follow (style, structure, docstrings...)
- what it should *never* do (touch `main` directly, commit secrets, etc.)

`AGENTS.md` answers all of that up front, once, so you don't have to
re-explain your project in every single chat with every tool. The agent
auto-discovers it just by being in the repo — you don't have to `@`
mention it (though you still can, to be explicit).

## Why DS3 wants you comfortable with this

- **It's now industry standard.** Understanding how to write good agent
  instructions — clear, specific, scoped, not overly long — is a real
  skill you'll use at any internship or job that touches AI tooling.
- **It's portable.** Whatever tool you or a future teammate prefers
  (Claude Code, Cursor, Codex, Copilot...), the same file works. You're
  not locked into one assistant.
- **It documents your project for humans too.** A well-written AGENTS.md
  is often just as useful for a new teammate joining the project as it is
  for an AI agent.
- **It's the difference between "the agent guesses" and "the agent
  knows."** Vague instructions produce vague/wrong help. Specific ones —
  "run `pytest` from the repo root," not "run tests" — get you working
  code the first time.

## Keep it alive — this is not a one-time setup step

A stale AGENTS.md is worse than none at all: it actively lies to the next
person (or agent) who trusts it. Every teammate on this project — and
every agent they work with — reads the *same* file, so it has to stay
accurate as the project actually changes.

**The rule: any time an agent (or you) adds a feature, changes how
something is run/tested, changes the structure, or adds a new
dependency/convention, AGENTS.md gets updated in the same PR.** Not
"eventually," not "someone else's job" — the same change that made the
file outdated is responsible for fixing it. See the instruction to this
effect in the template below; don't delete it.

## AGENTS.md vs. the `ds3-code-review` skill

These are two different things and both matter:
- **`AGENTS.md`** = standing context about *this whole project* (what it
  is, how to run it, conventions). The agent reads it automatically for
  *any* task in this repo.
- **`SKILL.md` files** (like `ds3-code-review`) = instructions for one
  *specific task* — in this case, running a strict read-only code review.
  You (or the agent) reach for it only when that specific job comes up.

A good mental model: AGENTS.md is "everything you need to know to work in
this repo," a skill is "here's exactly how to do this one thing well."

## How to fill this out (do this now)

This file is a **template**. Go through every `[bracketed placeholder]`
below and replace it with real info about your specific project — nobody
else can fill this in for you, since every DS3 project is different. Keep
the sections short and factual; don't write paragraphs the agent doesn't
need. If a command doesn't work, the agent will trust it and waste time —
so actually run each command yourself before writing it down.

Where this file goes: **the repo root**, named exactly `AGENTS.md`. If
your project ever splits into clearly separate sub-projects (e.g. a
`frontend/` and a `models/` pipeline that are basically unrelated), you
can also drop an additional `AGENTS.md` inside a subfolder — the agent
uses the one closest to the file it's working on.

Nothing tool-specific to install — Claude Code, Cursor, and Codex all
read `AGENTS.md` at the repo root automatically, no setup needed. (Claude
Code will also read a `CLAUDE.md` if present, and Cursor also honors
`.cursor/rules/` — but for a shared team repo, put the real content here
so it works everywhere, and keep the others as thin pointers to this file
if you need tool-specific extras.)

<!-- ============================================================
     TEMPLATE STARTS HERE — this is what the agent actually reads.
     Replace every [bracketed] placeholder below.
     ============================================================ -->

# AGENTS.md

## Project overview

ParkSmart is a UCSD parking decision engine that helps commuters and visitors compare eligible parking locations based on permit type, expected availability, and distance to their destination.

**Status:** Active development  
**Primary language(s)/framework(s):** Python, pandas, openpyxl, pytest, scikit-learn, FastAPI, React, and TypeScript

## Repo structure

This project follows the DS3 project template:
https://github.com/ucsdds3/ds3-project-template

Reusable logic lives in `src/`; notebooks are for exploration and should import from `src/` rather than redefining logic inline.

```text
.
├── README.md
├── AGENTS.md
├── .env.example
├── .gitignore
├── requirements.txt
├── pytest.ini
├── docs/              # data audits, assumptions, and technical documentation
├── notebooks/         # exploration, EDA, and modeling experiments
├── src/               # reusable data, modeling, and backend code (api/)
├── tests/             # pytest tests for src/
├── data/
│   ├── raw/           # original data; never edit or commit
│   └── processed/     # cleaned datasets and generated artifacts
├── results/           # model evaluations, figures, and reports
├── models/            # saved models and forecast artifacts
├── frontend/          # React + TypeScript website (synced copy; see Website)
└── infra/             # planned AWS deployment configuration
```

Some planned directories may not exist yet. Update this structure as components are added.

## Dev environment / setup

### macOS or Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### Windows PowerShell

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If `.env.example` exists, copy it to `.env` and add local API keys there. Never commit `.env`.

QPASS workbooks are not committed to GitHub. Download them into
`data/raw/QPASS/` with one command (safe to rerun; existing files are kept):

```bash
python -m src.download_qpass
```

## Running things

### Local FastAPI backend and proposed interface contract - Issue #12

After installing `requirements.txt`, run from the repository root:

```bash
python -m uvicorn src.api.main:app --reload
python -m pytest tests/test_api.py tests/test_api_schemas.py -q
```

Open `http://127.0.0.1:8000/docs` to call GET `/health` and GET `/locations`.
Only `/health` and `/locations` are implemented. Recommendation request/response
models and static JSON examples are proposed only; there is no recommendation
endpoint or logic. No model, eligibility, routing, or live data is connected.
The catalog uses fictional sample IDs and null coordinates; IDs and field names
remain proposed until Dylan and Hanrong confirm them. No data
files or secrets are required. Endpoint handling lives in `src/api/main.py`,
Pydantic v2 contracts in `schemas.py`, and the catalog in `locations.py`.
Keep future prediction logic outside endpoint handlers.
JSON uses snake_case, null for unknowns, 0–1 availability fractions, and minutes
for walking time. Arrival datetimes normalize to `America/Los_Angeles`; ambiguous
local DST times require an explicit offset. The local browser CORS allowlist
covers localhost/127.0.0.1 ports 3000 and 5173. See `docs/backend.md` and
`docs/examples/backend/` for startup, fixtures, and the pending Dylan/Hanrong
contract review. Production location IDs and permit codes require team review.
Coordination status is recorded in `docs/api_proposal.md`; the setup guide must
remain usable for teammates starting interface work with the sample catalog.
`not_implemented` means no recommendation evaluation is available;
`no_suitable_location` is reserved for a future evaluated empty result.

### Parking patterns and benchmarks — Issue #11

After building Dylan's integrated dataset, run from the repository root:

```bash
python -m src.parking_analysis
python scripts/execute_parking_notebook.py
python -m pytest tests/test_parking_benchmarks.py tests/test_parking_analysis.py -q
```

The CLI accepts `--dataset` and `--output-dir`; defaults are
`data/processed/pipeline/analysis_dataset.csv` and `results/issue11/`.
It writes EDA tables/charts, metrics, test predictions, facility errors, fallback
counts and `summary.md`. These generated artifacts stay local and gitignored.
`docs/issue11_findings.md` is a compact snapshot of locally verified results.
The walkthrough is `notebooks/11_parking_patterns.ipynb`; select `.venv` as its
VS Code Python kernel. `ipykernel` and `nbclient` are explicit requirements for
notebook execution; JupyterLab is optional for VS Code use. The execution script
uses the current Python via a temporary kernel spec, without user registration.
On PowerShell systems blocking activation, use `.\.venv\Scripts\python.exe`
in place of `python`; no execution-policy change is needed.

`src.parking_benchmarks` preserves all exported readings, validates required
fields, and keeps subtype/level distinctions. Its fixed holdout is the latest
20% of unique survey dates, rounded up; no survey date crosses the split.
Historical means back off from full parking group + weekday/time/quarter to
parking group + time, parking group, then training-wide mean. Both benchmarks
fit training data only and score identical test rows. Regression inputs exclude
observed counts, capacity, source identifiers and quality/decision metadata.
Primary predictions are clipped to [0, 1]; raw MAE/out-of-range rates remain
reported. Near full means actual availability <= 10%; MAE is in percentage points.
Coverage flags (<100 readings) are descriptive and never exclude records.
Results apply to historical survey coverage, not full quarters or live parking.
Review dataset assumptions with Dylan before requesting mentor review.

### Integrated pipeline — Issue #10

From the repository root, after `python -m src.download_qpass` and
`python -m src.download_inventory`:

```bash
python -m src.build_dataset
```

Writes `analysis_dataset.csv`, `audit.csv.gz`, `summary.md` and supporting
files to `data/processed/pipeline/` (gitignored); capacity batch reports go to
`data/interim/pipeline/capacity/`. `--reuse-inventory` skips Inventory
re-extraction. Inclusion rules, deduplication, and column definitions are in
`docs/pipeline.md`; the quality-flag policy is `QUALITY_FLAG_BLOCKS` in
`src/build_dataset.py`. Join observations to capacity by source key, never by
labels. The team-excluded Winter 2025-2026 workbook (`EXCLUDED_FILES` in
`src/download_qpass.py`) is left out of both the load and the capacity
manifest even if it is on disk; pass the same list to `load_all_qpass(...,
exclude=...)` elsewhere. Readings without a survey date are audited as
`capacity:missing_survey_date`, not fatal. Every build re-reads its outputs
with `validate_outputs` and fails on lost, multiplied, or invalid rows.
Tests: `python -m pytest tests/test_build_dataset.py -q`. The real-data check
runs when workbooks and outputs exist; point it at another output folder with
`PARKSMART_PIPELINE_DIR=<dir> python -m pytest tests/test_build_dataset.py -k real -q`.

### Inventory capacity selection — Issue #4

From the repository root, after placing QPASS workbooks in `data/raw/QPASS/`:

```bash
python -m src.download_inventory
python -m src.run_capacity_matching --rebuild-inventory
python scripts/prepare_capacity_deliverables.py
python -m pytest -q
```

The manifest is `results/capacity_matching/inventory_sources.csv`.
`--rebuild-inventory` rereads every available original workbook without modifying it;
without the flag, previously extracted groups are used. Missing Inventory quarters
remain in results. Batch flags: `--manifest`, `--qpass-dir`, `--inventory-dir`, `--output-dir`.

Individual supported cleaner commands:

```bash
python -m src.clean_inventory_legacy "data/raw/inventory/Inventory 2018-2019-2 October 1.xlsx" --academic-year 2018-2019 --quarter Fall
python -m src.clean_inventory_modern "data/raw/inventory/Inventory 2025-2026-2 Fall.xlsm" --academic-year 2025-2026 --quarter Fall
python -m src.compare_capacities --inventory "data/interim/inventory/Inventory 2025-2026-2 Fall_capacity_groups.csv" --qpass "data/raw/QPASS/QPASS 2025-2026-2 Fall.xlsm" --output-dir results/capacity_matching/fall_2025
```

Legacy tables are `5A By Lot` / `6A By Structure`; modern extraction detects
`Pivot Table Data` headers and the appropriate quarter/Inventory By Location field.
Never use all-category totals, sum overlapping lot/structure data, or force uncertain
period/subtype groups. `src.clean_inventory` is deprecated and delegates to modern;
its `capacity_status` helper remains shared.

Intermediate groups/audits: `data/interim/inventory/`. Batch outputs:
`results/capacity_matching/batch/`; combined reports live in its `combined/` folder.
Validated delivery copies: `results/capacity_matching/deliverables/`. Preparation
regenerates `docs/capacity_matching_summary.md` and flags validation failures.

Capacity selection uses valid QPASS row/group totals first. Missing or demonstrably
broken QPASS counts may fall back to one exact, positive, same-quarter Inventory
group with compatible scope and consistent period metadata. Fallback is explicitly
`assumed_same_quarter_capacity`, not verified daily capacity. Unknown zero alone
is not proof of a formula error. Conflicting evidence leaves capacity unknown.
The old snapshot-only/same-day acceptance rule is retired.

Both sources use Issue #3 mappings through `src.capacity_labels`, retaining raw
labels and restrictions. Whole-facility totals cannot fill a QPASS level, and broad
category counts cannot fill a restricted subtype. Known Fall 2025 formula errors
are source-data flags, not naming problems; their raw values remain unchanged.
Missing/invalid readings do not create group conflicts. Missing/zero identifiers,
including NaN, are excluded from eligible denominators and retained in reports.

`selected_capacity` / compatibility alias `matched_capacity`, `capacity_source`,
acceptance reason/basis and assumption describe selection. Summaries distinguish
`total_observation_slots`, `eligible_observation_slots`, `excluded_observation_slots`,
`accepted_qpass_capacities`, `accepted_inventory_capacities`, and
`accepted_capacity_matches`. Rates always use eligible slots; overall rates use
summed counts. `exact_key_candidate_rate` is Inventory key coverage, not acceptance.
Unresolved types separate naming, source errors, missing Inventory, scope and period
conflicts. See `docs/inventory_audit.md` for the full contract and assumptions.

Run `python -m pytest tests/test_capacity_integration.py -q` for generated-workbook
end-to-end checks, then full pytest. Real-workbook regeneration and the mentor's
DS3 code-review skill remain required before requesting review.

- Audit QPASS workbook structures:

  ```bash
  python -m src.qpass_inventory
  ```

- Import the reusable QPASS loader (all workbooks in `data/raw/QPASS/` in
  one table, or one workbook):

  ```python
  from src.qpass_loader import load_all_qpass, load_qpass
  df = load_all_qpass()
  ```

  Use `load_all_qpass()` instead of `pd.concat` over `load_qpass()`, which
  would drop the per-file `attrs` (skipped sheets, dropped rows).

- Issue #3 label exploration lives in `notebooks/01_issue3.ipynb` and uses
  `load_all_qpass()` followed by `src.labels.prepare_label_records()`.
  The adapter preserves loader fields and audit metadata and adds raw label
  columns; it does not resolve aliases. Set the notebook's `qpass_dir` to
  the folder directly containing the workbooks when using a custom location.
  The notebook reports the team-excluded Winter 2025–2026 workbook separately
  if present and omits it from label counts without modifying raw files.
  Label formatting preserves existing uppercase tokens and word boundaries
  around slashes/parentheses; uppercase words are not inferred to be aliases.
  Attached duration abbreviations use lowercase (for example `2hr`);
  durations and restriction wording are preserved.
  `format_category` reorders only exact numeric Hour/Hours category labels
  with recognized types to type-first order and normalizes Hr/Hrs/Hours to Hour;
  additional qualifiers and separate
  subtype restrictions are not moved or inferred.

- `src.label_decisions.standardize_labels(records)` applies formatting and
  decisions from `config/category_aliases.json` and `config/facility_aliases.json`,
  preserves raw columns, and
  adds field statuses plus `label_status` and reasons. Reviewed wording
  decisions live in `config/category_review_decisions.json`; visitor qualifiers
  and populated subtypes are flagged `keep_separate` without merging.
  Reserved, Accessible, Carpool, and Electric Vehicle wording also receives
  `keep_separate`: downstream eligibility checks must preserve its restrictions.
  Closure wording containing Closed becomes `Closure`, with unresolved status.
  Raw wording and dates remain unchanged; closure applies only to that source
  record's survey time, not permanently to the facility. It flags the audited
  unnamed Summer 2019 Week 2 row rather than asserting Pangea ownership.
  Missing guard columns produce a logger warning and an audit entry in
  `cleaned.attrs["summer_2019_check"]`; missing columns set status
  `skipped_missing_columns`, while a complete check sets `checked` and records
  its match count.
  Decisions may include an exact `scope` on original columns (the P602-only
  `2hr As` correction takes priority over the general unresolved fallback,
  regardless of JSON list order; the most-specific matching scope wins);
  historical category changes such as P782 SS to VA
  are preserved separately, not treated as aliases.
  Missing subtype alone is allowed; unchanged labels are not proof of review
  or permit eligibility. Other specialized categories remain distinct.
  `EV (Bagged Or Not In Use)` remains verbatim and unresolved with a note
  explaining its ambiguous operational status.
  Zero identifiers are unresolved across numeric/text forms, including `0.0`,
  while original values are retained.

- Issue #3 Sections 6B–8B use `src.label_reports` to group unresolved source
  rows, validate raw-value preservation, and export current inventories,
  unresolved reports, and examples as JSON under `results/issue3/`. These
  reports reflect implemented decisions, not certification of unreviewed labels.
  Section 8B calls `export_label_reports` to write compact submission reports
  and a local `standardized_records.json`; `.gitignore` allows the compact
  reports but keeps the full dataset ignored. Decision notes and a PR draft
  are in `docs/issue3_label_decisions.md` and `docs/issue3_pr_description.md`.
  Section 7C saves complete compact cleaned-label inventories for human review
  using `src.label_reports.build_cleaned_inventories`.
  Section 7D traces an exact raw label to workbook/sheet/source-row groups
  for evidence review without rereading raw workbooks.

- Launch notebooks:

  Issue #2 walkthrough: `notebooks/reshape-qpass-observations.ipynb` imports
  the loader adapter and validation functions from
  `src/qpass_observations.py`. Focused tests:
  `python -m pytest tests/test_qpass_observations.py -q`.
  The notebook uses `load_all_qpass()` from task #1, then
  `reshape_loaded_observations()` and `validate_observations()` from task #2.
  Reports cover all local workbooks and retain loader audit metadata.
  Shared loader names are retained: `type` is category and `sub_type` is
  subtype. Optional format-absent fields are informational. Blank and text
  counts have separate flags; exact repeats and conflicting identities have
  separate flags. The loader preserves per-sheet optional-header presence as
  `sub_type_in_format` / `report_type_in_format`, and raw Order as `source_order`.
  Optional statuses distinguish absent headers from blank cells. Format C
  differing-capacity groups use `ambiguous_allocation_requires_review`;
  same-capacity subsets with different open counts also retain
  `conflicting_observation`, including inside ambiguous groups. No rows
  are deleted or combined. Audited observations are integration-tested with
  `src.labels.prepare_label_records()` from main. All parsing uses the shared loader; see
  `docs/qpass_observation_contract.md` for the output contract.

  ```bash
  jupyter lab notebooks/
  ```

### Website — Issue #20

`frontend/` is a one-way copy of
[dylanwang-main/ParkSmart-Website](https://github.com/dylanwang-main/ParkSmart-Website),
which is synced with Google AI Studio. **Never edit files in `frontend/`**; the
next sync overwrites them. Change ParkSmart-Website, then from the repo root:

```bash
scripts/sync_frontend.sh            # or --ref <branch|commit>, --source <clone>
```

The script copies tracked files only, drops AI Studio's `bun.lock`, keeps local
`node_modules/`, `dist/` and `.env.local`, refreshes `package-lock.json`, and runs
the tests, type check and build. Review `git diff -- frontend` before committing.

Run the website (Node 20.19+ or 22.12+), from `frontend/`:

```bash
npm ci
npm run dev       # http://localhost:3000, on the backend CORS allowlist
npm test          # Vitest
npm run lint      # TypeScript type check
npm run build
```

`VITE_API_BASE_URL` (default `http://127.0.0.1:8000`) sets the backend; override it
in `frontend/.env.local`, never with secrets. Searches use labeled sample data
unless `VITE_RECOMMENDATION_SOURCE=api`, which sends them to
`POST /recommendations` (`frontend/src/api/recommendations.ts`) and never falls
back to sample data. Website data marked sample in `frontend/README.md` is not a
real prediction. Website pins must use registry `location_id` values; a test in
`tests/test_location_registry.py` checks this.

### Location registry — Issue #20

`config/locations.json` holds every parking location with a stable
`location_id`, its standardized dataset facilities, coordinates and
`registry_status`; `src/location_registry.py` validates it. Check it against the
integrated dataset with `python -m src.location_registry`; tests:
`python -m pytest tests/test_location_registry.py -q`. Never rename or reuse a
`location_id`. Every dataset facility must map to exactly one location. Keep
predictions keyed by facility/category/subtype/level and attach `location_id`
with `location_groups()`; only `supported` locations may be recommended.
Recent observations are not proof of current use. See
`docs/location_registry.md`.

### Eligibility and ranking — Issue #20

`src/eligibility.check_eligibility()` returns `allowed`, `not_allowed` or
`needs_verification` for a permit (`A`, `B`, `S`, `SR`, `D`, `V`), parking group
and time; only `allowed` is recommended, and unknown or conflicting rules are
never treated as allowed. `src/ranking.recommend()` takes latest-quarter groups
from `current_groups()` with `estimated_available_fraction`, and returns a first
choice and distinct backup (`to_api()` matches `ParkingChoice`). Missing
estimates are reported, never filled in. Rule sources, weights, walking
assumptions and tie-breaking are in `docs/recommendations.md`; update it and
the rule tests when permit rules change. Tests:
`python -m pytest tests/test_eligibility.py tests/test_ranking.py -q`.

- Commands for future forecasting deployment should be added after it is
  implemented and tested. Backend and parking analysis commands are documented
  above.

## Testing

- Unit tests live in `tests/` and run with:

  ```bash
  pytest
  ```

- Some tests use generated sample workbooks and do not require the original data.
- `tests/test_label_integration.py` runs the shared loader and label pipeline
  together using generated workbooks and checks row counts and raw/provenance
  preservation through `validate_label_output`. Run it with:

  ```bash
  python -m pytest tests/test_label_integration.py -q
  ```

- Real-data tests require the QPASS files in `data/raw/QPASS/`.
- Before opening or updating a PR, run `pytest` and make sure it passes.
- New reusable logic in `src/` should include corresponding tests in `tests/`.
- Important correctness checks should not exist only inside notebooks.

## Code style & conventions

- Follow PEP 8.
- Aim for a maximum line length of approximately 88 characters.
- The team has not adopted an automatic formatter or linter yet. If one is added, document its command here.
- Every public function and class in `src/` should have a docstring explaining its purpose, parameters, and return value.
- Avoid magic numbers. Use named constants or configuration values and document where important values come from.
- Keep reusable logic in `src/`, not only in notebooks.
- Preserve original facility and parking-category values when creating standardized columns.
- Flag uncertain mappings instead of guessing.
- Do not silently drop observations, sheets, or invalid values.
- Preserve provenance columns such as academic year, quarter, and source file.
- Add any new dependency to `requirements.txt`.
- Use a fixed random seed for modeling when randomness is involved.

## Git / PR workflow

- Create one GitHub Issue for each task, bug, or feature.
- Begin work from the latest version of `main`.
- Work on a separate branch, never directly on `main`.
- Use one branch and one pull request per Issue.
- Keep pull requests focused on the assigned task.
- Include `Closes #<issue-number>` in the pull-request description.
- Explain what changed, how it was tested, and any unresolved questions.
- Before opening a PR, update the branch from main, run `pytest`, and run
  the mentor-provided DS3 code-review skill against main. Read the findings,
  fix important issues, and rerun tests. Do not commit `code_review.md`.
- Another team member should review or test the work when possible.
- Only the project mentor may approve and merge pull requests into `main`.
- Team members must not merge their own pull requests.
- After a PR is merged, pull the latest `main` before creating the next branch.

## Keeping this file up to date

This is a standing instruction, not optional.

Whenever an agent or team member changes the repository structure, setup process, dependencies, commands, tests, conventions, API behavior, or deployment workflow, update the relevant section of `AGENTS.md` in the same pull request.

- Keep updates factual and concise.
- Test commands before documenting them.
- Fix outdated instructions instead of adding conflicting instructions.
- Remove “planned” labels after components are implemented.
- Mention changes to `AGENTS.md` in the pull-request summary.

## Things the agent should never do in this repo

- Never commit or hardcode passwords, API keys, credentials, or `.env` contents.
- Never push directly to `main` or merge a pull request.
- Never delete, edit, or overwrite files in `data/raw/`.
- Never commit virtual environments or large raw datasets.
- Never install packages without explaining why and updating `requirements.txt`.
- Never silently drop observations or replace missing values without documentation.
- Never guess uncertain facility, category, capacity, or permit mappings.
- Never remove or weaken tests simply to make them pass.
- Never treat Parking Occupancy summaries as individual training observations without verification.
- Never describe forecasts as guaranteed live parking availability.
- Never make unrelated changes within a focused Issue or pull request.
- Never change project commands or structure without updating `AGENTS.md`.

## Useful context

ParkSmart is being developed through the UC San Diego Data Science Student Society projects program.

The MVP should support every parking location that can be reliably recovered from the available public data. Locations with unresolved names, capacities, or parking categories should be flagged and documented.

The main public data sources are:

- UCSD QPASS workbooks
- Parking Space Inventory reports
- Parking Occupancy summary reports
- Official permit rules
- Geographic facility and entrance information
- Routing APIs
- Optional current parking-status information, if it can be validated

Important limitations:

- Detailed QPASS observations mainly cover the beginning of each quarter.
- Several academic years and quarters are missing from the public archive.
- Parking capacities and category labels may change over time.
- Parking Occupancy Reports are summaries, not dated training observations.
- Forecasts represent expected historical conditions and do not guarantee an available space.
- Optional current parking information must show its retrieval time.
- ParkSmart must continue to work when optional live-data or routing services are unavailable.

The data workflow is:

```text
Public parking data
→ workbook loading and auditing
→ standardized observations
→ facility and category reconciliation
→ capacity matching
→ cleaned analytical dataset
→ baseline and model evaluation
→ availability forecasts
```

The planned user workflow is:

```text
User inputs
→ permit filtering
→ availability lookup
→ distance and route comparison
→ parking-location ranking
→ first choice and backup
→ interactive map and recommendation explanation
```

## Period validation and rerun behavior

Missing/invalid observation dates, nonconsecutive academic-year labels, unknown
quarters, or calendar-year conflicts block both capacity sources and set
`qpass_period_metadata_conflict`. Summer/Fall use the starting calendar year;
Winter/Spring use the ending year. This is a metadata consistency check, not an
exact quarter-boundary or survey/inventory date-equality rule. The raw date and
period labels remain unchanged; unresolved cases use `period_metadata_conflict`.
All-missing-Inventory batches write header-only Inventory datasets, replacing
prior outputs. `src.audit_inventory` is a deprecated explicit-period wrapper for
the modern cleaner; it no longer filters missing-identifier source rows.

## Legacy summary scope and canonical filenames

`legacy_summary_category_requires_review` is an unverified Inventory category
scope. Such groups remain in audit outputs but cannot contradict QPASS capacity
or provide fallback. The same restriction applies to legacy-schema records with
a missing scope marker. An explicit exact-group scope decision requires both
`scope_verified=True` and nonblank `scope_verification_evidence` on the extracted
group; retain the original category_scope marker. Neither matching labels nor
a positive count establish scope equivalence. No legacy scopes are automatically
marked verified by the pipeline. Comparable verified-source disagreements remain
unresolved. Modern layout scope checks remain in force.

The downloader saves the filename linked by the archive, including spaces.
The Fall 2025 source is `Inventory 2025-2026-2 Fall.xlsm`; generated group files
use that same stem. The former local underscore alias is no longer consulted.
Existing local copies are preserved, but rerun `python -m src.download_inventory`
to generate a manifest using canonical downloaded filenames; no manual rename
is needed. Quote paths containing spaces.
