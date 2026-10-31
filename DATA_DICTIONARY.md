# Data dictionary and validation rules

Dates are ISO calendar dates (`YYYY-MM-DD`); timestamps are ISO datetimes. Hours are hours per employee per weekly period; FTE is a fraction of the configured standard work week. `Required` means non-null in the stored model unless noted. Primary keys are unique and immutable; foreign keys must refer to an existing parent. Enum lists describe allowed values checked by the generator/validator.

## Core entities

| Entity / field | Type | Required | Allowed values / units | Unique | Validation / meaning |
|---|---|---:|---|---|---|
| **Employee** `id` | string | Yes | `EMP-` + six digits | PK | Immutable employee identifier. |
| `name` | string | Yes | Synthetic display name | No | Generated as `Employee NNNNN`; no personal names. |
| `email` | string | Yes | `.example` address | Yes | Unique placeholder address; not a contact address. |
| `role_id` | string | Yes | `Role.id` | No | Required FK; one employee has one role. |
| `department` | string | Yes | Generated role department | No | Must match the employee's selected role department. |
| `employment_type` | string | Yes | `FULL_TIME`, `PART_TIME` | No | Controls generated weekly contracted hours. |
| `weekly_hours` | float | Yes | Hours/week; 20 or 40 in baseline | No | `> 0`, and generated capacity is at most 40 hours/week. |
| `status` | string | Yes | `ACTIVE`, `INACTIVE` | No | Lifecycle state; baseline employees are active. |
| `joined_on` | date | Yes | Calendar date | No | Must not be after the generation reference date. |
| **Role** `id` | string | Yes | `ROLE-` + three digits | PK | Immutable role identifier. |
| `name` | string | Yes | Role taxonomy name | Yes | Unique role name. |
| `department` | string | Yes | Department name | No | Taxonomy grouping used to align project and role demand. |
| **Skill** `id` | string | Yes | `SKL-` + six digits | PK | Immutable skill identifier. |
| `name` | string | Yes | Skill taxonomy name | Yes | Unique skill name. |
| `category` | string | Yes | `Technical`, `Cloud`, `Data`, `Quality`, `Business` | No | Taxonomy category. |
| `verification_days` | integer | Yes | Days; 180, 365 or 540 in baseline | No | Skill-specific maximum freshness period. |
| **EmployeeSkill** `id` | string | Yes | `ES-` + eight digits | PK | Immutable bridge/profile identifier. |
| `employee_id` | string | Yes | `Employee.id` | No | Required FK. |
| `skill_id` | string | Yes | `Skill.id` | No | Required FK. |
| `proficiency` | integer | Yes | 1–5 | No | Defined scale: 1 awareness, 2 basic, 3 working, 4 advanced, 5 expert. At least the configured minimum (3 by default) is needed for qualified capacity. |
| `last_verified` | date | Yes | Calendar date | No | Cannot be after the planning reference date in generated profiles. |
| `expires_on` | date | No | Calendar date or null | No | If present, must be on/after `last_verified`; qualified only through the demand period's expiry date. |
| `verified_current` | boolean | Yes | `true`, `false` | No | A stale-current mismatch is an explicit labelled exception, not silently corrected. |
| **Project** `id` | string | Yes | `PRJ-2026-` + six digits | PK | Immutable project identifier. |
| `name` | string | Yes | Synthetic project name | No | Descriptive project label. |
| `department` | string | Yes | Generated department | No | Used to select a compatible role taxonomy. |
| `start_date` | date | Yes | Calendar date | No | Project effective start. |
| `end_date` | date | Yes | Calendar date | No | Must be on/after `start_date`. |
| `status` | string | Yes | `PLANNED`, `ACTIVE`, `ON_HOLD`, `COMPLETED` | No | Project lifecycle; generator currently emits the first three. |
| `priority` | string | Yes | `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` | No | Planning priority. |
| **DemandPlan** `id` | string | Yes | `DEM-<project-id>-<ISO-year>W<week>-R<role-number>-S<skill-number>` | PK | Stable project/week/role/skill-based identifier. Deliberate duplicate rows use a `-DUP-001` suffix and are separately labelled. |
| `project_id` | string | Yes | `Project.id` | No | Required FK. |
| `role_id` | string | Yes | `Role.id` | No | Required FK. |
| `skill_id` | string | Yes | `Skill.id` | No | Required FK. |
| `period_start` | date | Yes | Monday weekly period | No | Must fall within the project effective dates for baseline demand. |
| `required_fte` | float | Yes | FTE | No | Nonnegative demand for that project/role/skill/week. |
| `demand_version` | integer | Yes | Positive integer; baseline `1` | No | Version distinguishes approved planning revisions. |
| `status` | string | Yes | `APPROVED` in baseline | No | Demand lifecycle state. |
| **Allocation** `id` | string | Yes | `ALLOC-2026-` + nine digits | PK | Immutable allocation identifier. |
| `employee_id` | string | Yes | `Employee.id` | No | Required FK. |
| `project_id` | string | Yes | `Project.id` | No | Required FK. |
| `period_start` | date | Yes | Calendar date | No | Start of allocation period. |
| `period_end` | date | Yes | Calendar date | No | Must be on/after start; baseline allocations span one week. |
| `allocated_hours` | float | Yes | Hours | No | Nonnegative; may deliberately exceed availability in a labelled exception. |
| `status` | string | Yes | `CONFIRMED` in baseline | No | Allocation lifecycle state. |
| **Availability** `id` | string | Yes | `AVL-` + nine digits | PK | Immutable availability record identifier. |
| `employee_id` | string | Yes | `Employee.id` | No | Required FK. |
| `period_start` | date | Yes | Weekly period | With employee | Unique `(employee_id, period_start)` key. |
| `working_hours` | float | Yes | Hours/week | No | Contracted hours for this period. |
| `leave_hours` | float | Yes | Hours/week | No | Must be between zero and working hours. |
| `available_hours` | float | Yes | Hours/week | No | Must reconcile to `working_hours - leave_hours`. |
| **Training** `id` | string | Yes | `TRN-` + seven digits | PK | Immutable training record identifier. |
| `employee_id` | string | Yes | `Employee.id` | No | Required FK. |
| `skill_id` | string | Yes | `Skill.id` | No | Required FK. |
| `status` | string | Yes | `PLANNED`, `IN_PROGRESS`, `COMPLETED` | No | Lifecycle controls date requirements. |
| `hours` | float | Yes | Training hours | No | Nonnegative planned/actual training duration. |
| `started_on` | date | No | Calendar date or null | No | Null for `PLANNED`; required for `IN_PROGRESS` and `COMPLETED`. |
| `completed_on` | date | No | Calendar date or null | No | Required only when completed; not before `started_on`. |
| **GapAnalysis** `id` | string | Yes | `GAP-<demand-id>` | PK | Deterministic current analysis result ID; recomputed on each analysis run. |
| `demand_id` | string | Yes | `DemandPlan.id` | No | Required FK; exactly one current row per demand line after analysis. |
| `required_fte` | float | Yes | FTE | No | Copied from the source demand line. |
| `available_fte` | float | Yes | FTE | No | Qualified capacity after leave and existing allocation, divided by standard weekly hours. This is a per-demand-line estimate, not a portfolio assignment. |
| `gap_fte` | float | Yes | FTE | No | `max(0, required_fte - available_fte)`. |
| `status` | string | Yes | `GAP`, `COVERED` | No | `GAP` if the shortfall is over the small numeric tolerance; otherwise `COVERED`. |
| `assumptions` | string | Yes | Human-readable policy summary | No | Records proficiency, freshness, expiry, capacity and standard-hours assumptions used. |

