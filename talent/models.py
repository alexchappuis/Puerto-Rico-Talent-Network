"""
talent/models.py — the core records for Carmen's workspace.

Naming note: confirm these with Carmen before migrating. If she says
"prospect" instead of "candidate", rename now rather than later.
"""

from django.db import models
from django.utils import timezone


class Candidate(models.Model):
    """A real person in the network. Created by promoting a signup or RSVP."""

    # Identity
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    linkedin = models.CharField(max_length=300, blank=True)

    # Location
    location = models.CharField(
        max_length=150, blank=True, help_text="City, state/territory")
    based_in_pr = models.BooleanField(
        default=False, verbose_name="Currently in Puerto Rico")

    # Professional
    FIELDS = [
        ('technology', 'Technology / Engineering'),
        ('finance', 'Finance / Accounting'),
        ('operations', 'Operations / Supply Chain'),
        ('marketing', 'Marketing / Growth'),
        ('sales', 'Sales / Business Development'),
        ('people', 'People / HR'),
        ('legal', 'Legal / Compliance'),
        ('executive', 'Executive Leadership'),
        ('other', 'Other'),
    ]
    SENIORITY = [
        ('entry', 'Entry'),
        ('mid', 'Mid'),
        ('senior', 'Senior'),
        ('lead', 'Lead / Principal'),
        ('director', 'Director'),
        ('exec', 'Executive'),
    ]

    field = models.CharField(max_length=50, choices=FIELDS, blank=True)
    seniority = models.CharField(max_length=20, choices=SENIORITY, blank=True)
    current_title = models.CharField(max_length=200, blank=True)
    current_employer = models.CharField(max_length=200, blank=True)
    years_experience = models.PositiveSmallIntegerField(null=True, blank=True)

    # Carmen's working notes
    summary = models.TextField(
        blank=True, help_text="Your own short description of this person.")

    # Follow-up tracking — kept current automatically by Interaction.save()
    last_contacted = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(
        default=True,
        help_text="Uncheck to hide someone who has asked not to be contacted.")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['last_name', 'first_name']
        indexes = [
            models.Index(fields=['last_contacted']),
            models.Index(fields=['last_name', 'first_name']),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def days_since_contact(self):
        if not self.last_contacted:
            return None
        return (timezone.now() - self.last_contacted).days


class Company(models.Model):
    """A client organization hiring in Puerto Rico."""

    INDUSTRIES = [
        ('tech', 'Technology'),
        ('finance', 'Financial Services'),
        ('pharma', 'Pharma / Life Sciences'),
        ('manufacturing', 'Manufacturing'),
        ('professional', 'Professional Services'),
        ('energy', 'Energy / Sustainability'),
        ('real_estate', 'Real Estate / Development'),
        ('other', 'Other'),
    ]

    name = models.CharField(max_length=200)
    website = models.CharField(max_length=300, blank=True)
    industry = models.CharField(max_length=50, choices=INDUSTRIES, blank=True)
    size = models.CharField(max_length=20, blank=True)

    primary_contact_name = models.CharField(max_length=100, blank=True)
    primary_contact_title = models.CharField(max_length=100, blank=True)
    primary_contact_email = models.EmailField(blank=True)

    notes = models.TextField(blank=True)
    is_active_client = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Companies'

    def __str__(self):
        return self.name


class Role(models.Model):
    """An open position at a company."""

    STATUS = [
        ('open', 'Open'),
        ('on_hold', 'On hold'),
        ('filled', 'Filled'),
        ('cancelled', 'Cancelled'),
    ]

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='roles')
    title = models.CharField(max_length=200)
    field = models.CharField(max_length=50, choices=Candidate.FIELDS, blank=True)
    seniority = models.CharField(max_length=20, choices=Candidate.SENIORITY, blank=True)

    location = models.CharField(max_length=150, blank=True)
    remote_ok = models.BooleanField(default=False)
    relocation_supported = models.BooleanField(default=False)

    description = models.TextField(blank=True)
    requirements = models.TextField(blank=True)

    status = models.CharField(max_length=20, choices=STATUS, default='open')
    opened_on = models.DateField(default=timezone.now)
    target_fill_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-opened_on']

    def __str__(self):
        return f"{self.title} — {self.company.name}"


