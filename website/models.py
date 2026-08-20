from zoneinfo import ZoneInfo

from django.db import models
from django.utils import timezone

INTAKE_STATUS = [
    ('new', 'New — needs review'),
    ('promoted', 'Promoted to new candidate'),
    ('merged', 'Merged into existing candidate'),
    ('rejected', 'Rejected'),
]

TIMEZONES = [
    ('America/Puerto_Rico', 'Puerto Rico (AST)'),
    ('America/New_York', 'Eastern (ET)'),
    ('America/Chicago', 'Central (CT)'),
    ('America/Denver', 'Mountain (MT)'),
    ('America/Los_Angeles', 'Pacific (PT)'),
]


class ProfessionalSubmission(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    linkedin = models.URLField(blank=True)
    location = models.CharField(max_length=150, blank=True)
    field = models.CharField(max_length=50, blank=True)
    message = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    candidate = models.ForeignKey(
        'talent.Candidate', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='submissions',
        help_text="Set automatically when you promote or merge this signup.",
    )
    status = models.CharField(max_length=20, choices=INTAKE_STATUS, default='new')
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-submitted_at']
        verbose_name = 'Professional Submission'
        verbose_name_plural = 'Professional Submissions'

    def __str__(self):
        return f"{self.first_name} {self.last_name} — {self.email}"


class CompanySubmission(models.Model):
    company_name = models.CharField(max_length=200)
    website = models.URLField(blank=True)
    contact_name = models.CharField(max_length=100)
    title = models.CharField(max_length=100, blank=True)
    email = models.EmailField()
    industry = models.CharField(max_length=50, blank=True)
    size = models.CharField(max_length=20, blank=True)
    hiring_needs = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-submitted_at']
        verbose_name = 'Company Submission'
        verbose_name_plural = 'Company Submissions'

    def __str__(self):
        return f"{self.company_name} — {self.contact_name}"


class Event(models.Model):
    title = models.CharField(max_length=200, help_text="e.g. 'Palo Alto, CA'")
    slug = models.SlugField(
        unique=True,
        help_text="URL fragment AND image filename. A matching file must exist "
                  "at static/images/<slug>.jpg",
    )
    subtitle = models.CharField(
        max_length=200, blank=True,
        default="An evening to network & connect",
    )
    description = models.TextField(blank=True)

    starts_at = models.DateTimeField()
    timezone_name = models.CharField(
        max_length=50,
        choices=TIMEZONES,
        default='America/Puerto_Rico',
        verbose_name='Event timezone',
        help_text="Where the event happens. Enter the start time as local "
                  "clock time — 6:00 PM with Pacific selected means 6pm in "
                  "California.",
    )
    time_display = models.CharField(
        max_length=100, blank=True,
        help_text="Leave blank to show the time from starts_at. "
                  "Set to 'Time coming soon' while TBD.",
    )
    duration_minutes = models.PositiveSmallIntegerField(
        default=120, help_text="Used to set the end time on calendar invites.")

    city = models.CharField(max_length=100)
    region = models.CharField(max_length=100, blank=True, help_text="State or territory")
    venue = models.CharField(max_length=200, blank=True)
    address = models.CharField(
        max_length=300, blank=True,
        help_text="Full street address — appears in the calendar invite.")
    venue_note = models.CharField(
        max_length=200, blank=True,
        default="Venue details coming soon",
    )

    is_published = models.BooleanField(default=False)
    registration_open = models.BooleanField(default=True)

    class Meta:
        ordering = ['starts_at']

    def __str__(self):
        return f"{self.title} — {self.local_start:%b %d, %Y}"

    # --- timezone-aware display helpers ---------------------------------

    @property
    def tz(self):
        return ZoneInfo(self.timezone_name)

    @property
    def local_start(self):
        """Start time as clock time in the event's own timezone."""
        return self.starts_at.astimezone(self.tz)

    @property
    def tz_abbr(self):
        """Short label like PDT or AST, correct for that date."""
        return self.local_start.strftime('%Z')

    @property
    def image_path(self):
        """Static path for this event's photo, derived from the slug."""
        return f"images/{self.slug}.jpg"

    @property
    def is_upcoming(self):
        return self.starts_at >= timezone.now()

    @property
    def month_abbr(self):
        return self.local_start.strftime('%b').upper()

    @property
    def day_number(self):
        return self.local_start.strftime('%d')


class EventRegistration(models.Model):
    """Intake record for an event RSVP."""

    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name='registrations')

    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    email = models.CharField(max_length=254, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    linkedin = models.CharField(max_length=300, blank=True)
    location = models.CharField(max_length=150, blank=True)
    field = models.CharField(max_length=50, blank=True)
    company = models.CharField(max_length=200, blank=True)
    role = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)

    attended = models.BooleanField(
        default=False,
        help_text="Check after the event — RSVP is not attendance.",
    )

    candidate = models.ForeignKey(
        'talent.Candidate', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='event_registrations',
        help_text="Set automatically when you promote or merge this RSVP.",
    )
    status = models.CharField(max_length=20, choices=INTAKE_STATUS, default='new')
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-submitted_at']
        verbose_name = 'Event Registration'
        verbose_name_plural = 'Event Registrations'

    def __str__(self):
        return f"{self.first_name} {self.last_name} — {self.event.title}"


class EmailLog(models.Model):
    """
    One row per email sent to a registrant.

    Lets Carmen see who has already received an invite or a reminder, and
    lets the send screen offer to skip them.
    """

    KINDS = [
        ('invite', 'Calendar invite'),
        ('reminder', 'Reminder'),
    ]

    registration = models.ForeignKey(
        'EventRegistration', on_delete=models.CASCADE, related_name='emails')
    kind = models.CharField(max_length=20, choices=KINDS)
    subject = models.CharField(max_length=200, blank=True)

    sent_at = models.DateTimeField(auto_now_add=True)
    succeeded = models.BooleanField(default=True)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ['-sent_at']
        verbose_name = 'Email Log'
        verbose_name_plural = 'Email Log'

    def __str__(self):
        return f"{self.get_kind_display()} → {self.registration}"