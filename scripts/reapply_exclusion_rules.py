from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import models  # noqa: F401
from app.db import init_db, session_scope
from app.services.exclusion_rules import ExclusionRuleService


if __name__ == "__main__":
    init_db()
    with session_scope() as db:
        summary = ExclusionRuleService(db).reapply_all()
        print(
            "Reapplied exclusion rules: "
            f"evaluated={summary.evaluated}, "
            f"blocked={summary.blocked}, "
            f"unblocked={summary.unblocked}, "
            f"unchanged={summary.unchanged}."
        )
