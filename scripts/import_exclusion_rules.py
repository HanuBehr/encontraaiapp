from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import models  # noqa: F401
from app.db import init_db, session_scope
from app.services.exclusion_rules import ExclusionRuleService


def main() -> None:
    parser = argparse.ArgumentParser(description="Import lead exclusion rules from CSV.")
    parser.add_argument("csv_path", help="CSV with rule_type, pattern, reason, is_active columns.")
    parser.add_argument(
        "--reapply",
        action="store_true",
        help="Reapply all active exclusion rules to existing leads after import.",
    )
    args = parser.parse_args()

    init_db()
    imported = 0
    with session_scope() as db:
        service = ExclusionRuleService(db)
        with Path(args.csv_path).open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {"rule_type", "pattern"}
            missing = required - set(reader.fieldnames or [])
            if missing:
                raise SystemExit(f"Missing required CSV columns: {', '.join(sorted(missing))}")

            for row in reader:
                pattern = (row.get("pattern") or "").strip()
                if not pattern:
                    continue
                is_active = _parse_bool(row.get("is_active"), default=True)
                service.create_rule(
                    rule_type=(row.get("rule_type") or "").strip(),
                    pattern=pattern,
                    reason=(row.get("reason") or "").strip() or None,
                    is_active=is_active,
                )
                imported += 1

        print(f"Imported or updated {imported} exclusion rule(s).")
        if args.reapply:
            summary = service.reapply_all()
            print(
                "Reapplied rules: "
                f"evaluated={summary.evaluated}, "
                f"blocked={summary.blocked}, "
                f"unblocked={summary.unblocked}, "
                f"unchanged={summary.unchanged}."
            )


def _parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "active"}


if __name__ == "__main__":
    main()
