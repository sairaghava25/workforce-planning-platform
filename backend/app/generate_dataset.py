import argparse
import csv
import hashlib
import json
import uuid
import subprocess
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, SmallInteger, insert, select
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable


TABLES = {
    "employees": "Employee",
    "roles": "Role",
    "skills": "Skill",
    "employee_skills": "EmployeeSkill",
    "projects": "Project",
    "demand": "DemandPlan",
    "allocations": "Allocation",
    "availability": "Availability",
    "training": "Training",
    "gaps": "GapAnalysis",
    "policies": "PolicySetting",
}

IMPORT_TABLES = [
    ("roles", "roles", "roles"),
    ("skills", "skills", "skills"),
    ("employees", "employees", "employees"),
    ("projects", "projects", "projects"),
    ("policies", "policy_settings", None),
    ("employee_skills", "employee_skills", "employee_skills"),
    ("demand", "demand_plans", "demand_plans"),
    ("allocations", "allocations", "allocations"),
    ("availability", "availability", "availability"),
    ("training", "training", "training"),
    ("ground_truth", "anomaly_issues", "anomalies"),
    ("gaps", "gap_analysis", "demand_plans"),
]

TRUNCATE_TABLES = [
    "gap_analysis", "anomaly_issues", "training", "allocations", "availability",
    "demand_plans", "employee_skills", "employees", "projects", "skills", "roles",
    "policy_settings",
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Load the existing full dataset into PostgreSQL, or generate a new dataset with --generate."
    )
    parser.add_argument(
        "--generate", action="store_true",
        help="Generate new synthetic data instead of loading the existing generated_data_full CSVs.",
    )
    parser.add_argument(
        "--load-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "generated_data_full",
    )
    parser.add_argument("--employees", type=int)
    parser.add_argument("--skills", type=int)
    parser.add_argument("--projects", type=int)
    parser.add_argument("--months", type=int)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--no-anomalies", action="store_true")
    parser.add_argument("--verify-reproducibility", action="store_true")
    return parser.parse_args()


def parse_value(value: str, column_type: Any) -> Any:
    if value == "":
        return None
    if isinstance(column_type, DateTime):
        return datetime.fromisoformat(value)
    if isinstance(column_type, Date):
        return date.fromisoformat(value)
    if isinstance(column_type, Boolean):
        return value.lower() in {"true", "1", "t", "yes"}
    if isinstance(column_type, (Integer, SmallInteger)):
        return int(value)
    if isinstance(column_type, Float):
        return float(value)
    return value


def csv_records(csv_path: Path, table):
    with csv_path.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            raise ValueError(f"{csv_path.name} is missing its CSV header.")

        source_fields = reader.fieldnames
        if csv_path.stem == "ground_truth":
            source_fields = [
                "id" if name == "case_id" else
                "ground_truth" if name == "expected_label" else name
                for name in source_fields
            ]

        expected_fields = [column.name for column in table.columns]
        if set(source_fields) != set(expected_fields):
            raise ValueError(
                f"{csv_path.name} columns do not match {table.name}: "
                f"expected {expected_fields}, found {source_fields}."
            )

        for source_row in reader:
            if csv_path.stem == "ground_truth":
                source_row["id"] = source_row.pop("case_id")
                source_row["ground_truth"] = source_row.pop("expected_label")
            yield {
                column.name: parse_value(source_row[column.name], column.type)
                for column in table.columns
            }


