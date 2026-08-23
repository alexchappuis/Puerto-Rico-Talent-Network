from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from .models import (
    ProfessionalSubmission,
    CompanySubmission,
    Event,
    EventRegistration,
)


def home(request):
    """Landing page view."""
    upcoming = Event.objects.filter(
        is_published=True,
        starts_at__gte=timezone.now(),
    )[:2]
    return render(request, 'PRTN/home.html', {'upcoming_events': upcoming})


def about_us(request):
    """About Us page view."""
    return render(request, 'PRTN/about_us.html')


def join_the_network(request):
    """Join the Network page with forms for professionals and companies."""
    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        if form_type == 'professional':
            submission = ProfessionalSubmission.objects.create(
                first_name=request.POST.get('first_name', ''),
                last_name=request.POST.get('last_name', ''),
                email=request.POST.get('email', ''),
                phone=request.POST.get('phone', ''),
                linkedin=request.POST.get('linkedin', ''),
                location=request.POST.get('location', ''),
                field=request.POST.get('field', ''),
                message=request.POST.get('message', ''),
            )

            send_notification(
                subject=f"New Professional Submission: {submission.first_name} {submission.last_name}",
                body=(
                    f"Name: {submission.first_name} {submission.last_name}\n"
                    f"Email: {submission.email}\n"
                    f"Phone: {submission.phone}\n"
                    f"LinkedIn: {submission.linkedin}\n"
                    f"Location: {submission.location}\n"
                    f"Field: {submission.field}\n"
                    f"Message: {submission.message}\n"
                    f"\nSubmitted: {submission.submitted_at}"
                ),
            )

            messages.success(request, "Thanks for joining the network! We'll be in touch soon.")

        elif form_type == 'company':
            submission = CompanySubmission.objects.create(
                company_name=request.POST.get('company_name', ''),
                website=request.POST.get('website', ''),
                contact_name=request.POST.get('contact_name', ''),
                title=request.POST.get('title', ''),
                email=request.POST.get('email', ''),
                industry=request.POST.get('industry', ''),
                size=request.POST.get('size', ''),
                hiring_needs=request.POST.get('hiring_needs', ''),
            )

            send_notification(
                subject=f"New Company Submission: {submission.company_name}",
                body=(
                    f"Company: {submission.company_name}\n"
                    f"Website: {submission.website}\n"
                    f"Contact: {submission.contact_name} ({submission.title})\n"
                    f"Email: {submission.email}\n"
                    f"Industry: {submission.industry}\n"
                    f"Size: {submission.size}\n"
                    f"Hiring Needs: {submission.hiring_needs}\n"
                    f"\nSubmitted: {submission.submitted_at}"
                ),
            )

            messages.success(request, "Thanks for reaching out! We'll be in touch soon.")

        return redirect('join_the_network')

    return render(request, 'PRTN/join_the_network.html')


def events(request):
    """Public events listing — upcoming, published events only."""
    upcoming = Event.objects.filter(
        is_published=True,
        starts_at__gte=timezone.now(),
    )
    return render(request, 'PRTN/events.html', {
        'featured': upcoming.filter(is_featured=True),
        'events': upcoming.filter(is_featured=False),
        'has_any': upcoming.exists(),
    })


def event_register(request, slug):
    """RSVP form for a single event."""
    event = get_object_or_404(Event, slug=slug, is_published=True)

    if request.method == 'POST':
        registration = EventRegistration.objects.create(
            event=event,
            first_name=request.POST.get('first_name', ''),
            last_name=request.POST.get('last_name', ''),
            email=request.POST.get('email', ''),
            phone=request.POST.get('phone', ''),
            linkedin=request.POST.get('linkedin', ''),
            location=request.POST.get('location', ''),
            field=request.POST.get('field', ''),
            company=request.POST.get('company', ''),
            role=request.POST.get('role', ''),
            notes=request.POST.get('notes', ''),
        )

        send_notification(
            subject=f"Event RSVP — {event.title}: {registration.first_name} {registration.last_name}",
            body=(
                f"Event: {event.title} ({event.starts_at:%b %d, %Y})\n\n"
                f"Name: {registration.first_name} {registration.last_name}\n"
                f"Email: {registration.email}\n"
                f"Phone: {registration.phone}\n"
                f"LinkedIn: {registration.linkedin}\n"
                f"Location: {registration.location}\n"
                f"Field: {registration.field}\n"
                f"Company: {registration.company}\n"
                f"Role: {registration.role}\n"
                f"Notes: {registration.notes}\n"
            ),
        )
        messages.success(request, "You're on the list — we'll be in touch with details.")
        return redirect('event_register', slug=slug)

    return render(request, 'PRTN/event_register.html', {'event': event})


def send_notification(subject, body):
    """Send email notification for new form submission."""
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.NOTIFICATION_EMAIL],
            fail_silently=True,
        )
    except Exception:
        pass