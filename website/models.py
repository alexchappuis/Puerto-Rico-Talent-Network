from django.db import models
from django.utils import timezone


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
        help_text="URL fragment AND image filename — a matching "
                  "static/images/<slug>.jpg must exist.",
    )
    subtitle = models.CharField(
        max_length=200, blank=True,
        default="An evening to network & connect",
    )
    description = models.TextField(blank=True)

    starts_at = models.DateTimeField()
    time_display = models.CharField(
        max_length=100, blank=True,
        help_text="Leave blank to show the time from starts_at. "
                  "Set to 'Time coming soon' while TBD.",
    )

    city = models.CharField(max_length=100)
    region = models.CharField(max_length=100, blank=True, help_text="State or territory")
    venue = models.CharField(max_length=200, blank=True)
    venue_note = models.CharField(
        max_length=200, blank=True,
        default="Venue details coming soon",
    )

    is_published = models.BooleanField(default=False)
    registration_open = models.BooleanField(default=True)

    class Meta:
        ordering = ['starts_at']

    def __str__(self):
        return f"{self.title} — {self.starts_at:%b %d, %Y}"

    @property
    def image_path(self):
        """Static path for this event's photo — resolved via {% static %}."""
        return f"images/{self.slug}.jpg"

    @property
    def is_upcoming(self):
        return self.starts_at >= timezone.now()

    @property
    def month_abbr(self):
        return self.starts_at.strftime('%b').upper()

    @property
    def day_number(self):
        return self.starts_at.strftime('%d')


class EventRegistration(models.Model):
    """
    Intake record for an event RSVP. Immutable, like the submission models.
    """
    STATUS = [
        ('new', 'New'),
        ('reviewed', 'Reviewed'),
        ('rejected', 'Rejected'),
    ]

    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name='registrations')

    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    email = models.CharField(max_length=254, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    linkedin = models.CharField(max_length=300, blank=True)
    company = models.CharField(max_length=200, blank=True)
    role = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)

    attended = models.BooleanField(
        default=False,
        help_text="Check after the event — RSVP is not attendance.",
    )

    status = models.CharField(max_length=20, choices=STATUS, default='new')
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-submitted_at']
        verbose_name = 'Event Registration'
        verbose_name_plural = 'Event Registrations'

    def __str__(self):
        return f"{self.first_name} {self.last_name} — {self.event.title}"