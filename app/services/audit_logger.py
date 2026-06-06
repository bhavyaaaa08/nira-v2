from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import settings


def _json_default(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()

    if hasattr(value, "value"):
        return value.value

    if isinstance(value, datetime):
        return value.isoformat()

    return str(value)


class AuditLogger:
    """
    Lightweight JSONL audit logger for NIRA.

    This is frontend-independent and useful for:
    - compliance review
    - debugging
    - demo analytics
    - later React dashboard backend
    - production-style call trace export
    """

    def __init__(self, log_dir: str = "audit_logs") -> None:
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def log_event(
        self,
        session_id: str | None,
        event_type: str,
        source: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        record = {
            "timestamp": datetime.now().isoformat(),
            "app": settings.app_name,
            "env": settings.env,
            "session_id": session_id,
            "event_type": event_type,
            "source": source,
            "payload": payload or {},
        }

        file_path = self.log_dir / f"nira_audit_{datetime.now().date().isoformat()}.jsonl"

        try:
            with file_path.open("a", encoding="utf-8") as file:
                file.write(
                    json.dumps(
                        record,
                        ensure_ascii=False,
                        default=_json_default,
                    )
                    + "\n"
                )
        except Exception as exc:
            if settings.env == "development":
                print(f"[AuditLogger error] {type(exc).__name__}: {exc}")


audit_logger = AuditLogger()