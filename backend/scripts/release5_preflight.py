"""Read-only Release 5 migration preflight with deterministic JSON output."""
from __future__ import annotations

import json
from sqlalchemy import text

from app.db import engine


CHECKS = {
    "invalid_category_applications": "SELECT id, workspace FROM categories WHERE upper(workspace) NOT IN ('LIGHTING','AUTOMATION')",
    "invalid_product_applications": "SELECT id, workspace FROM products WHERE upper(workspace) NOT IN ('LIGHTING','AUTOMATION')",
    "invalid_inquiry_applications": "SELECT id, workspace FROM inquiries WHERE upper(workspace) NOT IN ('LIGHTING','AUTOMATION')",
    "duplicate_category_siblings": """
        SELECT workspace, COALESCE(parent_id, '') AS parent_id, lower(name) AS normalized_name, count(*) AS count
        FROM categories GROUP BY workspace, COALESCE(parent_id, ''), lower(name) HAVING count(*) > 1
    """,
    "mixed_application_inquiries": """
        SELECT rr.inquiry_id, count(DISTINCT p.workspace) AS application_count
        FROM room_requirements rr JOIN products p ON p.id = rr.product_id
        GROUP BY rr.inquiry_id HAVING count(DISTINCT p.workspace) > 1
    """,
    "orphan_product_media": """
        SELECT pm.id, pm.storage_key FROM product_media pm
        LEFT JOIN products p ON p.id = pm.product_id
        LEFT JOIN product_families pf ON pf.id = pm.product_family_id
        WHERE p.id IS NULL AND pf.id IS NULL
    """,
}


def main() -> int:
    report: dict[str, list[dict]] = {}
    with engine.connect() as connection:
        for name, query in CHECKS.items():
            report[name] = [dict(row._mapping) for row in connection.execute(text(query))]
    issues = sum(len(rows) for rows in report.values())
    print(json.dumps({"status": "pass" if issues == 0 else "review_required", "issue_count": issues, "checks": report}, indent=2, default=str))
    return 0 if issues == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
