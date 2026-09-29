import logging
import re

import resend
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend


logger = logging.getLogger(__name__)
SAFE_ERROR_METADATA = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")

# The official Python SDK exposes process-wide configuration. MotoService uses
# one fixed API key per process, so configure it once when this backend loads.
resend.api_key = settings.RESEND_API_KEY
resend.default_http_client = resend.RequestsClient(timeout=10)


class ResendEmailDeliveryError(RuntimeError):
    """A safe public error for failed Resend deliveries."""


class ResendEmailMessageError(ValueError):
    """A safe error for Django messages that Resend cannot represent."""


class ResendEmailBackend(BaseEmailBackend):
    """Send Django email messages through the Resend HTTPS API."""

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        sent_count = 0

        for message in email_messages:
            try:
                if not message.recipients():
                    continue

                payload = self._build_payload(message)
                resend.Emails.send(payload)
            except Exception as error:
                if isinstance(
                    error,
                    (NotImplementedError, ResendEmailMessageError),
                ) and not self.fail_silently:
                    raise

                self._log_delivery_error(error)
                if not self.fail_silently:
                    raise ResendEmailDeliveryError(
                        "Email delivery through Resend failed."
                    ) from None
            else:
                sent_count += 1

        return sent_count

    @staticmethod
    def _log_delivery_error(error):
        logger.warning(
            "Resend email delivery failed "
            "(exception=%s, error_type=%s, code=%s).",
            ResendEmailBackend._safe_error_metadata(type(error).__name__),
            ResendEmailBackend._safe_error_metadata(
                getattr(error, "error_type", None)
            ),
            ResendEmailBackend._safe_error_metadata(getattr(error, "code", None)),
        )

    @staticmethod
    def _safe_error_metadata(value):
        text = str(value) if value is not None else "unknown"
        if not SAFE_ERROR_METADATA.fullmatch(text):
            return "unknown"
        return text

    @staticmethod
    def _build_payload(message):
        if message.attachments:
            raise NotImplementedError(
                "Attachments are not supported by ResendEmailBackend."
            )

        to = [address for address in message.to if address]
        if not to:
            raise ResendEmailMessageError(
                "Resend requires at least one primary recipient in 'to'."
            )

        payload = {
            "from": settings.RESEND_FROM_EMAIL,
            "to": to,
            "subject": str(message.subject or ""),
        }

        if message.content_subtype == "html":
            payload["html"] = message.body
        else:
            payload["text"] = message.body

        for alternative in getattr(message, "alternatives", ()):
            if alternative.mimetype.lower() == "text/html":
                payload["html"] = alternative.content

        cc = [address for address in message.cc if address]
        if cc:
            payload["cc"] = cc

        bcc = [address for address in message.bcc if address]
        if bcc:
            payload["bcc"] = bcc

        reply_to = [address for address in message.reply_to if address]
        if reply_to:
            payload["reply_to"] = reply_to

        return payload
