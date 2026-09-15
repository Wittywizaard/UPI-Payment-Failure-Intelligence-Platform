"""
Audit logging helper (PRD Section 13: "Every major change should generate an
audit log."). Real authentication/RBAC lands in Phase 5; until then, the
actor is passed explicitly by callers (defaulting to 'system') via the
X-Actor header on write endpoints, rather than silently omitted, so the
audit trail's shape is correct from day one and only the identity source
changes later.
"""

import json

from sqlalchemy import text
from sqlalchemy.orm import Session


def log_action(db: Session, action: str, entity_type: str, entity_id: str,
                actor: str | None = None, metadata: dict | None = None) -> None:
    payload = {"actor": actor or "system", **(metadata or {})}
    db.execute(
        text("""
            INSERT INTO audit_logs (user_id, action, entity_type, entity_id, metadata_json, timestamp)
            VALUES (NULL, :action, :entity_type, :entity_id, CAST(:metadata AS JSONB), now())
        """),
        {
            "action": action,
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "metadata": json.dumps(payload, default=str),
        },
    )