def load_existing_dataset(data_directory: Path) -> dict[str, Any]:
    from app.database import Base, engine
    from app.services import validate_dataset

    if not engine.url.drivername.startswith("postgresql"):
        raise RuntimeError("The configured DATABASE_URL must point to PostgreSQL.")

    manifest_path = data_directory / "source_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Dataset manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_counts = manifest["counts"]

    files = []
    for file_key, table_name, count_key in IMPORT_TABLES:
        csv_path = data_directory / f"{file_key}.csv"
        if not csv_path.is_file():
            raise FileNotFoundError(f"Required dataset file not found: {csv_path}")
        table = Base.metadata.tables[table_name]
        files.append((csv_path, table, expected_counts.get(count_key) if count_key else None))

    loaded_counts = {}
    try:
        Base.metadata.create_all(bind=engine)
        with engine.begin() as connection:
            quoted_tables = ", ".join(
                connection.dialect.identifier_preparer.quote(table_name)
                for table_name in TRUNCATE_TABLES
            )
            connection.exec_driver_sql(f"TRUNCATE TABLE {quoted_tables} RESTART IDENTITY")

            for csv_path, table, expected_count in files:
                count = 0
                batch = []
                for record in csv_records(csv_path, table):
                    batch.append(record)
                    if len(batch) == 2000:
                        connection.execute(table.insert(), batch)
                        count += len(batch)
                        batch.clear()
                if batch:
                    connection.execute(table.insert(), batch)
                    count += len(batch)
                if expected_count is not None and count != expected_count:
                    raise ValueError(
                        f"{csv_path.name} contains {count} rows; the manifest expects {expected_count}."
                    )
                loaded_counts[table.name] = count

            with Session(bind=connection, join_transaction_mode="rollback_only") as session:
                validation = validate_dataset(session)
                if validation["failed"]:
                    failed = [check for check in validation["checks"] if check["status"] == "FAIL"]
                    raise RuntimeError(f"Loaded dataset failed validation: {failed}")

            audit_table = Base.metadata.tables["audit_events"]
            connection.execute(audit_table.insert().values(
                id=f"EVT-{uuid.uuid4().hex[:12].upper()}",
                event_type="DATA_LOADED",
                entity_type="DATASET",
                entity_id="GENERATED_DATA_FULL",
                details=json.dumps({
                    "seed": manifest["seed"],
                    "source_directory": data_directory.name,
                    "counts": loaded_counts,
                }),
            ))
    finally:
        engine.dispose()

    return {
        "database": engine.url.database,
        "host": engine.url.host,
        "counts": loaded_counts,
        "validation": f"{validation['passed']} passed, {validation['failed']} failed",
    }


def export_rows(output_dir, key, rows, columns=None):
    if key == "ground_truth":
        rows = [{
            "case_id": row["id"],
            "issue_type": row["issue_type"],
            "entity_id": row["entity_id"],
            "expected_label": row["ground_truth"],
            "details": row["details"],
        } for row in rows]
    with (output_dir / f"{key}.csv").open("w", newline="", encoding="utf-8") as handle:
        columns = columns or (list(rows[0]) if rows else [])
        writer = csv.DictWriter(handle, fieldnames=columns)
        if columns:
            writer.writeheader()
            writer.writerows(rows)
    with (output_dir / f"{key}.json").open("w", encoding="utf-8") as handle:
        json.dump(rows, handle, indent=2, default=lambda value: value.isoformat())
        handle.write("\n")


def write_sql_dump(engine, metadata, output_path):
    with engine.connect() as connection, output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for table in metadata.sorted_tables:
            handle.write(f"{CreateTable(table).compile(dialect=engine.dialect)};\n\n")

        for table in metadata.sorted_tables:
            if table.name == "audit_events":
                continue
            statement = select(table).order_by(*table.primary_key.columns)
            for row in connection.execute(statement).mappings():
                insert_statement = insert(table).values(**dict(row))
                handle.write(f"{insert_statement.compile(dialect=engine.dialect, compile_kwargs={'literal_binds': True})};\n")
            handle.write("\n")


