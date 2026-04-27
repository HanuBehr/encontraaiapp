from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import models  # noqa: F401
from app.db import SessionLocal, init_db
from app.services.lead_assignment_validation import AssignmentValidationService


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate organization lead assignment/classification results.")
    parser.add_argument(
        "--organization-slug",
        default=None,
        help="Organization slug to validate. Defaults to the organization that owns the current leads.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate projected assignment results without mutating leads.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="When used with --dry-run, project overwrite=True assignment behavior.",
    )
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="Idempotently seed the default assignment configuration before validating.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/exports",
        help="Directory for JSON/CSV validation artifacts.",
    )
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    try:
        service = AssignmentValidationService(db)
        report = service.build_report(
            organization_slug=args.organization_slug,
            dry_run=args.dry_run,
            overwrite=args.overwrite,
            bootstrap=args.bootstrap,
        )
        service.write_artifacts(report, Path(args.output_dir))
        if args.dry_run:
            db.rollback()
        print(service.console_summary(report))
    finally:
        db.close()


if __name__ == "__main__":
    main()
