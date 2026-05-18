# Fabric Power BI CI/CD

This repository contains the scripts and PBIP artifacts used to deploy Microsoft Fabric / Power BI reports into workspaces through GitHub Actions and the `fabric-cicd` Python package.

The repo is organized around one deployment branch per dashboard, plus a shared branch for the deployment scripts themselves.

## Branching Model

### `fabric-cicd`

This is the shared integration branch for the deployment scripts and repository-wide fixes.

- Updates to `scripts/`, `parameter.yml`, and supporting deployment logic should go here.
- If the deployment logic has a bug, fix it in this branch first.
- Developers working on a report should keep their dashboard branch aligned with this branch so they get the latest script changes.

### `master/<DashboardName>`

Each dashboard has its own locked master branch.

Examples:

- `master/SalesDashboard`
- `master/FinanceDashboard`

Rules for master branches:

- Treat these as release branches for a single dashboard.
- Do not mix unrelated dashboards in the same master branch.
- The branch name must match the report folder name under `Reports/`.
- A push to `master/**` triggers deployment for that dashboard only.

### `feature/<Developer>/<DashboardName>`

Developers create feature branches from the dashboard master branch.

Example:

- `feature/ShivaramJimada/SalesDashboard`

Before working, the feature branch should be up to date with both:

- `master/<DashboardName>` for the current PBIP content
- `fabric-cicd` for the latest deployment scripts and fixes

This keeps the PBIP files and deployment automation in sync.

## Repository Layout

```text
.
├── parameter.yml
├── README.md
├── requirements.txt
├── Reports/
│   ├── SalesDashboard/
│   ├── FinanceDashboard/
│   └── ...
└── scripts/
	├── deploy.py
	├── auth.py
	├── semantic_model_list.py
	├── semantic_model_id_replace.py
	├── semantic_model_refresh.py
	└── .github/workflows/deploy.yml
```

Each report lives in its own folder under `Reports/`. The folder name must match the branch/dashboard name used in deployment.

## How Deployment Works

The deployment flow is branch-driven:

1. A developer updates a dashboard in a feature branch.
2. The feature branch is merged into the corresponding `master/<DashboardName>` branch.
3. A push to `master/**` triggers the deployment workflow.
4. GitHub Actions sets `REPORT_FOLDER` from the branch name.
5. `scripts/deploy.py` publishes the PBIP content for that dashboard only.
6. The script exports semantic model IDs, replaces references in PBIR files, republishes the report, and triggers refresh.

Because each dashboard has its own branch, Fabric CI/CD does not need to publish every report when only one report changes.

## Working on a New Dashboard

When a dashboard is created for the first time:

1. Download the latest `.pbix` from the workspace.
2. Convert the file to PBIP format.
3. Save it inside a folder under `Reports/` whose name matches the dashboard branch.
4. Create a feature branch for development.
5. Create the corresponding `master/<DashboardName>` branch when the dashboard becomes the release branch.
6. Raise a pull request from the feature branch into the dashboard master branch.

Example folder structure for the `SalesDashboard` report:

```text
Reports/
└── SalesDashboard/
	├── Sales Dashboard.pbip
	├── Sales Dashboard.Report/
	└── Sales Dashboard.SemanticModel/
```

## Working on an Existing Dashboard

If the dashboard already exists in Git:

1. Create a new feature branch from `master/<DashboardName>`.
2. Pull the latest changes from `master/<DashboardName>` before editing.
3. Pull the latest changes from `fabric-cicd` so the deployment script stays current.
4. Make changes only in the dashboard folder for that report.
5. Open a pull request back into `master/<DashboardName>` when done.

This avoids re-downloading the report from the workspace every time.

## Pull Request Flow

1. Complete changes in `feature/<Developer>/<DashboardName>`.
2. Open a pull request into the matching `master/<DashboardName>` branch.
3. Another developer reviews and approves the change.
4. Merge into master after approval.
5. Deployment starts automatically from the merged `master/**` branch.

## Deployment Script

The deployment entry point is `scripts/deploy.py`.

What it does:

- Validates the target folder under `Reports/`
- Publishes semantic models
- Exports semantic model IDs to `semantic_models.csv`
- Updates PBIR files with the correct semantic model IDs
- Republishes the report files
- Triggers semantic model refresh for the published model

The script expects a single dashboard folder through `REPORT_FOLDER`.

## Environment Variables

For local development, use `.env` or set the variables in PowerShell before running the script.

Required variables:

```dotenv
TENANT_ID="..."
CLIENT_ID="..."
CLIENT_SECRET="..."
ENVIRONMENT="development"
WORKSPACE_ID="..."
REPORT_FOLDER="SalesDashboard" (This is not required as GitActions will auto fetch based on the master/branchname)
PYTHONUNBUFFERED="1"
```

The GitHub workflow maps repository secrets and variables to the same `FABRIC_*` names.

Recommended local PowerShell setup:

```powershell
$env:FABRIC_TENANT_ID="..."
$env:FABRIC_CLIENT_ID="..."
$env:FABRIC_CLIENT_SECRET="..."
$env:FABRIC_WORKSPACE_ID="..."
$env:FABRIC_ENVIRONMENT="development"
$env:PYTHONUNBUFFERED="1"
python -u .\scripts\deploy.py
```

## parameter.yml

`parameter.yml` controls find-and-replace values used during deployment.

It is used to keep report and semantic model references aligned across environments, including:

- Workspace URLs
- datasource names, database names
- Works with Snowflake, Databrics, SQL and mostly used.
- Optional environment variable based replacements

Important notes:

- The report name in the workspace must match the name in Git.
- The workspace must not contain duplicate report or semantic model names.
- If a report already exists, deployment replaces the existing dashboard content rather than creating a second one.

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Then set the required environment variables and run:

```powershell
python -u .\scripts\deploy.py
```

## GitHub Actions

The workflow is defined in `scripts/.github/workflows/deploy.yml`.

It currently:

- Triggers on pushes to `master/**`
- Derives `REPORT_FOLDER` from the branch name
- Installs Python 3.12
- Runs the deployment script for the matching dashboard

## Troubleshooting

- If deployment fails with a missing folder error, confirm the dashboard folder exists under `Reports/`.
- If authentication fails, check the Fabric tenant, client ID, and client secret values.
- If refresh fails, the semantic model may need explicit connection credentials in Fabric.
- If the wrong report is deployed, verify that the branch name and folder name match exactly.
- If the deployment script is not picking up logs in real time, keep `PYTHONUNBUFFERED=1` or run Python with `-u`.

## Summary

Use `fabric-cicd` for deployment logic changes, use `master/<DashboardName>` for each dashboard release branch, and use `feature/<Developer>/<DashboardName>` for day-to-day development.

This keeps dashboards isolated, reduces unnecessary republishing, and makes the deployment flow predictable.