"""Email notification channel — sends HTML email via aiosmtplib.

Uses SMTP with STARTTLS.  Config dict keys:
    smtp_host, smtp_port (default 587), smtp_user, smtp_pass,
    from_name (default 'Ambient AI'), to_email.
"""

from __future__ import annotations

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

logger = logging.getLogger(__name__)

_SEVERITY_EMOJI = {
    "critical": "🚨",
    "important": "⚠️",
    "info": "ℹ️",
}


class EmailChannel:
    """Sends notification events as HTML emails."""

    @staticmethod
    def _severity_emoji(severity: str) -> str:
        return _SEVERITY_EMOJI.get(severity.lower(), "📬")

    async def send(
        self,
        config: dict[str, Any],
        subject: str,
        body: str,
        severity: str,
    ) -> bool:
        """Send an HTML email via SMTP.

        Args:
            config: SMTP connection config.
            subject: Email subject line.
            body: HTML body content.
            severity: Event severity for emoji prefix.

        Returns:
            True on success, False on failure.
        """
        try:
            import aiosmtplib
        except ImportError:
            logger.error("aiosmtplib not installed — cannot send email")
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"{self._severity_emoji(severity)} {subject}"
        msg["From"] = config.get("from_name", "Ambient AI")
        msg["To"] = config["to_email"]
        msg.attach(MIMEText(body, "html"))

        try:
            await aiosmtplib.send(
                msg,
                hostname=config["smtp_host"],
                port=config.get("smtp_port", 587),
                username=config.get("smtp_user"),
                password=config.get("smtp_pass"),
                start_tls=True,
            )
            return True
        except Exception as e:
            logger.error("Email send failed: %s", e)
            return False
