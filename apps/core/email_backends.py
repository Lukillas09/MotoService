import logging
import re
from email.header import decode_header, make_header
from email.utils import parseaddr

from brevo import Brevo
from brevo.transactional_emails import (
    SendTransacEmailRequestBccItem,
    SendTransacEmailRequestCcItem,
    SendTransacEmailRequestReplyTo,
    SendTransacEmailRequestSender,
    SendTransacEmailRequestToItem,
)
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import sanitize_address
from django.core.validators import validate_email


logger = logging.getLogger(__name__)
SAFE_ERROR_METADATA = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")


class BrevoEmailDeliveryError(RuntimeError):
    """A safe public error for failed Brevo deliveries."""

    provider = "brevo"

    def __init__(
        self,
        message,
        *,
        error_class="unknown",
        status_code="unknown",
        provider_code="unknown",
    ):
        super().__init__(message)
        self.error_class = error_class
        self.error_type = error_class
        self.status_code = status_code
        self.provider_code = provider_code


class BrevoEmailMessageError(ValueError):
    """A safe error for Django messages that Brevo cannot represent."""


class BrevoEmailBackend(BaseEmailBackend):
    """Send Django email messages through the Brevo HTTPS API."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._client = None
        self.message_ids = []

    def _get_client(self):
        if self._client is None:
            self._client = Brevo(
                api_key=settings.BREVO_API_KEY,
                timeout=10.0,
            )
        return self._client

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        sent_count = 0

        for message in email_messages:
            try:
                if not message.recipients():
                    continue

                payload = self._build_payload(message)
                response = self._get_client().transactional_emails.send_transac_email(
                    **payload
                )
            except Exception as error:
                if isinstance(
                    error,
                    (NotImplementedError, BrevoEmailMessageError),
                ) and not self.fail_silently:
                    raise

                self._log_delivery_error(error)
                if not self.fail_silently:
                    metadata = self._error_metadata(error)
                    raise BrevoEmailDeliveryError(
                        "Email delivery through Brevo failed.",
                        **metadata,
                    ) from None
            else:
                sent_count += 1
                message_id = getattr(response, "message_id", None)
                if message_id:
                    self.message_ids.append(str(message_id))

        return sent_count

    @classmethod
    def _log_delivery_error(cls, error):
        metadata = cls._error_metadata(error)
        logger.warning(
            "Email delivery failed "
            "(provider=brevo, error_class=%s, status_code=%s, provider_code=%s).",
            metadata["error_class"],
            metadata["status_code"],
            metadata["provider_code"],
        )

    @classmethod
    def _error_metadata(cls, error):
        provider_code = getattr(error, "code", None)
        if provider_code is None:
            body = getattr(error, "body", None)
            if isinstance(body, dict):
                provider_code = body.get("code")
            elif body is not None:
                provider_code = getattr(body, "code", None)

        return {
            "error_class": cls._safe_error_metadata(type(error).__name__),
            "status_code": cls._safe_error_metadata(
                getattr(error, "status_code", None)
            ),
            "provider_code": cls._safe_error_metadata(provider_code),
        }

    @staticmethod
    def _safe_error_metadata(value):
        text = str(value) if value is not None else "unknown"
        if not SAFE_ERROR_METADATA.fullmatch(text):
            return "unknown"
        return text

    @classmethod
    def _build_payload(cls, message):
        if message.attachments:
            raise NotImplementedError(
                "Attachments are not supported by BrevoEmailBackend."
            )

        to = cls._build_recipients(
            message.to,
            SendTransacEmailRequestToItem,
        )
        if not to:
            raise BrevoEmailMessageError(
                "Brevo requires at least one primary recipient in 'to'."
            )

        subject = str(message.subject or "")
        if "\r" in subject or "\n" in subject:
            raise BrevoEmailMessageError("Brevo cannot represent this email subject.")

        payload = {
            "sender": cls._build_sender(),
            "to": to,
            "subject": subject,
        }

        cls._add_content(
            payload,
            message.content_subtype,
            message.body,
        )

        for content, mimetype in getattr(message, "alternatives", ()):
            cls._add_content(
                payload,
                mimetype,
                content,
            )

        cc = cls._build_recipients(
            message.cc,
            SendTransacEmailRequestCcItem,
        )
        if cc:
            payload["cc"] = cc

        bcc = cls._build_recipients(
            message.bcc,
            SendTransacEmailRequestBccItem,
        )
        if bcc:
            payload["bcc"] = bcc

        reply_to = [address for address in message.reply_to if address]
        if len(reply_to) > 1:
            raise BrevoEmailMessageError(
                "BrevoEmailBackend supports at most one reply-to address."
            )
        if reply_to:
            name, email = cls._parse_address(reply_to[0])
            payload["reply_to"] = SendTransacEmailRequestReplyTo(
                email=email,
                name=name or None,
            )

        return payload

    @classmethod
    def _build_sender(cls):
        name = settings.BREVO_FROM_NAME
        if "\r" in name or "\n" in name:
            raise BrevoEmailMessageError("Brevo cannot represent this sender name.")
        cls._validate_email(settings.BREVO_FROM_EMAIL)
        return SendTransacEmailRequestSender(
            email=settings.BREVO_FROM_EMAIL,
            name=name,
        )

    @classmethod
    def _build_recipients(cls, addresses, recipient_class):
        recipients = []
        for address in addresses:
            if not address:
                continue
            name, email = cls._parse_address(address)
            recipients.append(
                recipient_class(
                    email=email,
                    name=name or None,
                )
            )
        return recipients

    @classmethod
    def _parse_address(cls, address):
        text = str(address).strip()
        if "\r" in text or "\n" in text:
            raise BrevoEmailMessageError("Brevo cannot represent this email address.")
        try:
            sanitized = sanitize_address(address, "utf-8")
        except ValueError:
            raise BrevoEmailMessageError(
                "Brevo cannot represent this email address."
            ) from None
        name, email = parseaddr(sanitized)
        try:
            name = str(make_header(decode_header(name)))
        except (LookupError, UnicodeError):
            raise BrevoEmailMessageError(
                "Brevo cannot represent this recipient name."
            ) from None
        cls._validate_email(email)
        if len(name) > 70:
            raise BrevoEmailMessageError("Brevo cannot represent this recipient name.")
        return name, email

    @staticmethod
    def _validate_email(email):
        try:
            validate_email(email)
        except ValidationError:
            raise BrevoEmailMessageError(
                "Brevo cannot represent this email address."
            ) from None

    @staticmethod
    def _add_content(payload, mimetype, content):
        normalized_mimetype = str(mimetype or "plain").lower()
        if "/" not in normalized_mimetype:
            normalized_mimetype = f"text/{normalized_mimetype}"

        content_keys = {
            "text/plain": "text_content",
            "text/html": "html_content",
        }
        key = content_keys.get(normalized_mimetype)
        if key is None:
            raise BrevoEmailMessageError(
                "BrevoEmailBackend supports only text/plain and text/html content."
            )
        if key in payload:
            raise BrevoEmailMessageError(
                "BrevoEmailBackend supports at most one body per content type."
            )
        payload[key] = str(content or "")
