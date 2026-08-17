import csv

from django.contrib import admin, messages
from django.http import HttpResponse

from talent.services import (
    find_matches, promote_submission, promote_rsvp, reject_intake,
)
from .models import (
    ProfessionalSubmission, CompanySubmission, Event, EventRegistration,
)


# --------------------------------------------------------------------------
# Actions and mixins — defined BEFORE the admin classes that reference them
# --------------------------------------------------------------------------

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
            "and merge: " + ", ".join(skipped)
        )
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


# --------------------------------------------------------------------------
# Intake
# --------------------------------------------------------------------------

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


# --------------------------------------------------------------------------
# Events
# --------------------------------------------------------------------------

class EventRegistrationInline(admin.TabularInline):
    model = EventRegistration
    extra = 0
    fields = ['first_name', 'last_name', 'email', 'company',
              'attended', 'status']
    show_change_link = True


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['title', 'starts_at', 'city', 'is_published',
                    'registration_open', 'rsvp_count']
    list_filter = ['is_published', 'registration_open', 'starts_at']
    prepopulated_fields = {'slug': ('title',)}
    inlines = [EventRegistrationInline]

    fieldsets = (
        ('Details', {
            'fields': ('title', 'slug', 'subtitle', 'description'),
            'description': 'The slug also names the photo — slug "palo-alto" '
                           'looks for static/images/palo-alto.jpg',
        }),
        ('When & Where', {
            'fields': ('starts_at', 'time_display', 'city', 'region',
                       'venue', 'venue_note')
        }),
        ('Visibility', {'fields': ('is_published', 'registration_open')}),
    )

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
    actions = [promote_as_new, mark_rejected, export_to_csv]    