class Consideration(models.Model):
    """
    A candidate being considered for a specific role.

    The stage lives here, not on Candidate — one person can be in
    several pipelines at different stages simultaneously.
    """

    STAGES = [
        ('sourced', 'Sourced'),
        ('contacted', 'Contacted'),
        ('screening', 'Screening'),
        ('submitted', 'Submitted to client'),
        ('interviewing', 'Interviewing'),
        ('offer', 'Offer extended'),
        ('placed', 'Placed'),
        ('declined_by_candidate', 'Declined by candidate'),
        ('declined_by_client', 'Declined by client'),
        ('closed', 'Closed'),
    ]

    OPEN_STAGES = ['sourced', 'contacted', 'screening',
                   'submitted', 'interviewing', 'offer']

    DECLINE_REASONS = [
        ('', '—'),
        ('compensation', 'Compensation'),
        ('relocation', 'Unwilling to relocate'),
        ('spouse_employment', 'Spouse employment'),
        ('schools', 'Schools / children'),
        ('timing', 'Timing'),
        ('counteroffer', 'Accepted counteroffer'),
        ('other_offer', 'Took another offer'),
        ('role_fit', 'Role not a fit'),
        ('company_fit', 'Company not a fit'),
        ('client_skills', 'Client: skills gap'),
        ('client_seniority', 'Client: seniority mismatch'),
        ('other', 'Other'),
    ]

    candidate = models.ForeignKey(
        Candidate, on_delete=models.CASCADE, related_name='considerations')
    role = models.ForeignKey(
        Role, on_delete=models.CASCADE, related_name='considerations')

    stage = models.CharField(max_length=30, choices=STAGES, default='sourced')
    decline_reason = models.CharField(
        max_length=30, choices=DECLINE_REASONS, blank=True,
        help_text="Fill in whenever a consideration ends without a placement. "
                  "This becomes valuable data over time.")
    decline_notes = models.TextField(blank=True)

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    stage_changed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-stage_changed_at']
        unique_together = [['candidate', 'role']]

    def __str__(self):
        return f"{self.candidate} → {self.role}"

    @property
    def is_open(self):
        return self.stage in self.OPEN_STAGES

    def save(self, *args, **kwargs):
        """Record a StageChange row whenever the stage moves."""
        previous = None
        if self.pk:
            previous = Consideration.objects.filter(pk=self.pk).values_list(
                'stage', flat=True).first()

        if previous and previous != self.stage:
            self.stage_changed_at = timezone.now()

        super().save(*args, **kwargs)

        if previous and previous != self.stage:
            StageChange.objects.create(
                consideration=self,
                from_stage=previous,
                to_stage=self.stage,
            )


class StageChange(models.Model):
    """Audit trail of pipeline movement. Never edited by hand."""

    consideration = models.ForeignKey(
        Consideration, on_delete=models.CASCADE, related_name='stage_changes')
    from_stage = models.CharField(max_length=30)
    to_stage = models.CharField(max_length=30)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-changed_at']

    def __str__(self):
        return f"{self.consideration_id}: {self.from_stage} → {self.to_stage}"


class Interaction(models.Model):
    """A call, email, meeting, or note involving a candidate."""

    KINDS = [
        ('call', 'Call'),
        ('email', 'Email'),
        ('meeting', 'Meeting'),
        ('event', 'Met at event'),
        ('linkedin', 'LinkedIn'),
        ('note', 'Note'),
    ]

    candidate = models.ForeignKey(
        Candidate, on_delete=models.CASCADE, related_name='interactions')
    consideration = models.ForeignKey(
        Consideration, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='interactions',
        help_text="Optional — link this to a specific role conversation.")

    kind = models.CharField(max_length=20, choices=KINDS, default='call')
    occurred_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-occurred_at']
        indexes = [models.Index(fields=['candidate', '-occurred_at'])]

    def __str__(self):
        return f"{self.get_kind_display()} — {self.candidate} ({self.occurred_at:%b %d, %Y})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._refresh_candidate_last_contacted()

    def delete(self, *args, **kwargs):
        candidate = self.candidate
        super().delete(*args, **kwargs)
        latest = candidate.interactions.first()
        candidate.last_contacted = latest.occurred_at if latest else None
        candidate.save(update_fields=['last_contacted'])

    def _refresh_candidate_last_contacted(self):
        latest = self.candidate.interactions.first()
        if latest and self.candidate.last_contacted != latest.occurred_at:
            self.candidate.last_contacted = latest.occurred_at
            self.candidate.save(update_fields=['last_contacted'])