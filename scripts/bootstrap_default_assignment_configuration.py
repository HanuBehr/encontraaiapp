from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import models  # noqa: F401
from app.db import init_db, session_scope
from app.services.default_assignment_bootstrap import bootstrap_default_assignment_configuration


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the default assignment configuration for an organization.")
    parser.add_argument(
        "--organization-slug",
        default=None,
        help="Organization slug to seed. Defaults to the current default organization.",
    )
    args = parser.parse_args()

    init_db()
    with session_scope() as db:
        result = bootstrap_default_assignment_configuration(db, organization_slug=args.organization_slug)

    print(f"Default assignment bootstrap complete for organization '{result.organization_slug}' (id={result.organization_id}).")
    print(f"Sales reps: {result.sales_reps}")
    print(f"Sales regions: {result.sales_regions}")
    print(f"Market segments: {result.market_segments}")
    print(f"Market subsegments: {result.market_subsegments}")
    print(f"Assignment rules: {result.assignment_rules}")
    for warning in result.warnings:
        print(f"WARNING: {warning}")


if __name__ == "__main__":
    main()
