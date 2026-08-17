"""
talent/admin.py — Carmen's workspace.

The admin is a thin shell. All real logic lives in services.py.
"""

import csv
from django.contrib import admin, messages
from django.db.models import Q
from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    Candidate, Company, Role, Consideration, StageChange, Interaction,
)


# --------------------------------------------------------------------------
# Shared actions and filters
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


class FollowUpFilter(admin.SimpleListFilter):
    """The single most useful filter Carmen will have."""
    title = 'follow-up'
    parameter_name = 'followup'

    def lookups(self, request, model_admin):
        return [
            ('never', 'Never contacted'),
            ('21', 'No contact in 21+ days'),
            ('60', 'No contact in 60+ days'),
            ('recent', 'Contacted in last 7 days'),
        ]

    def queryset(self, request, queryset):
        value = self.value()
        now = timezone.now()

        if value == 'never':
            return queryset.filter(last_contacted__isnull=True)
        if value in ('21', '60'):
            cutoff = now - timezone.timedelta(days=int(value))
            return queryset.filter(
                Q(last_contacted__lt=cutoff) | Q(last_contacted__isnull=True))
        if value == 'recent':
            cutoff = now - timezone.timedelta(days=7)
            return queryset.filter(last_contacted__gte=cutoff)
        return queryset


# --------------------------------------------------------------------------
# Inlines
# --------------------------------------------------------------------------

class InteractionInline(admin.TabularInline):
    model = Interaction
    extra = 1
    fields = ['occurred_at', 'kind', 'notes', 'consideration']
    ordering = ['-occurred_at']
    verbose_name_plural = 'Conversation history'


class ConsiderationInline(admin.TabularInline):
    model = Consideration
    extra = 0
    fields = ['role', 'stage', 'decline_reason', 'stage_changed_at']
    readonly_fields = ['stage_changed_at']
    autocomplete_fields = ['role']
    verbose_name_plural = 'Roles under consideration'


class RoleInline(admin.TabularInline):
    model = Role
    extra = 0
    fields = ['title', 'field', 'seniority', 'location', 'status']
    show_change_link = True


class StageChangeInline(admin.TabularInline):
    model = StageChange
    extra = 0
    fields = ['from_stage', 'to_stage', 'changed_at']
    readonly_fields = ['from_stage', 'to_stage', 'changed_at']
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


# --------------------------------------------------------------------------
# Candidate
# --------------------------------------------------------------------------

@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'field', 'seniority', 'location',
                    'current_employer', 'contact_status', 'open_considerations']
    list_filter = [FollowUpFilter, 'field', 'seniority', 'based_in_pr', 'is_active']
    search_fields = ['first_name', 'last_name', 'email', 'location',
                     'current_employer', 'current_title', 'summary']
    readonly_fields = ['last_contacted', 'created_at', 'updated_at', 'intake_history']
    inlines = [ConsiderationInline, InteractionInline]
    actions = [export_to_csv]
    list_per_page = 50

    fieldsets = (
        ('Who', {
            'fields': ('first_name', 'last_name', 'summary')
        }),
        ('Contact', {
            'fields': ('email', 'phone', 'linkedin', 'location', 'based_in_pr')
        }),
        ('Professional', {
            'fields': ('field', 'seniority', 'current_title',
                       'current_employer', 'years_experience')
        }),
        ('Record', {
            'fields': ('is_active', 'last_contacted', 'intake_history',
                       'created_at', 'updated_at'),
        }),
    )

    def contact_status(self, obj):
        days = obj.days_since_contact
        if days is None:
            return format_html('<span style="color:#b91c1c;">Never</span>')
        if days >= 60:
            colour = '#b91c1c'
        elif days >= 21:
            colour = '#b45309'
        else:
            colour = '#047857'
        label = 'Today' if days == 0 else f'{days}d ago'
        return format_html('<span style="color:{};">{}</span>', colour, label)
    contact_status.short_description = 'Last contact'
    contact_status.admin_order_field = 'last_contacted'

    def open_considerations(self, obj):
        count = obj.considerations.filter(
            stage__in=Consideration.OPEN_STAGES).count()
        return count or '—'
    open_considerations.short_description = 'Active'

    def intake_history(self, obj):
        """Where this person came from — signups and RSVPs."""
        if not obj.pk:
            return '—'
        rows = []
        for sub in obj.submissions.all():
            rows.append(f'Signup form — {sub.submitted_at:%b %d, %Y}')
        for rsvp in obj.event_registrations.all():
            attended = ' (attended)' if rsvp.attended else ' (RSVP only)'
            rows.append(f'{rsvp.event.title}{attended}')
        return format_html('<br>'.join(rows)) if rows else 'Added manually'
    intake_history.short_description = 'Came from'


# --------------------------------------------------------------------------
# Company and Role
# --------------------------------------------------------------------------

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['name', 'industry', 'size', 'primary_contact_name',
                    'open_roles', 'is_active_client']
    list_filter = ['industry', 'is_active_client']
    search_fields = ['name', 'primary_contact_name', 'primary_contact_email']
    inlines = [RoleInline]

    def open_roles(self, obj):
        return obj.roles.filter(status='open').count() or '—'
    open_roles.short_description = 'Open roles'


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['title', 'company', 'field', 'seniority',
                    'location', 'status', 'pipeline_count']
    list_filter = ['status', 'field', 'seniority', 'remote_ok',
                   'relocation_supported', 'company']
    search_fields = ['title', 'company__name', 'description', 'requirements']
    autocomplete_fields = ['company']
    inlines = [ConsiderationInline]

    def pipeline_count(self, obj):
        return obj.considerations.filter(
            stage__in=Consideration.OPEN_STAGES).count() or '—'
    pipeline_count.short_description = 'In pipeline'


# --------------------------------------------------------------------------
# Consideration
# --------------------------------------------------------------------------

@admin.register(Consideration)
class ConsiderationAdmin(admin.ModelAdmin):
    list_display = ['candidate', 'role', 'stage', 'days_in_stage', 'created_at']
    list_filter = ['stage', 'decline_reason', 'role__company', 'role']
    search_fields = ['candidate__first_name', 'candidate__last_name',
                     'role__title', 'role__company__name']
    autocomplete_fields = ['candidate', 'role']
    list_editable = ['stage']
    readonly_fields = ['stage_changed_at', 'created_at']
    inlines = [StageChangeInline]
    actions = [export_to_csv]

    fieldsets = (
        (None, {'fields': ('candidate', 'role', 'stage', 'notes')}),
        ('If this ended without a placement', {
            'fields': ('decline_reason', 'decline_notes'),
            'description': 'Recording why a search ended is how the system '
                           'gets smarter over time. Worth filling in every time.',
        }),
        ('Record', {'fields': ('stage_changed_at', 'created_at')}),
    )

    def days_in_stage(self, obj):
        return (timezone.now() - obj.stage_changed_at).days
    days_in_stage.short_description = 'Days in stage'


# --------------------------------------------------------------------------
# Interaction
# --------------------------------------------------------------------------

@admin.register(Interaction)
class InteractionAdmin(admin.ModelAdmin):
    list_display = ['occurred_at', 'candidate', 'kind', 'short_notes']
    list_filter = ['kind', 'occurred_at']
    search_fields = ['candidate__first_name', 'candidate__last_name', 'notes']
    autocomplete_fields = ['candidate', 'consideration']
    date_hierarchy = 'occurred_at'

    def short_notes(self, obj):
        if not obj.notes:
            return '—'
        return obj.notes[:80] + ('…' if len(obj.notes) > 80 else '')
    short_notes.short_description = 'Notes'