# Source manifest

## Data provenance

- **Source type:** Fully synthetic, locally generated records.
- **External source URL / dataset version / retrieval date:** Not applicable; no external records are used.
- **License / attribution:** No third-party dataset is redistributed. Faker is an installed software dependency, not a workforce-data source. Names and emails in generated records are deterministic placeholders; emails use the reserved `.example` domain.
- **Personal or confidential data:** None is intentionally collected or embedded in the generator.
- **Transformations:** Seeded random generation creates master records first, then employee skills, projects, weekly availability/leave, allocations, demand, training, derived gap analysis and finally isolated labelled exception cases. IDs and derived metrics are generated from their parent/source records.
- **Reproducibility:** Default seed `20261022`; scale and seed are configurable. The CLI writes a run-specific `source_manifest.json` containing the exact parameters, entity counts and output description. `--verify-reproducibility` regenerates an independent dataset and compares exported-data checksums.
- **Ground truth:** Four deliberate edge-case labels are stored in the separate `AnomalyIssue` table and exported as `ground_truth.csv`/`.json`; labels are not included in analytical feature exports or read by the analysis rules.
- **Database:** The application and generator use the SQLAlchemy URL configured in `backend/.env`. The starter `.env` is a PostgreSQL connection template; no database password is stored in this source manifest.
- **Audit history:** Run-level audit events remain in the configured database. They are excluded from deterministic checksums because event IDs and timestamps describe individual executions.

To create a manifest for a concrete dataset run and inspect counts/checksums, run the CLI documented in [README.md](./README.md).