def run_generation(args, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)

    from app.database import Base, SessionLocal, engine
    from app import models
    from app.schemas import GenerateRequest
    from app.services import analyze, generate, serialize, validate_dataset

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        config = GenerateRequest(
            employees=args.employees,
            skills=args.skills,
            projects=args.projects,
            months=args.months,
            seed=args.seed,
            inject_anomalies=not args.no_anomalies,
        )
        counts = generate(db, config)
        analyze(db)
        validation = validate_dataset(db)
        (output_dir / "validation_summary.json").write_text(
            json.dumps(validation, indent=2) + "\n", encoding="utf-8"
        )
        if validation["failed"]:
            raise RuntimeError(f"Dataset validation failed: {validation['failed']} check(s) failed.")

        for key, model_name in TABLES.items():
            model = getattr(models, model_name)
            export_rows(output_dir, key, serialize(db.query(model).all()),
                        [column.name for column in model.__table__.columns])
        export_rows(output_dir, "ground_truth", serialize(db.query(models.AnomalyIssue).all()),
                    ["case_id", "issue_type", "entity_id", "expected_label", "details"])

        manifest = {
            "dataset": "synthetic workforce planning data",
            "seed": args.seed,
            "generator_command": "python -m app.generate_dataset",
            "parameters": {
                "employees": args.employees,
                "skills": args.skills,
                "projects": args.projects,
                "months": args.months,
                "inject_anomalies": not args.no_anomalies,
            },
            "counts": counts,
            "ground_truth_is_separate": True,
            "external_sources": [],
            "database": "Configured SQLAlchemy database from DATABASE_URL",
        }
        (output_dir / "source_manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        write_sql_dump(engine, Base.metadata, output_dir / "seed.sql")

        checksums = {}
        for path in sorted(output_dir.iterdir()):
            if path.suffix in {".csv", ".json", ".sql"} and path.name not in {
                "checksums.json", "validation_summary.json", "source_manifest.json"
            }:
                checksums[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        (output_dir / "checksums.json").write_text(
            json.dumps(checksums, indent=2) + "\n", encoding="utf-8"
        )
        return checksums, validation, counts
    finally:
        db.close()
        engine.dispose()


def main():
    args = parse_args()
    generation_requested = args.generate or any([
        args.employees is not None,
        args.skills is not None,
        args.projects is not None,
        args.months is not None,
        args.seed is not None,
        args.no_anomalies,
        args.verify_reproducibility,
    ])
    if not generation_requested:
        print(json.dumps(load_existing_dataset(args.load_dir.resolve()), indent=2))
        return

    args.employees = args.employees if args.employees is not None else 100
    args.skills = args.skills if args.skills is not None else 30
    args.projects = args.projects if args.projects is not None else 10
    args.months = args.months if args.months is not None else 12
    args.seed = args.seed if args.seed is not None else 20261022
    output_dir = (args.output_dir or Path("generated_data_full")).resolve()
    checksums, validation, counts = run_generation(args, output_dir)
    if args.verify_reproducibility:
        with tempfile.TemporaryDirectory(prefix="workforce-repro-") as temp_dir:
            command = [
                sys.executable, "-m", "app.generate_dataset",
                "--employees", str(args.employees),
                "--skills", str(args.skills),
                "--projects", str(args.projects),
                "--months", str(args.months),
                "--seed", str(args.seed),
                "--output-dir", str(Path(temp_dir) / "repeat"),
            ]
            if args.no_anomalies:
                command.append("--no-anomalies")
            backend_directory = Path(__file__).resolve().parents[1]
            subprocess.run(command, check=True, cwd=backend_directory)
            repeated = json.loads((Path(temp_dir) / "repeat" / "checksums.json").read_text(encoding="utf-8"))
            if checksums != repeated:
                raise RuntimeError("Fixed-seed reproducibility check failed: exported CSV/JSON/SQL checksums differ.")

    print(json.dumps({
        "output_dir": str(output_dir),
        "counts": counts,
        "validation": f"{validation['passed']} passed, {validation['failed']} failed",
        "reproducibility": "verified" if args.verify_reproducibility else "not requested",
        "export_files": len(checksums),
    }, indent=2))


if __name__ == "__main__":
    main()
