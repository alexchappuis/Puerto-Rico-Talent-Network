import csv
from django.contrib import admin
from django.http import HttpResponse
from .models import ProfessionalSubmission, CompanySubmission


def export_to_csv(modeladmin, request, queryset):
    model = queryset.model
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename={model._meta.verbose_name_plural}.csv'
    writer = csv.writer(response)
    fields = [f.name for f in model._meta.fields]
    writer.writerow(fields)
    for obj in queryset:
        writer.writerow([getattr(obj, f) for f in fields])
    return response

export_to_csv.short_description = "Export selected to CSV"


@admin.register(ProfessionalSubmission)
class ProfessionalSubmissionAdmin(admin.ModelAdmin):
    list_display = ['first_name', 'last_name', 'email', 'location', 'field', 'submitted_at']
    list_filter = ['field', 'submitted_at']
    search_fields = ['first_name', 'last_name', 'email', 'location']
    readonly_fields = ['submitted_at']
    ordering = ['-submitted_at']
    actions = [export_to_csv]


@admin.register(CompanySubmission)
class CompanySubmissionAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'contact_name', 'email', 'industry', 'size', 'submitted_at']
    list_filter = ['industry', 'size', 'submitted_at']
    search_fields = ['company_name', 'contact_name', 'email']
    readonly_fields = ['submitted_at']
    ordering = ['-submitted_at']
    actions = [export_to_csv]