## Policy and traceability entities

| Entity / field | Type | Required | Allowed values / units | Unique | Validation / meaning |
|---|---|---:|---|---|---|
| **PolicySetting** `key` | string | Yes | Policy key | PK | Examples: `stale_skill_days`, `minimum_proficiency`, `standard_week_hours`, `training_gap_max_fte`. |
| `value` | string | Yes | Numeric value serialized as text | No | Parsed as a number by policy consumers. |
| `description` | string | Yes | Explanation | No | Documents the decision rule. |
| **AnomalyIssue** `id` | string | Yes | `GT-` + three digits | PK | Ground-truth case ID, kept separate from analysis input exports. |
| `issue_type` | string | Yes | `ALLOCATION_EXCEEDS_AVAILABILITY`, `STALE_SKILL_TREATED_CURRENT`, `DEMAND_DOUBLE_COUNTED`, `OVERLAPPING_PROJECT_ASSIGNMENT` | No | Expected anomaly label. |
| `entity_id` | string | Yes | ID of the affected employee, employee skill or demand row | No | Target must exist in its corresponding source entity; allocation IDs are included in allocation-case details. |
| `ground_truth` | boolean | Yes | `true` for injected cases | No | Expected label, not a feature used by analysis. |
| `details` | string | Yes | Explanation | No | Human-readable injected-case description. |
| **AuditEvent** `id` | string | Yes | `EVT-` + generated unique token | PK | Append-only run-event identifier. |
| `event_type` | string | Yes | `DATA_GENERATED`, `ANALYSIS_RUN` | No | State-changing workflow event. |
| `entity_type` | string | Yes | `DATASET`, `ANALYSIS` | No | Scope of event. |
| `entity_id` | string | Yes | Referenced dataset/analysis scope | No | Audit reference; intentionally not a cascading FK. |
| `details` | string | Yes | JSON text | No | Seed, counts or analysis summary. |
| `created_at` | datetime | Yes | UTC timestamp by default | No | Event time; audit history is not part of reproducible feature-data checksums. |

## Lifecycle, coverage and validation notes

- **Employee/project state:** employee is `ACTIVE` or `INACTIVE`; project is planned, active, on hold or completed. Project effective end cannot precede start.
- **Skill state:** proficiency is a 1–5 integer. A profile counts for a demand week only if it meets the minimum proficiency, `verified_current` is true, it is not future-dated, it is within the stricter of the policy freshness and skill taxonomy windows, and it has not expired by that demand week.
- **Training state:** planned has no start/completion dates; in progress has a start but no completion; completed has both dates, with completion not before start.
- **Capacity:** `available_hours = working_hours - leave_hours`. Weekly utilization is `allocated_hours / available_hours`; if availability is zero and allocation is positive, the period is overallocated. Part-time hours are not normalized to 40 before utilization.
- **Demand duplication:** the intended business key is `(project_id, role_id, skill_id, period_start, demand_version)`. A duplicate is valid only as an explicitly labelled edge case; normal demand rows must not share this key.
- **Join validation:** all IDs in dependent records must resolve to their parent IDs. The database enforces declared foreign keys; `/api/validation` and the CLI report referential integrity, key formats, capacity arithmetic, date order, lifecycle and ground-truth target checks.
- **Analysis assumptions:** minimum proficiency defaults to 3, standard week defaults to 40 hours, stale skill limit defaults to 365 days, and training is suggested for gaps up to 1 FTE. Stored `PolicySetting` rows are the source of those thresholds.
