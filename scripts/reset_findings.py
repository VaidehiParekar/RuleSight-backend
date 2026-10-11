"""Empties the database so everything shown in the app comes from real uploads and agent runs.

Removes all documents (and their stored files), controls, evidence, every finding derived from
them (obligations, mappings, assessments, gaps, remediations, changes, missing circulars),
pipeline runs, the audit log and the last accuracy report. Keeps user accounts only.

Afterwards, in the app: upload the bank's control matrix (doc type "rcm") and evidence CSVs,
then the RBI regulations, and run the pipeline.

Usage:  uv run python -m scripts.reset_findings --yes
"""

from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import create_engine, text

from app.core.config import get_settings

# Foreign keys cascade from documents and obligations; the explicit order keeps counts readable.
STATEMENTS = (
    "DELETE FROM remediations",
    "DELETE FROM gaps",
    "DELETE FROM assessments",
    "DELETE FROM mappings",
    "DELETE FROM obligations",
    "DELETE FROM changes",
    "DELETE FROM missing_circulars",
    "DELETE FROM chunks",
    "DELETE FROM documents",
    "DELETE FROM controls",
    "DELETE FROM evidence",
    "DELETE FROM agent_runs",
    "DELETE FROM audit_log",
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true", help="confirm the deletion")
    args = parser.parse_args()
    if not args.yes:
        raise SystemExit("This deletes all data except user accounts. Re-run with --yes.")

    settings = get_settings()
    storage = settings.storage_dir.resolve()
    engine = create_engine(settings.database_url.get_secret_value())
    with engine.begin() as conn:
        files = [
            Path(row[0])
            for row in conn.execute(
                text("SELECT file_path FROM documents WHERE file_path IS NOT NULL")
            )
        ]
        for statement in STATEMENTS:
            print(f"{conn.execute(text(statement)).rowcount:5}  {statement}")
        users = conn.execute(text("SELECT count(*) FROM users")).scalar_one()
    engine.dispose()

    removed = 0
    for path in files:
        # Only files inside the configured storage folder are ever deleted.
        if path.resolve().parent == storage and path.is_file():
            path.unlink()
            removed += 1
    print(f"Removed {removed} stored document files from {storage}")
    if settings.eval_report_path is not None and settings.eval_report_path.is_file():
        settings.eval_report_path.unlink()
        print(f"Removed old accuracy report {settings.eval_report_path}")
    print(f"Kept {users} user accounts.")


if __name__ == "__main__":
    main()
