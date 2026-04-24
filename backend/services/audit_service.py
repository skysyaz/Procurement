"""Write-through audit log helper."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class AuditEvent:
    """Structured audit event. Group-related params -> single object."""
    action: str
    target_type: str
    actor_id: Optional[str] = None
    actor_email: Optional[str] = None
    actor_role: Optional[str] = None
    target_id: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)


async def write_log(db, event: AuditEvent) -> None:
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "actor_id": event.actor_id,
        "actor_email": event.actor_email,
        "actor_role": event.actor_role,
        "action": event.action,
        "target_type": event.target_type,
        "target_id": event.target_id,
        "meta": event.meta or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    })


async def log_from_user(
    db,
    user: Dict[str, Any],
    *,
    action: str,
    target_type: str,
    target_id: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    """Convenience wrapper: populate actor_* fields from an authenticated user dict."""
    await write_log(db, AuditEvent(
        actor_id=user.get("id") if user else None,
        actor_email=user.get("email") if user else None,
        actor_role=user.get("role") if user else None,
        action=action,
        target_type=target_type,
        target_id=target_id,
        meta=meta or {},
    ))
