from django.db import models


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