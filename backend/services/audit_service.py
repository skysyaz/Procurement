"""Write-through audit log helpers."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional


async def write_log(
    db,
    *,
    actor_id: Optional[str],
    actor_email: Optional[str],
    actor_role: Optional[str],
    action: str,
    target_type: str,
    target_id: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    await db.audit_logs.insert_one(
        {
            "id": str(uuid.uuid4()),
            "actor_id": actor_id,
            "actor_email": actor_email,
            "actor_role": actor_role,
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "meta": meta or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
