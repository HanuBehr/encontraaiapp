from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import models  # noqa: F401
from app.db import SessionLocal, init_db
from app.repositories.organization_repository import (
    OrganizationRepository,
    get_or_create_default_organization,
)
from app.services.lead_assignment import LeadAssignmentService


def main() -> None:
    parser = argparse.ArgumentParser(description="Run lead assignment for a tenant scope.")
    parser.add_argument(
        "--organization-slug",
        default=None,
        help="Organization slug to scope leads. Defaults to the current default organization.",
    )
    parser.add_argument("--lead-id", action="append", type=int, default=[], help="Lead id to process. Repeatable.")
    parser.add_argument("--lead-ids", default=None, help="Comma-separated lead ids to process.")
    parser.add_argument("--all", action="store_true", help="Process all leads in the organization scope.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing assignment/classification fields.")
    parser.add_argument("--commit", action="store_true", help="Persist changes. Without this flag the run is a dry run.")
    args = parser.parse_args()

    lead_ids = _parse_lead_ids(args.lead_id, args.lead_ids)
    if not lead_ids and not args.all:
        parser.error("Pass --all or at least one --lead-id/--lead-ids value.")
    if lead_ids and args.all:
        parser.error("Use either selected lead ids or --all, not both.")

    init_db()
    db = SessionLocal()
    try:
        organization = _resolve_organization(db, args.organization_slug)
        service = LeadAssignmentService(db, organization_id=organization.id)
        result = service.apply_batch(
            lead_ids=lead_ids if lead_ids else None,
            overwrite=args.overwrite,
            dry_run=not args.commit,
        )
        if args.commit:
            db.commit()
        else:
            db.rollback()

        mode = "committed" if args.commit else "dry-run"
        print(f"Lead assignment {mode} for organization '{organization.slug}' (id={organization.id}).")
        print(f"Processed: {result.processed}")
        print(f"Would change: {result.changed}" if result.dry_run else f"Changed: {result.changed}")
        for item in result.results:
            if not item.changed_fields:
                continue
            fields = ", ".join(item.changed_fields)
            suggestion = item.suggestion
            print(
                "Lead "
                f"{item.lead_id}: {fields} "
                f"(region_id={suggestion.sales_region_id}, "
                f"segment_id={suggestion.market_segment_id}, "
                f"subsegment_id={suggestion.market_subsegment_id}, "
                f"rep_id={suggestion.assigned_sales_rep_id})"
            )
    finally:
        db.close()


def _resolve_organization(db, organization_slug: str | None):
    if not organization_slug:
        return get_or_create_default_organization(db)

    organization = OrganizationRepository(db).get_by_slug(organization_slug)
    if organization is None:
        raise SystemExit(f"Organization slug '{organization_slug}' was not found. Run bootstrap first.")
    return organization


def _parse_lead_ids(repeated_ids: list[int], csv_ids: str | None) -> list[int]:
    values = list(repeated_ids)
    if csv_ids:
        values.extend(int(value.strip()) for value in csv_ids.split(",") if value.strip())
    return list(dict.fromkeys(values))


if __name__ == "__main__":
    main()
