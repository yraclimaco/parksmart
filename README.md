# ParkSmart

ParkSmart is a UC San Diego parking decision project. It cleans historical QPASS
observations, standardizes parking labels, and attaches defensible parking
capacities before availability analysis. Forecasting and the web interface are
planned; the current implementation includes the data pipeline and historical
availability benchmarks.

## Setup and capacity matching (Issue #4)

Run from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m src.download_qpass
python -m src.download_inventory
python -m src.run_capacity_matching --rebuild-inventory
python scripts/prepare_capacity_deliverables.py
python -m pytest -q
```

Downloads require access to the public UCSD archive. Original workbooks stay local
in `data/raw/QPASS/` and `data/raw/inventory/` and are never modified. The Inventory
source manifest is generated at `results/capacity_matching/inventory_sources.csv`.
No API key is needed for this pipeline; `.env.example` is an optional template.

Capacity selection prefers valid QPASS totals for the exact parking group.
Missing or demonstrably broken totals may use one compatible same-quarter
Inventory candidate, explicitly labeled as an assumption. Uncertain scopes,
conflicting capacities or period metadata remain flagged with unknown selected
capacity. No cross-quarter carry or fuzzy facility matching is performed.

## Outputs and documentation

### Parking analysis (Issue #11)

After `python -m src.build_dataset`, run `python -m src.parking_analysis`.
Open `notebooks/11_parking_patterns.ipynb` in VS Code using the `.venv` kernel,
or execute it with `python scripts/execute_parking_notebook.py`.
The notebook compares training-only historical averages and linear regression
using the same later survey dates, with overall and near-full errors.
Local reports, charts and predictions go to `results/issue11/`.
See [findings and limitations](docs/issue11_findings.md) for the verified snapshot.
Notebook execution needs the `ipykernel` and `nbclient` dependencies in
`requirements.txt`; JupyterLab is optional when using VS Code.
If PowerShell blocks activation, use `.\.venv\Scripts\python.exe` instead of
`python` in these commands.

- [Inventory schema, assumptions and run instructions](docs/inventory_audit.md).
- [Capacity selection results and quarter-level rates](docs/capacity_matching_summary.md).
- [Packaged datasets and unresolved cases](results/capacity_matching/deliverables/README.md).
- [QPASS loader schema and source limitations](docs/qpass_schema_audit.md).
- [Shared standardized-label decisions](docs/issue3_label_decisions.md).
- [Development conventions](AGENTS.md).

Reusable code lives in `src/`, tests in `tests/`, and exploration in `notebooks/`.
Intermediate Inventory groups/audits are in `data/interim/inventory/`; batch
reports are in `results/capacity_matching/batch/`. Delivery copies are compressed
CSVs in `results/capacity_matching/deliverables/`; pandas reads `.csv.gz` directly.
Frontend, infrastructure and model folders are placeholders for later work.

## Git and GitHub workflow for DS3 projects

Using Git and GitHub well is just as important as writing good code. A clean workflow makes collaboration easier and helps the project stay organized.

### 1. Use GitHub Issues for tracking work

Create an Issue for each task, bug, experiment, or feature request. Keep each issue focused and include:

- a short title
- a clear description of the work
- acceptance criteria if relevant
- labels such as bug, enhancement, documentation, or blocked

Example workflow:
- one issue for data cleaning
- one issue for model training
- one issue for documentation updates

### 2. Use branches to separate work

Each person or feature should usually work in its own branch. This prevents people from overwriting each other's changes.

Common branch commands:

```bash
git branch
git checkout -b feature/my-task
git checkout main
git branch -d feature/my-task
```

What they mean:
- `git branch` shows existing branches
- `git checkout -b feature/my-task` creates and switches to a new branch
- `git checkout main` switches back to the main branch
- `git branch -d feature/my-task` deletes a branch after it is merged

### 3. Use pull requests to merge code into main

When work is complete, open a Pull Request (PR) from your branch into `main`. A PR is the place to review changes, discuss issues, and confirm everything is ready.

Important rule:
- Only project managers or mentors should approve pull requests.
- Students should contribute code, but approvals should be handled by the designated maintainers.

### 4. Basic Git commands and what they mean

```bash
git clone <repo-url>
git status
git add <file>
git add .
git commit -m "Describe your change"
git push origin <branch-name>
git log
git merge <branch-name>
git rebase <branch-name>
```

What they mean:
- `git clone` copies a repository from GitHub to your local machine
- `git status` shows which files changed and what branch you are on
- `git add` stages files for commit
- `git commit` saves staged changes with a message
- `git push` uploads your local commits to GitHub
- `git log` shows recent commit history
- `git merge` combines another branch into your current branch
- `git rebase` reapplies your commits on top of another branch and can help keep history cleaner

### 5. Recommended team habits

- Pull the latest changes before starting work
- Keep commits small and descriptive
- Avoid committing large data files or secrets
- Open a PR early for feedback, not only at the end
- Resolve merge conflicts carefully and communicate with the team

### 6. Example workflow

```bash
git checkout main
git pull origin main
git checkout -b feature/data-cleaning
git status
git add .
git commit -m "Add initial data cleaning script"
git push origin feature/data-cleaning
```

Then open a Pull Request on GitHub and wait for approval from the appropriate project manager or mentor.

## Notes for DS3 projects

This template is intentionally simple so students can focus on the science instead of setup. As projects grow, teams can add:

- experiment tracking
- model checkpoints
- deployment scripts
- cloud infrastructure (AWS/GCP) in `infra/`
- frontend UI/UX code in `frontend/`
- CI checks
- docs pages
