from django.contrib import admin
from .models import ProfessionalSubmission, CompanySubmission


@admin.register(ProfessionalSubmission)
class ProfessionalSubmissionAdmin(admin.ModelAdmin):
    list_display = ['first_name', 'last_name', 'email', 'location', 'field', 'submitted_at']
    list_filter = ['field', 'submitted_at']
    search_fields = ['first_name', 'last_name', 'email', 'location']
    readonly_fields = ['submitted_at']
    ordering = ['-submitted_at']


@admin.register(CompanySubmission)
class CompanySubmissionAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'contact_name', 'email', 'industry', 'size', 'submitted_at']
    list_filter = ['industry', 'size', 'submitted_at']
    search_fields = ['company_name', 'contact_name', 'email']
    readonly_fields = ['submitted_at']
    ordering = ['-submitted_at']