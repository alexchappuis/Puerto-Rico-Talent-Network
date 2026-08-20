"""
website/email_backend.py

Django email backend that sends through Resend's HTTP API instead of SMTP.

Why: SMTP needs port 587 outbound, which many hosting providers block
(the symptom is "[Errno 101] Network is unreachable"). This uses HTTPS
on 443, which is never blocked.

Nothing else in the project changes — send_mail() and
EmailMultiAlternatives() work exactly as before.
"""

import base64
import logging

import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

RESEND_ENDPOINT = "https://api.resend.com/emails"


class ResendBackend(BaseEmailBackend):

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_key = getattr(settings, 'RESEND_API_KEY', '')

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        if not self.api_key:
            if not self.fail_silently:
                raise ValueError("RESEND_API_KEY is not set")
            return 0

        sent = 0
        for message in email_messages:
            if self._send(message):
                sent += 1
        return sent

    def _send(self, message):
        payload = {
            'from': message.from_email,
            'to': list(message.to),
            'subject': message.subject,
            'text': message.body,
        }

        if message.cc:
            payload['cc'] = list(message.cc)
        if message.bcc:
            payload['bcc'] = list(message.bcc)
        if message.reply_to:
            payload['reply_to'] = list(message.reply_to)

        # HTML alternative, if one was attached
        for content, mimetype in getattr(message, 'alternatives', []):
            if mimetype == 'text/html':
                payload['html'] = content
                break

        # Extra headers (List-Unsubscribe, etc.)
        headers = {
            k: v for k, v in (message.extra_headers or {}).items()
            if k.lower() not in ('from', 'to', 'subject')
        }
        if headers:
            payload['headers'] = headers

        # Attachments — the .ics calendar file
        attachments = []
        for attachment in message.attachments:
            if isinstance(attachment, tuple):
                filename, content, _mimetype = attachment
            else:
                continue
            if isinstance(content, str):
                content = content.encode('utf-8')
            attachments.append({
                'filename': filename,
                'content': base64.b64encode(content).decode('ascii'),
            })
        if attachments:
            payload['attachments'] = attachments

        try:
            response = requests.post(
                RESEND_ENDPOINT,
                json=payload,
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json',
                },
                timeout=15,
            )
            if response.status_code >= 400:
                raise RuntimeError(
                    f"Resend returned {response.status_code}: {response.text}")
            return True

        except Exception:
            logger.exception("Resend send failed for %s", message.to)
            if not self.fail_silently:
                raise
            return False