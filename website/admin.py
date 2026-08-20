import csv
from zoneinfo import ZoneInfo

from django import forms
from django.contrib import admin, messages
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.utils import timezone as dj_timezone

from talent.services import (
    find_matches, promote_submission, promote_rsvp, reject_intake,
)
from .models import (
    ProfessionalSubmission, CompanySubmission,
    Event, EventRegistration, EmailLog,
)
from .notifications import (
    send_blast, default_subject, default_body, render_message,
)


# ==========================================================================
# Shared actions
# ==========================================================================

def export_to_csv(modeladmin, request, queryset):
    model = queryset.model
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (
        f'attachment; filename={model._meta.verbose_name_plural}.csv')
    writer = csv.writer(response)
    fields = [f.name for f in model._meta.fields]
    writer.writerow(fields)
    for obj in queryset:
        writer.writerow([getattr(obj, f) for f in fields])
    return response

export_to_csv.short_description = "Export selected to CSV"


def promote_as_new(modeladmin, request, queryset):
    """Create a fresh candidate for each selected intake record."""
    created = 0
    skipped = []

    for obj in queryset.filter(status='new'):
        exact, likely = find_matches(obj.first_name, obj.last_name, obj.email)
        if exact.exists() or likely.exists():
            skipped.append(f"{obj.first_name} {obj.last_name}")
            continue

        if isinstance(obj, EventRegistration):
            promote_rsvp(obj)
        else:
            promote_submission(obj)
        created += 1

    if created:
        messages.success(request, f"Created {created} candidate(s).")
    if skipped:
        messages.warning(
            request,
            "Possible duplicates, not promoted — review these individually "
            "and merge: " + ", ".join(skipped))
    if not created and not skipped:
        messages.info(request, "Nothing to do — those were already reviewed.")

promote_as_new.short_description = "Promote to new candidate"


def mark_rejected(modeladmin, request, queryset):
    count = 0
    for obj in queryset.filter(status='new'):
        reject_intake(obj)
        count += 1
    messages.success(request, f"Rejected {count} item(s).")

mark_rejected.short_description = "Reject (spam or not a fit)"


class NewFirstMixin:
    """Default the changelist to unreviewed items — makes it a work queue."""

    def changelist_view(self, request, extra_context=None):
        if 'status__exact' not in request.GET:
            q = request.GET.copy()
            q['status__exact'] = 'new'
            request.GET = q
            request.META['QUERY_STRING'] = request.GET.urlencode()
        return super().changelist_view(request, extra_context=extra_context)


# ==========================================================================
# Email blast
# ==========================================================================

class BlastForm(forms.Form):
    subject = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'style': 'width:100%'}),
    )
    body = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 6, 'style': 'width:100%'}),
        help_text=(
            "Your message. Event details, the Google Calendar button, and "
            "the sign-off are added automatically below it."
        ),
    )
    skip_already_sent = forms.BooleanField(
        required=False,
        initial=True,
        label="Skip anyone who already received this",
    )


def _run_blast(request, registrations, kind, events):
    """Shared confirmation-and-send flow for both blast kinds."""

    eligible = registrations.exclude(email='')
    already = set(
        EmailLog.objects.filter(
            registration__in=eligible, kind=kind, succeeded=True
        ).values_list('registration_id', flat=True)
    )

    if 'apply' in request.POST:
        form = BlastForm(request.POST)
        if form.is_valid():
            targets = eligible
            if form.cleaned_data['skip_already_sent']:
                targets = eligible.exclude(pk__in=already)

            sent, failed = send_blast(
                targets, kind,
                form.cleaned_data['subject'],
                form.cleaned_data['body'],
            )

            if sent:
                messages.success(request, f"Sent {sent} email(s).")
            if failed:
                messages.error(
                    request,
                    f"{failed} failed. Check the email log on each "
                    "registration for details.")
            if not sent and not failed:
                messages.info(
                    request,
                    "Nobody to send to — everyone already received it.")
            return redirect(request.get_full_path())
    else:
        first_event = events[0] if events else None
        form = BlastForm(initial={
            'subject': default_subject(first_event, kind) if first_event else '',
            'body': default_body(kind),
        })

    preview_html = ''
    if events:
        _, preview_html = render_message(
            events[0], kind, default_body(kind), 'Alex')

    return render(request, 'admin/event_blast.html', {
        'title': 'Send calendar invite' if kind == 'invite' else 'Send reminder',
        'kind': kind,
        'form': form,
        'events': events,
        'total': eligible.count(),
        'already_count': len(already),
        'no_email_count': registrations.filter(email='').count(),
        'preview_html': preview_html,
        'action_name': request.POST.get('action', ''),
        'selected': request.POST.getlist(admin.helpers.ACTION_CHECKBOX_NAME),
        'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
    })


def event_send_invite(modeladmin, request, queryset):
    registrations = EventRegistration.objects.filter(
        event__in=queryset).exclude(status='rejected')
    return _run_blast(request, registrations, 'invite', list(queryset))

event_send_invite.short_description = "Send calendar invite to all registrants"


def event_send_reminder(modeladmin, request, queryset):
    registrations = EventRegistration.objects.filter(
        event__in=queryset).exclude(status='rejected')
    return _run_blast(request, registrations, 'reminder', list(queryset))

event_send_reminder.short_description = "Send reminder to all registrants"


