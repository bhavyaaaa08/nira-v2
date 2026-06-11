from __future__ import annotations

from typing import Any

import requests
import json

from app.core.config import settings
from app.services.audit_logger import audit_logger


class AutomationClient:
    """
    Outbound automation client for NIRA.

    Sends operational events to n8n or other workflow tools.
    """

    def trigger_ticket_created(self, payload: dict[str, Any]) -> None:
        if not settings.n8n_enabled:
            return

        webhook_url = settings.n8n_ticket_webhook_url

        if not webhook_url:
            audit_logger.log_event(
                session_id=payload.get("session_id"),
                event_type="n8n_ticket_webhook_missing",
                source="automation_client",
                payload=payload,
            )
            return
        

        safe_payload = json.loads(
            json.dumps(
                {
                    "event_type": "ticket_created",
                    **payload,
                },
                default=str,
            )
        )

        try:
            response = requests.post(
                webhook_url,
                json=safe_payload,
                timeout=settings.n8n_timeout_seconds,
            )
            response.raise_for_status()

            audit_logger.log_event(
                session_id=payload.get("session_id"),
                event_type="n8n_ticket_webhook_sent",
                source="automation_client",
                payload={
                    "ticket_id": payload.get("ticket_id"),
                    "status_code": response.status_code,
                },
            )

        except requests.RequestException as exc:
            audit_logger.log_event(
                session_id=payload.get("session_id"),
                event_type="n8n_ticket_webhook_failed",
                source="automation_client",
                payload={
                    "ticket_id": payload.get("ticket_id"),
                    "error": str(exc),
                },
            )


automation_client = AutomationClient()