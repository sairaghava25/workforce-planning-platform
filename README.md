# Workforce Planning & Skill Gap Platform

A synthetic-data workforce planning demo that helps teams understand
upcoming project work, qualified employee capacity, skill gaps and
possible training or hiring actions.

**This is a challenge prototype, not a production HR system.** It uses
synthetic records, not real employee data.

## 1. How it works

1.  Creates master data for roles, skills and employees.
2.  Creates projects and weekly demand plans linking a project, role and
    required skill.
3.  Tracks employee allocations and weekly availability, including
    part-time hours and leave.
4.  Checks whether employee skills meet proficiency, verification,
    freshness and expiry rules for the demand week.
5.  Compares qualified capacity with demand and stores the result in
    `GapAnalysis`.
6.  Suggests `TRAIN` for smaller gaps (up to the default 1 FTE
    threshold) or `HIRE_OR_TRAIN` for larger gaps.
7.  Detects deliberate data-quality scenarios such as over-allocation,
    stale skills, duplicate demand and overlapping assignments.

Recommendations are decision support. The application does not
automatically hire, train or assign employees.

### Important: interpreting available FTE

`available_fte` is an estimate for an individual demand line. One
employee may qualify for multiple skills, so available FTE values across
different demand lines must not be added together as if capacity were
reserved. The prototype does not perform portfolio-wide constrained
assignment.

## 2. Example actors

These are workflow responsibilities, not authenticated application
roles. The demo has no login or role-based permissions.

  -----------------------------------------------------------------------
  Actor                               Responsibility
  ----------------------------------- -----------------------------------
  Employee or candidate               Provides or updates skill evidence;
                                      may be considered for training.

  Manager                             Maintains project demand and
                                      allocation decisions; reviews gaps
                                      and utilization.

  HR partner                          Reviews training or hiring
                                      suggestions.

  IT or operations partner            Supports role/skill definitions,
                                      data feeds and exception
                                      resolution.

  System administrator                Runs generation, validation and
                                      database configuration.
  -----------------------------------------------------------------------

## 3. Data model

  -----------------------------------------------------------------------
  Relationship            Cardinality             Implementation
  ----------------------- ----------------------- -----------------------
  Role → Employee         1:N                     Each employee has one
                                                  required role.

  Employee ↔ Skill        N:M                     `EmployeeSkill` stores
                                                  proficiency,
                                                  verification and
                                                  expiry.

  Project → DemandPlan    1:N                     A project can have
                                                  multiple weekly demand
                                                  lines.

  Role → DemandPlan       1:N                     Each demand line
                                                  requires one role.

  Skill → DemandPlan      1:N                     Each demand line
                                                  requires one skill.

  Employee ↔ Project      N:M                     `Allocation` stores
                                                  project assignments and
                                                  hours.

  Employee → Availability 1:N                     Availability is
                                                  recorded by employee
                                                  and week.

  Employee → Training     1:N                     Training records
                                                  connect an employee and
                                                  a skill.

  DemandPlan →            1:0..1 current result   Each demand line has a
  GapAnalysis                                     current result after
                                                  analysis.
  -----------------------------------------------------------------------

See [`DATA_DICTIONARY.md`](./DATA_DICTIONARY.md) for field definitions,
keys, constraints, lifecycle rules and validation notes.

## 4. Requirements

-   Python version compatible with `backend/requirements.txt`
-   Node.js and npm
-   PostgreSQL

The backend uses FastAPI and SQLAlchemy. The frontend uses Next.js.

## 5. Configure and run (Windows PowerShell)

### 5.1 Configure PostgreSQL

Create a local PostgreSQL database, for example `workforce_planning`.

In `backend/`, copy `.env.example` to `.env` if that example file is
supplied. Edit `.env` and set your local connection string. The template
format is:

``` text
DATABASE_URL=postgresql+psycopg://postgres:YOUR_POSTGRES_PASSWORD@localhost:5432/workforce_planning
```

Replace the example password and database name with your own. The
database must already exist, and the database user needs permission to
create tables and write data. URL-reserved characters in a password must
be percent-encoded.

**Keep `backend/.env` private. Do not commit it or include it in a
public ZIP.** Include `.env.example` instead.

