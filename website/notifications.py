"""
website/notifications.py

Two kinds of email to event registrants:

  invite    — full details plus a Google Calendar link and .ics attachment
  reminder  — a short nudge before the event

Both are sent manually from the Django admin. Every send is recorded in
EmailLog so Carmen can see who has already received what.
"""

import logging
import uuid
from urllib.parse import urlencode
from datetime import timezone as dt_timezone
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone
from django.utils.html import escape
from datetime import timedelta, timezone as dt_timezone

from .models import EmailLog

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Event helpers
# --------------------------------------------------------------------------

def _utc(dt):
    return dt.astimezone(dt_timezone.utc).strftime('%Y%m%dT%H%M%SZ')


def _end(event):
    minutes = getattr(event, 'duration_minutes', 120)
    return event.starts_at + timedelta(minutes=minutes)


def when_text(event):
    if event.time_display:
        return f"{event.local_start:%A, %B %-d} · {event.time_display}"
    return (f"{event.local_start:%A, %B %-d} at "
            f"{event.local_start:%-I:%M %p} {event.tz_abbr}")


def where_text(event):
    if event.venue:
        return event.venue
    address = getattr(event, 'address', '')
    if address:
        return address
    if event.region:
        return f"{event.city}, {event.region}"
    return event.city


def google_calendar_url(event):
    """One-click 'Add to Google Calendar' link."""
    params = {
        'action': 'TEMPLATE',
        'text': f'Puerto Rico Talent Network — {event.title}',
        'dates': f'{_utc(event.starts_at)}/{_utc(_end(event))}',
        'details': event.description or event.subtitle,
        'location': getattr(event, 'address', '') or where_text(event),
        'trp': 'false',
    }
    return 'https://calendar.google.com/calendar/render?' + urlencode(params)


def build_ics(event):
    """iCalendar file for Apple Calendar, Outlook, and anything non-Google."""
    location = getattr(event, 'address', '') or where_text(event)
    description = (event.description or event.subtitle).replace('\n', '\\n')

    lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//Puerto Rico Talent Network//Events//EN',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        'BEGIN:VEVENT',
        f'UID:prtn-{uuid.uuid5(uuid.NAMESPACE_URL, event.slug)}',
        f'DTSTAMP:{_utc(timezone.now())}',
        f'DTSTART:{_utc(event.starts_at)}',
        f'DTEND:{_utc(_end(event))}',
        f'SUMMARY:PRTN — {event.title}',
        f'DESCRIPTION:{description}',
        f'LOCATION:{location}',
        f'ORGANIZER;CN=Puerto Rico Talent Network:mailto:{settings.NOTIFICATION_EMAIL}',
        'STATUS:CONFIRMED',
        'BEGIN:VALARM',
        'TRIGGER:-PT1H',
        'ACTION:DISPLAY',
        'DESCRIPTION:Reminder',
        'END:VALARM',
        'END:VEVENT',
        'END:VCALENDAR',
    ]
    return '\r\n'.join(lines)


# --------------------------------------------------------------------------
# Defaults — prefilled in the admin, editable before every send
# --------------------------------------------------------------------------

DEFAULTS = {
    'invite': {
        'subject': "You're registered — {title}",
        'body': (
            "Thanks for registering. We're glad you'll be joining us.\n\n"
            "Full details are below, and you can add the event to your "
            "calendar with one click."
        ),
    },
    'reminder': {
        'subject': "Reminder — {title}",
        'body': (
            "A quick reminder about our upcoming event. We're looking "
            "forward to seeing you there."
        ),
    },
}


def default_subject(event, kind):
    return DEFAULTS[kind]['subject'].format(title=event.title)


def default_body(kind):
    return DEFAULTS[kind]['body']


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

def render_message(event, kind, body, first_name=''):
    """Return (plain_text, html) for one recipient."""
    greeting = f"Hi {first_name}," if first_name else "Hi,"
    when = when_text(event)
    where = where_text(event)
    address = getattr(event, 'address', '')
    cal_url = google_calendar_url(event)

    # --- plain text ---
    parts = [greeting, "", body, "", event.title, when, where]
    if address and address != where:
        parts.append(address)
    parts += ["", f"Add to Google Calendar: {cal_url}", "",
              "— Puerto Rico Talent Network"]
    text = "\n".join(parts)

    # --- html ---
    address_html = (
        f'<div style="color:#6B7280;font-size:14px;">{escape(address)}</div>'
        if address and address != where else ''
    )
    body_html = escape(body).replace('\n', '<br>')

    html = f"""\
<div style="font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;
            max-width:520px;margin:0 auto;padding:32px 24px;color:#1F2937;">

  <p style="font-size:15px;margin-top:0;">{escape(greeting)}</p>

  <p style="font-size:15px;color:#374151;line-height:1.65;">{body_html}</p>

  <div style="border-left:3px solid #C8102E;padding:6px 0 6px 16px;margin:26px 0;">
    <div style="font-size:19px;font-weight:600;color:#0A3459;">{escape(event.title)}</div>
    <div style="font-size:15px;color:#374151;margin-top:6px;">{escape(when)}</div>
    <div style="font-size:15px;color:#374151;">{escape(where)}</div>
    {address_html}
  </div>

  <a href="{cal_url}"
     style="display:inline-block;background:#0F4C81;color:#ffffff;
            text-decoration:none;font-size:14px;font-weight:600;
            padding:11px 22px;border-radius:6px;">Add to Google Calendar</a>

  <p style="font-size:12px;color:#9CA3AF;margin-top:10px;">
    Not using Google Calendar? A calendar file is attached to this email.
  </p>

  <p style="font-size:13px;color:#9CA3AF;border-top:1px solid #E5E7EB;
            padding-top:16px;margin-top:30px;">
    Puerto Rico Talent Network
  </p>
</div>"""

    return text, html


# --------------------------------------------------------------------------
# Sending
# --------------------------------------------------------------------------

def send_to_registration(registration, kind, subject, body):
    """
    Send one email and log it. Returns True on success.

    No duplicate guard here — the admin decides whether to skip people who
    already received this kind. Manual sends stay under Carmen's control.
    """
    if not registration.email:
        return False

    event = registration.event

    try:
        text, html = render_message(event, kind, body, registration.first_name)

        message = EmailMultiAlternatives(
            subject=subject,
            body=text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[registration.email],
        )
        message.attach_alternative(html, "text/html")

        if kind == 'invite':
            message.attach(
                f'{event.slug}.ics', build_ics(event), 'text/calendar')

        message.send(fail_silently=False)

        EmailLog.objects.create(
            registration=registration, kind=kind, subject=subject)
        return True

    except Exception as exc:
        logger.exception("Email failed: reg=%s kind=%s", registration.pk, kind)
        EmailLog.objects.create(
            registration=registration, kind=kind, subject=subject,
            succeeded=False, error=str(exc)[:500])
        return False


def send_blast(registrations, kind, subject, body):
    """Send to many registrations. Returns (sent, failed)."""
    sent = failed = 0
    for reg in registrations:
        if send_to_registration(reg, kind, subject, body):
            sent += 1
        else:
            failed += 1
    return sent, failed