def reg_send_invite(modeladmin, request, queryset):
    events = list(Event.objects.filter(registrations__in=queryset).distinct())
    return _run_blast(request, queryset, 'invite', events)

reg_send_invite.short_description = "Send calendar invite to selected"


def reg_send_reminder(modeladmin, request, queryset):
    events = list(Event.objects.filter(registrations__in=queryset).distinct())
    return _run_blast(request, queryset, 'reminder', events)

reg_send_reminder.short_description = "Send reminder to selected"


class EmailLogInline(admin.TabularInline):
    model = EmailLog
    extra = 0
    fields = ['kind', 'subject', 'sent_at', 'succeeded', 'error']
    readonly_fields = ['kind', 'subject', 'sent_at', 'succeeded', 'error']
    can_delete = False
    verbose_name_plural = 'Emails sent'

    def has_add_permission(self, request, obj=None):
        return False


# ==========================================================================
# Intake
# ==========================================================================

@admin.register(ProfessionalSubmission)
class ProfessionalSubmissionAdmin(NewFirstMixin, admin.ModelAdmin):
    list_display = ['first_name', 'last_name', 'email', 'location',
                    'field', 'status', 'candidate', 'submitted_at']
    list_filter = ['status', 'field', 'submitted_at']
    search_fields = ['first_name', 'last_name', 'email', 'location']
    readonly_fields = ['submitted_at', 'reviewed_at', 'candidate']
    ordering = ['-submitted_at']
    actions = [promote_as_new, mark_rejected, export_to_csv]


@admin.register(CompanySubmission)
class CompanySubmissionAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'contact_name', 'email',
                    'industry', 'size', 'submitted_at']
    list_filter = ['industry', 'size', 'submitted_at']
    search_fields = ['company_name', 'contact_name', 'email']
    readonly_fields = ['submitted_at']
    ordering = ['-submitted_at']
    actions = [export_to_csv]


# ==========================================================================
# Events
# ==========================================================================

class EventAdminForm(forms.ModelForm):
    """
    Makes starts_at mean local clock time in the event's own timezone.

    Django stores datetimes in UTC and the admin normally interprets input
    using settings.TIME_ZONE. This form intercepts both directions so that
    what Carmen types is what attendees see: type 6:00 PM, pick Pacific,
    and it means 6pm in California.
    """

    class Meta:
        model = Event
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = getattr(self, 'instance', None)
        if instance and instance.pk and instance.starts_at:
            local = instance.starts_at.astimezone(
                ZoneInfo(instance.timezone_name))
            self.initial['starts_at'] = local.replace(tzinfo=None)

    def clean(self):
        cleaned = super().clean()
        starts_at = cleaned.get('starts_at')
        tz_name = cleaned.get('timezone_name')

        if starts_at and tz_name:
            if dj_timezone.is_aware(starts_at):
                starts_at = dj_timezone.make_naive(
                    starts_at, dj_timezone.get_current_timezone())
            cleaned['starts_at'] = starts_at.replace(tzinfo=ZoneInfo(tz_name))

        return cleaned


class EventRegistrationInline(admin.TabularInline):
    model = EventRegistration
    extra = 0
    fields = ['first_name', 'last_name', 'email', 'company',
              'attended', 'status']
    show_change_link = True


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    form = EventAdminForm
    list_display = ['title', 'local_time_display', 'city', 'is_published',
                    'registration_open', 'rsvp_count']
    list_filter = ['is_published', 'registration_open', 'starts_at']
    prepopulated_fields = {'slug': ('title',)}
    inlines = [EventRegistrationInline]
    actions = [event_send_invite, event_send_reminder]

    fieldsets = (
        ('Details', {
            'fields': ('title', 'slug', 'subtitle', 'description'),
            'description': 'The slug also names the photo — slug "palo-alto" '
                           'looks for static/images/palo-alto.jpg',
        }),
        ('When & Where', {
            'fields': ('starts_at', 'timezone_name', 'time_display',
                       'duration_minutes', 'city', 'region', 'venue',
                       'address', 'venue_note'),
            'description': 'Enter the start time as local clock time for the '
                           'city where the event happens, then pick that '
                           'timezone. Address and duration appear on the '
                           'calendar invite.',
        }),
        ('Visibility', {'fields': ('is_published', 'registration_open')}),
    )

    def local_time_display(self, obj):
        return f"{obj.local_start:%b %d, %Y · %-I:%M %p} {obj.tz_abbr}"
    local_time_display.short_description = 'Starts'
    local_time_display.admin_order_field = 'starts_at'

    def rsvp_count(self, obj):
        return obj.registrations.count()
    rsvp_count.short_description = 'RSVPs'


@admin.register(EventRegistration)
class EventRegistrationAdmin(NewFirstMixin, admin.ModelAdmin):
    list_display = ['first_name', 'last_name', 'email', 'event', 'location',
                    'field', 'attended', 'status', 'candidate', 'submitted_at']
    list_filter = ['status', 'event', 'field', 'attended', 'submitted_at']
    search_fields = ['first_name', 'last_name', 'email', 'company', 'location']
    list_editable = ['attended']
    readonly_fields = ['submitted_at', 'reviewed_at', 'candidate']
    inlines = [EmailLogInline]
    actions = [reg_send_invite, reg_send_reminder,
               promote_as_new, mark_rejected, export_to_csv]