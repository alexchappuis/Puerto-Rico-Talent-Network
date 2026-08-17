"""
talent/services.py — business logic.

Everything here is deliberately independent of the admin. When you replace
admin screens with custom views later, those views call these same functions
and nothing has to be rewritten.
"""

from django.db.models import Q
from django.utils import timezone

from .models import Candidate, Interaction


# Fields safe to copy from a signup into a candidate record.
# Order matters only for readability.
COPYABLE_FIELDS = [
    'email', 'phone', 'linkedin', 'location', 'field',
]


def find_matches(first_name='', last_name='', email=''):
    """
    Look for existing candidates who might be this same person.

    Returns (exact, likely):
      exact  — same email address
      likely — same first and last name, different or missing email

    Never merges automatically. Carmen decides.
    """
    exact = Candidate.objects.none()
    if email:
        exact = Candidate.objects.filter(email__iexact=email.strip())

    likely = Candidate.objects.none()
    if first_name and last_name:
        likely = Candidate.objects.filter(
            first_name__iexact=first_name.strip(),
            last_name__iexact=last_name.strip(),
        ).exclude(pk__in=exact.values_list('pk', flat=True))

    return exact, likely


def promote_submission(submission, merge_into=None):
    """
    Turn a ProfessionalSubmission into a Candidate.

    merge_into=None  → create a new candidate
    merge_into=<Candidate> → attach this signup to an existing person

    On merge, only blank fields are filled. Anything Carmen has already
    edited wins over form data, always.
    """
    if merge_into:
        candidate = merge_into
        _fill_blanks(candidate, submission)
    else:
        candidate = Candidate.objects.create(
            first_name=submission.first_name,
            last_name=submission.last_name,
            email=submission.email,
            phone=submission.phone,
            linkedin=submission.linkedin,
            location=submission.location,
            field=submission.field,
            summary=submission.message,
        )

    submission.candidate = candidate
    submission.status = 'merged' if merge_into else 'promoted'
    submission.reviewed_at = timezone.now()
    submission.save(update_fields=['candidate', 'status', 'reviewed_at'])

    return candidate


def promote_rsvp(rsvp, merge_into=None):
    """
    Turn an EventRegistration into a Candidate, and log the event
    as an interaction so it shows up in their history.
    """
    if merge_into:
        candidate = merge_into
        _fill_blanks(candidate, rsvp)
    else:
        candidate = Candidate.objects.create(
            first_name=rsvp.first_name,
            last_name=rsvp.last_name,
            email=rsvp.email,
            phone=rsvp.phone,
            linkedin=rsvp.linkedin,
            location=rsvp.location,
            field=rsvp.field,
            current_employer=rsvp.company,
            current_title=rsvp.role,
            summary=rsvp.notes,
        )
 
    if rsvp.attended:
        Interaction.objects.create(
            candidate=candidate,
            kind='event',
            occurred_at=rsvp.event.starts_at,
            notes=f"Attended {rsvp.event.title}.",
        )
 
    rsvp.candidate = candidate
    rsvp.status = 'merged' if merge_into else 'promoted'
    rsvp.reviewed_at = timezone.now()
    rsvp.save(update_fields=['candidate', 'status', 'reviewed_at'])
 
    return candidate


def reject_intake(obj, reason=''):
    """Mark a signup or RSVP as not worth adding. Nothing is deleted."""
    obj.status = 'rejected'
    obj.reviewed_at = timezone.now()
    obj.save(update_fields=['status', 'reviewed_at'])


def _fill_blanks(candidate, source):
    """
    Copy values from an intake record into a candidate, but only where
    the candidate's field is currently empty.

    This is the rule that protects Carmen's edits from being overwritten
    by stale form data.
    """
    changed = []
    for field in COPYABLE_FIELDS:
        incoming = getattr(source, field, '') or ''
        if incoming and not getattr(candidate, field, ''):
            setattr(candidate, field, incoming)
            changed.append(field)

    if changed:
        candidate.save(update_fields=changed)

    return changed


def stale_candidates(days=21):
    """Active candidates not contacted in `days`, plus those never contacted."""
    cutoff = timezone.now() - timezone.timedelta(days=days)
    return Candidate.objects.filter(
        Q(last_contacted__lt=cutoff) | Q(last_contacted__isnull=True),
        is_active=True,
    )