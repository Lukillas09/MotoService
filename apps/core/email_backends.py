import logging

import resend
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend


logger = logging.getLogger(__name__)

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
                if not self.fail_silently:
                    if isinstance(
                        error,
                        (NotImplementedError, ResendEmailMessageError),
                    ):
                        raise
                    raise ResendEmailDeliveryError(
                        "Email delivery through Resend failed."
                    ) from None
                logger.warning(
                    "Resend email delivery failed (%s).",
                    type(error).__name__,
                )
            else:
                sent_count += 1

        return sent_count

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