The backend creates its tables at startup, but it does not create the
PostgreSQL database. Starting the API reads the current database
records; it does not automatically regenerate the dataset.

### 5.2 Start the backend

From the project root:

``` powershell
Set-Location .\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

-   API: http://127.0.0.1:8000
-   Interactive API documentation: http://127.0.0.1:8000/docs

The backend loads `backend/.env` regardless of the terminal's current
directory.

### 5.3 Start the frontend

Open a second PowerShell terminal from the project root:

``` powershell
Set-Location .\frontend
npm install
npm run dev
```

Open http://localhost:3000.

The Next.js server proxies `/api/*` requests to `http://127.0.0.1:8000`,
so the browser and frontend use one origin. To use a different backend
host, set `BACKEND_API_URL` in the environment where you launch Next.js.

If `node` or `npm` is not recognized, install Node.js, ensure its
install directory (commonly `C:\Program Files\nodejs`) is on `PATH`,
reopen the terminal, and check:

``` powershell
node --version
npm --version
```

## 6. Dataset, generation and safety

The challenge baseline uses synthetic data with default seed `20261022`.

  Entity                          Baseline volume
  ------------------ ----------------------------
  Employees                                 5,000
  Skills                                      300
  Projects                                    500
  Planning horizon     12 months of weekly demand

Other entity counts depend on generated relationships and records. The
generator creates master data first, followed by related skill, project,
availability, allocation, demand, training and gap records. Deliberate
labelled cases are added separately.

### Important database warning

The generator CLI has different modes:

-   **No arguments:** imports the existing full dataset from
    `backend/generated_data_full` into the PostgreSQL database
    configured in `backend/.env`.
-   **Generation options or `--generate`:** generates a new synthetic
    dataset and replaces workforce records in the configured database.

The no-argument import is validated and committed as one transaction; a
failed import or validation rolls back. A successful import nevertheless
**replaces workforce data in that database**. Existing audit events are
retained.

**Do not run import, generation or reproducibility commands against a
database containing data you need to preserve.** Use a dedicated
challenge database, not a production or unrelated database.

### Import the supplied full dataset

Only do this when you intentionally want to import the supplied dataset
into the configured database. From `backend/`:

``` powershell
python -m app.generate_dataset
```

### Generate a small starter dataset

Use a separate test database and output directory if you want to try
generation without overwriting the supplied dataset files:

``` powershell
Set-Location .\backend
python -m app.generate_dataset --employees 100 --skills 30 --projects 10 --months 12 --seed 20261022 --output-dir .\generated_data_starter
```

### Generate the challenge baseline

This is a substantial dataset. Use a dedicated challenge database and
allow additional time, memory and disk space:

``` powershell
Set-Location .\backend
python -m app.generate_dataset --employees 5000 --skills 300 --projects 500 --months 12 --seed 20261022 --output-dir .\generated_data_full
```

### Verify reproducibility

The CLI supports `--verify-reproducibility`. It regenerates data using
the selected parameters and compares SHA-256 checksums for exported CSV,
JSON and SQL seed files. This can replace generated records in the
configured database. Use only a dedicated challenge database and a safe
output directory.

Example:

``` powershell
Set-Location .\backend
python -m app.generate_dataset --employees 100 --skills 30 --projects 10 --months 12 --seed 20261022 --output-dir .\generated_data_starter --verify-reproducibility
```

Generated outputs include entity CSV and JSON files, `seed.sql`,
`source_manifest.json`, `validation_summary.json`, `checksums.json`, and
separate `ground_truth.csv` and `ground_truth.json` files. Ground-truth
labels are not mixed into analytical feature exports. Audit events
remain in the database and are excluded from deterministic feature-data
checksums because their IDs and timestamps describe individual runs.

## 7. API overview

  -----------------------------------------------------------------------
  Endpoint                            Purpose
  ----------------------------------- -----------------------------------
  `POST /api/generator/run`           Generate and persist seeded
                                      synthetic records.

  `POST /api/analysis/run`            Recalculate utilization,
                                      exceptions, gaps and
                                      recommendations.

  `GET /api/dashboard`                Return workforce, demand,
                                      utilization and gap metrics.

  `GET /api/validation`               Return validation checks and
                                      results.

  `GET /api/recommendations`          Return current gap-driven
                                      recommendations and assumptions.

  `GET /api/exceptions`               Return detected synthetic exception
                                      records.

  `GET /api/exports/{entity}`         Export a persisted entity as CSV;
                                      `ground_truth` is a separate label
                                      export.
  -----------------------------------------------------------------------

Explore the API at http://127.0.0.1:8000/docs.

## 8. Ground-truth scenarios

The dataset includes four deliberate challenge scenarios:

  -----------------------------------------------------------------------
  Scenario                            What it demonstrates
  ----------------------------------- -----------------------------------
  Allocation exceeds availability     Weekly allocated hours exceed
                                      availability after leave.

  Stale skill treated as current      A skill profile is marked current
                                      despite exceeding its freshness
                                      limit.

  Demand double-counted               Two demand rows share the
                                      project/role/skill/week/version
                                      business key.

  Overlapping project assignments     One employee has allocations to
                                      different projects in the same
                                      week.
  -----------------------------------------------------------------------

Labels are stored separately. Analysis is expected to detect issues from
source records and business rules, not by reading the labels.

## 9. Validation and outputs

Validation and analysis cover:

-   Primary-key and foreign-key integrity.
-   Identifier formats and duplicate demand business keys.
-   Date order and lifecycle rules.
-   Availability arithmetic and allocation/capacity exceptions.
-   Skill verification, freshness and expiry.
-   Demand coverage and FTE gap calculations.
-   Detected anomaly scenarios.
-   Export checksums and reproducibility.

Dashboard and API counts reflect the current database state and may
change after importing, generating or analysing data.

## 10. Demo / interview explanation

> "The system starts with a relational workforce model and deterministic
> synthetic records. Project demand is defined by role, skill and week.
> Employee skills count only when proficiency, verification age and
> expiry pass the configured rules. Capacity accounts for contracted
> hours, leave and existing allocations, so part-time schedules affect
> utilization. The platform compares qualified capacity with demand,
> stores traceable gap results and suggests training for smaller gaps or
> hiring-or-training for larger ones. Four deliberate exception
> scenarios are kept in a separate ground-truth export. The API
> validates relationships, arithmetic and lifecycle rules, and the CLI
> supports reproducible exports."

## 11. Limitations and production considerations

-   **Synthetic data only:** generated names and `.example` email
    addresses are placeholders.
-   **No authentication:** add login and role-based access controls
    before handling real workforce data.
-   **Demo schema management:** SQLAlchemy `create_all` is used.
    Production deployments need managed migrations, backups,
    audit-retention policies and operational monitoring.
-   **Simple recommendations:** the configurable training threshold does
    not account for hiring lead times, training availability, costs,
    employee preferences or location.
-   **No portfolio-wide optimization:** per-demand-line available FTE
    estimates can overlap; the prototype does not solve constrained
    assignment across simultaneous demands.
-   **Limited historical traceability:** run-level audit snapshots are
    recorded, but this is not a fully immutable, row-level event-sourced
    HR system.
-   **Dataset replacement:** generator/import workflows can replace
    workforce records in the configured database. Always use a dedicated
    challenge database for those operations.

## 12. Project documentation

-   [`DATA_DICTIONARY.md`](./DATA_DICTIONARY.md) --- entities, fields,
    relationships, constraints and validation rules.
-   [`SOURCE_MANIFEST.md`](./SOURCE_MANIFEST.md) --- data provenance,
    synthetic generation and reproducibility notes.
-   [`AI_PROMPTS.md`](./AI_PROMPTS.md) --- AI prompts used during
    development, if included in the submission.

## 13. Before submitting

-   Confirm the backend and frontend start successfully.
-   Open the dashboard and review the main pages.
-   Check the API documentation at `/docs`.
-   Include the supplied dataset and its manifest/checksum files.
-   Include `.env.example`, but exclude `backend/.env`.
-   Exclude `frontend/node_modules`, `frontend/.next`, Python caches,
    virtual environments and temporary databases.
-   Do not include credentials, secrets or real personal data.
-   Do not run generation or import commands against a database whose
    data you need to preserve.
