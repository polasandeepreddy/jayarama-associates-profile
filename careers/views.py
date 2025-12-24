# careers/views.py
import csv
import json
import logging
import uuid
import hmac
import hashlib

from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail, EmailMultiAlternatives
from django.db import transaction, OperationalError
from django.db.models import Q, F, Count, Avg, Max, Min, Sum, Case, When, Value, FloatField
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone
from django.urls import reverse, reverse_lazy

from django.views.generic import (
    ListView, DetailView, CreateView, TemplateView, View, DeleteView
)
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages

from .models import (
    JobOpening, JobCategory, JobApplication,
    JobAlertSubscription, SavedJob, ApplicationEventLog
)
from .forms import (
    AdvancedJobApplicationForm, QuickApplyForm,
    JobAlertSubscriptionForm, JobSearchFilterForm,
    SavedJobForm, ApplicationStatusUpdateForm
)

logger = logging.getLogger(__name__)

# Cache keys
CACHE_KEYS = {
    'featured_jobs': 'featured_jobs_7d',
    'job_categories': 'job_categories_active',
    'job_stats': 'job_stats_global',
    'recent_jobs': 'recent_jobs_24h',
}

# Helper utilities -----------------------------------------------------------

def model_has_field(model, field_name):
    """Return True if model defines field_name."""
    try:
        model._meta.get_field(field_name)
        return True
    except Exception:
        return False

def first_existing_field(model, preferred):
    """
    Return the first field name in 'preferred' that exists on model.
    preferred: list/tuple of field names.
    """
    for name in preferred:
        if model_has_field(model, name):
            return name
    return None

def safe_order_field(model, preferred, fallback='id'):
    """Pick a safe field to order by from preferred list, else fallback."""
    f = first_existing_field(model, preferred)
    return f or fallback

def serialize_jobs_for_cache(qs, fields=None, limit=10):
    """
    Convert queryset to list of dicts for caching/returning.
    Uses .values(...) when possible to avoid pickling model instances.
    """
    fields = fields or ['id', 'title', 'reference_id', 'job_category_id', 'location', 'posted_date', 'published_date']
    try:
        return list(qs.values(*[f for f in fields if f in [f.name for f in qs.model._meta.fields]])[:limit])
    except Exception:
        # Last-resort: build minimal list
        result = []
        try:
            for obj in qs[:limit]:
                result.append({
                    'id': getattr(obj, 'id', None),
                    'title': getattr(obj, 'title', None),
                    'reference_id': getattr(obj, 'reference_id', None),
                    'location': getattr(obj, 'location', None),
                })
        except Exception:
            return []
        return result

# discover safe date fields for JobOpening and JobApplication
JOB_DATE_PREFS = ['created_at', 'posted_date', 'published_date', 'created', 'timestamp']
APP_DATE_PREFS = ['created_at', 'application_date', 'applied_at', 'timestamp']

JOB_DATE_FIELD = first_existing_field(JobOpening, JOB_DATE_PREFS) or 'id'
JOB_POSTED_FIELD = first_existing_field(JobOpening, ['posted_date', 'published_date', 'created_at', 'created']) or 'id'
JOB_UPDATED_FIELD = first_existing_field(JobOpening, ['updated_at', 'last_modified', 'modified_at']) or None

APP_DATE_FIELD = first_existing_field(JobApplication, APP_DATE_PREFS) or None
APP_CREATED_FIELD = first_existing_field(JobApplication, ['created_at', 'application_date', 'applied_at']) or None

# Views ---------------------------------------------------------------------

class CareersHomeView(TemplateView):
    """Enhanced home page with caching and safe DB access"""
    template_name = 'careers/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()

        # Featured jobs - cached as list of dicts, not queryset
        featured_jobs = cache.get(CACHE_KEYS['featured_jobs'])
        if featured_jobs is None:
            try:
                query_filters = {
                    'status': 'open',
                    'is_featured': True,
                }
                # respect published_date presence if available
                if model_has_field(JobOpening, 'published_date'):
                    query_filters['published_date__lte'] = now

                qs = JobOpening.objects.filter(**query_filters).select_related('job_category')
                order_field = safe_order_field(JobOpening, JOB_DATE_PREFS, fallback='id')
                qs = qs.order_by(f'-{order_field}')
                featured_jobs = serialize_jobs_for_cache(qs, limit=6)
            except Exception as e:
                logger.exception("Error fetching featured jobs: %s", e)
                featured_jobs = []
            cache.set(CACHE_KEYS['featured_jobs'], featured_jobs, 3600)

        # Job categories with job counts - cached
        categories = cache.get(CACHE_KEYS['job_categories'])
        if categories is None:
            try:
                categories_qs = JobCategory.objects.filter(is_active=True).annotate(
                    job_count=Count('jobs', filter=Q(jobs__status='open'))
                ).filter(job_count__gt=0).order_by('-job_count')[:8]
                categories = list(categories_qs.values('id', 'name', 'slug', 'job_count'))
            except Exception as e:
                logger.exception("Error fetching categories: %s", e)
                categories = []
            cache.set(CACHE_KEYS['job_categories'], categories, 1800)

        # Recent jobs: use published_date/posted_date if available
        week_ago = now - timedelta(days=7)
        try:
            recent_filters = {'status': 'open'}
            if model_has_field(JobOpening, 'published_date'):
                recent_filters['published_date__gte'] = week_ago
                recent_filters['published_date__lte'] = now
            else:
                # fallback to posted_date if present
                if model_has_field(JobOpening, 'posted_date'):
                    recent_filters['posted_date__gte'] = week_ago
                    recent_filters['posted_date__lte'] = now

            recent_qs = JobOpening.objects.filter(**recent_filters).select_related('job_category')
            recent_qs = recent_qs.order_by(f'-{safe_order_field(JobOpening, JOB_DATE_PREFS)}')[:8]
            recent_jobs = serialize_jobs_for_cache(recent_qs, limit=8)
        except Exception as e:
            logger.exception("Error fetching recent jobs: %s", e)
            recent_jobs = []

        # Global stats - cached
        stats = cache.get(CACHE_KEYS['job_stats'])
        if stats is None:
            try:
                stats = {
                    'total_openings': JobOpening.objects.filter(status='open').count(),
                    'total_applications': JobApplication.objects.count(),
                    'avg_salary': JobOpening.objects.filter(show_salary=True).aggregate(
                        Avg('salary_range_min')
                    )['salary_range_min__avg'],
                    'remote_jobs': JobOpening.objects.filter(status='open', is_remote_allowed=True).count(),
                }
            except Exception as e:
                logger.exception("Error calculating stats: %s", e)
                stats = {'total_openings': 0, 'total_applications': 0, 'avg_salary': None, 'remote_jobs': 0}
            cache.set(CACHE_KEYS['job_stats'], stats, 3600)

        # Urgent jobs (closing soon) - safe filters
        try:
            urgent_deadline = now + timedelta(days=3)
            urgent_qs = JobOpening.objects.filter(status='open')
            if model_has_field(JobOpening, 'application_deadline'):
                urgent_qs = urgent_qs.filter(application_deadline__lte=urgent_deadline, application_deadline__gte=now)
            else:
                urgent_qs = urgent_qs.none()
            urgent_qs = urgent_qs.order_by('application_deadline')[:4]
            urgent_jobs = serialize_jobs_for_cache(urgent_qs, limit=4)
        except Exception as e:
            logger.exception("Error fetching urgent jobs: %s", e)
            urgent_jobs = []

        # Popular searches (static-ish fallback)
        popular_searches = [
            {'term': 'Software Engineer', 'count': 42},
            {'term': 'Data Analyst', 'count': 38},
            {'term': 'Project Manager', 'count': 31},
            {'term': 'Business Analyst', 'count': 28},
        ]

        context.update({
            'featured_jobs': featured_jobs,
            'recent_jobs': recent_jobs,
            'urgent_jobs': urgent_jobs,
            'categories': categories,
            'stats': stats,
            'popular_searches': popular_searches,
            'search_form': JobSearchFilterForm(),
            'alert_form': JobAlertSubscriptionForm(),
            'quick_apply_form': QuickApplyForm(),
        })
        return context


class JobListView(ListView):
    """Advanced job listing with filtering, sorting, and pagination"""
    model = JobOpening
    template_name = 'careers/job_list.html'
    context_object_name = 'jobs'
    paginate_by = 12

    def get_queryset(self):
        keyword = (self.request.GET.get('keyword') or '').strip()
        now = timezone.now()

        qs_filters = {'status': 'open'}
        if model_has_field(JobOpening, 'published_date'):
            qs_filters['published_date__lte'] = now

        queryset = JobOpening.objects.filter(**qs_filters).select_related('job_category')

        form = JobSearchFilterForm(self.request.GET)
        if form.is_valid():
            form_keyword = form.cleaned_data.get('keyword')
            if form_keyword:
                queryset = queryset.filter(
                    Q(title__icontains=form_keyword) |
                    Q(short_description__icontains=form_keyword) |
                    Q(detailed_description__icontains=form_keyword) |
                    Q(required_skills__icontains=form_keyword) |
                    Q(tools_technologies__icontains=form_keyword)
                )

            location = form.cleaned_data.get('location')
            if location:
                if 'remote' in location.lower():
                    queryset = queryset.filter(is_remote_allowed=True)
                else:
                    queryset = queryset.filter(location__icontains=location)

            job_types = form.cleaned_data.get('job_type')
            if job_types:
                queryset = queryset.filter(job_type__in=job_types)

            experience_levels = form.cleaned_data.get('experience_level')
            if experience_levels:
                queryset = queryset.filter(experience_level__in=experience_levels)

            categories = form.cleaned_data.get('category')
            if categories:
                queryset = queryset.filter(job_category__in=categories)

            salary_range = form.cleaned_data.get('salary_range')
            if salary_range:
                if salary_range == '0-300000':
                    queryset = queryset.filter(salary_range_max__lte=300000)
                elif salary_range == '300000-600000':
                    queryset = queryset.filter(salary_range_min__gte=300000, salary_range_max__lte=600000)
                elif salary_range == '600000-1200000':
                    queryset = queryset.filter(salary_range_min__gte=600000, salary_range_max__lte=1200000)
                elif salary_range == '1200000-2400000':
                    queryset = queryset.filter(salary_range_min__gte=1200000, salary_range_max__lte=2400000)
                elif salary_range == '2400000+':
                    queryset = queryset.filter(salary_range_min__gte=2400000)

            posted_within = form.cleaned_data.get('posted_within')
            if posted_within:
                days_ago = timezone.now() - timedelta(days=int(posted_within))
                if model_has_field(JobOpening, 'posted_date'):
                    queryset = queryset.filter(posted_date__gte=days_ago)
                elif model_has_field(JobOpening, 'published_date'):
                    queryset = queryset.filter(published_date__gte=days_ago)

            if form.cleaned_data.get('remote_only'):
                queryset = queryset.filter(is_remote_allowed=True)

            if form.cleaned_data.get('featured_only'):
                queryset = queryset.filter(is_featured=True)

        sort_by = self.request.GET.get('sort_by', 'newest')
        if sort_by == 'newest':
            queryset = queryset.order_by(f'-{safe_order_field(JobOpening, JOB_DATE_PREFS)}')
        elif sort_by == 'salary_high':
            queryset = queryset.order_by('-salary_range_max', '-salary_range_min')
        elif sort_by == 'salary_low':
            queryset = queryset.order_by('salary_range_min', 'salary_range_max')
        elif sort_by == 'deadline' and model_has_field(JobOpening, 'application_deadline'):
            queryset = queryset.order_by('application_deadline')
        elif sort_by == 'relevance' and keyword:
            queryset = queryset.annotate(
                relevance=Count('id', filter=Q(title__icontains=keyword))
            ).order_by('-relevance', f'-{safe_order_field(JobOpening, JOB_DATE_PREFS)}')
        else:
            queryset = queryset.order_by(f'-{safe_order_field(JobOpening, JOB_DATE_PREFS)}')

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = self.get_queryset()

        # safe counts
        try:
            total_jobs = qs.count()
            featured_count = qs.filter(is_featured=True).count()
            remote_count = qs.filter(is_remote_allowed=True).count()
        except Exception:
            total_jobs = featured_count = remote_count = 0

        try:
            salary_ranges = qs.aggregate(
                min_salary=Min('salary_range_min'),
                max_salary=Max('salary_range_max'),
                avg_salary=Avg('salary_range_min')
            )
        except Exception:
            salary_ranges = {'min_salary': None, 'max_salary': None, 'avg_salary': None}

        try:
            categories = JobCategory.objects.filter(is_active=True).annotate(
                job_count=Count('jobs', filter=Q(jobs__status='open'))
            )
        except Exception:
            categories = JobCategory.objects.none()

        context.update({
            'search_form': JobSearchFilterForm(self.request.GET),
            'total_jobs': total_jobs,
            'featured_count': featured_count,
            'remote_count': remote_count,
            'salary_ranges': salary_ranges,
            'categories': categories,
            'sort_options': [
                ('newest', 'Newest First'),
                ('salary_high', 'Salary (High to Low)'),
                ('salary_low', 'Salary (Low to High)'),
                ('deadline', 'Application Deadline'),
                ('relevance', 'Relevance'),
            ],
        })
        return context


class JobDetailView(DetailView):
    """Enhanced job detail view with tracking and recommendations"""
    model = JobOpening
    template_name = 'careers/job_detail.html'
    context_object_name = 'job'

    def get_queryset(self):
        qs = JobOpening.objects.select_related('job_category', 'hiring_manager', 'recruiter')
        try:
            qs = qs.prefetch_related('saved_by', 'applications')
        except Exception:
            pass
        return qs

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        try:
            if hasattr(self.object, 'increment_views'):
                self.object.increment_views()
        except Exception:
            logger.exception("Error incrementing views", exc_info=True)

        viewed_jobs = request.session.get('viewed_jobs', [])
        if self.object.id not in viewed_jobs:
            viewed_jobs.append(self.object.id)
            request.session['viewed_jobs'] = viewed_jobs[-10:]

        request.session[f'job_view_{self.object.id}'] = timezone.now().isoformat()
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        job = self.object

        try:
            similar_qs = JobOpening.objects.filter(
                Q(job_category=job.job_category) |
                Q(required_skills__overlap=job.required_skills)
            ).exclude(id=job.id).filter(status='open')
            if model_has_field(JobOpening, 'published_date'):
                similar_qs = similar_qs.filter(published_date__lte=timezone.now())
            similar_qs = similar_qs.select_related('job_category')[:4]
            similar_jobs = serialize_jobs_for_cache(similar_qs, limit=4)
        except Exception:
            similar_jobs = []

        context['application_form'] = AdvancedJobApplicationForm()
        context['quick_apply_form'] = QuickApplyForm()

        benefits = job.benefits if isinstance(getattr(job, 'benefits', None), list) else []
        context['benefits_list'] = benefits

        skills = job.required_skills if isinstance(getattr(job, 'required_skills', None), list) else []
        context['skills_list'] = skills[:10]

        context['is_saved'] = False
        if self.request.user.is_authenticated:
            try:
                context['is_saved'] = SavedJob.objects.filter(user=self.request.user, job=job).exists()
            except Exception:
                context['is_saved'] = False

        context['application_stats'] = {
            'total': getattr(job, 'applications_count', 0),
            'conversion_rate': getattr(job, 'conversion_rate', 0),
            'views_today': getattr(job, 'views_count', 0),
        }

        context['similar_jobs'] = similar_jobs
        context['saved_job_form'] = SavedJobForm()
        return context


class JobApplicationCreateView(CreateView):
    """Enhanced application submission with validation and tracking"""
    model = JobApplication
    form_class = AdvancedJobApplicationForm
    template_name = 'careers/job_apply.html'

    def dispatch(self, request, *args, **kwargs):
        self.job = get_object_or_404(
            JobOpening,
            pk=kwargs['job_id'],
            status='open'
        )

        # Check published/posted constraints if available
        if model_has_field(JobOpening, 'published_date') and getattr(self.job, 'published_date', None):
            if self.job.published_date > timezone.now():
                messages.error(request, "This job is not published yet.")
                return redirect(self.job.get_absolute_url())

        if getattr(self.job, 'application_deadline', None) and self.job.application_deadline < timezone.now():
            messages.error(request, "The application deadline for this position has passed.")
            return redirect(self.job.get_absolute_url())

        vacancy = getattr(self.job, 'vacancy_count', None)
        if vacancy is not None and vacancy <= 0:
            messages.error(request, "This position is no longer accepting applications.")
            return redirect(self.job.get_absolute_url())

        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['initial'] = {
            'salary_currency': getattr(self.job, 'salary_currency', None),
        }
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['job'] = self.job
        context['application_steps'] = self.get_application_steps()
        return context

    def get_application_steps(self):
        return [
            {'number': 1, 'title': 'Position', 'description': 'Select Job'},
            {'number': 2, 'title': 'Application', 'description': 'Fill Details', 'active': True},
            {'number': 3, 'title': 'Documents', 'description': 'Upload Resume'},
            {'number': 4, 'title': 'Review', 'description': 'Confirm Submission'},
            {'number': 5, 'title': 'Confirmation', 'description': 'Success'},
        ]

    @transaction.atomic
    def form_valid(self, form):
        application = form.save(commit=False)
        application.job = self.job

        # Capture metadata
        application.ip_address = self.get_client_ip()
        application.user_agent = self.request.META.get('HTTP_USER_AGENT', '')
        application.device_type = self.get_device_type()

        # Capture UTM parameters
        application.utm_source = self.request.GET.get('utm_source', '')
        application.utm_medium = self.request.GET.get('utm_medium', '')
        application.utm_campaign = self.request.GET.get('utm_campaign', '')

        if getattr(self.job, 'required_skills', None) and isinstance(self.job.required_skills, list):
            application.skills_match_percentage = self.calculate_skills_match(application, self.job.required_skills)

        application.save()

        # Create event log (best-effort)
        try:
            ApplicationEventLog.objects.create(
                application=application,
                event_type='status_change',
                description=f'Application submitted for {self.job.title}',
                metadata={
                    'job_id': self.job.id,
                    'job_title': self.job.title,
                    'source': getattr(application, 'source', ''),
                },
                ip_address=application.ip_address,
            )
        except Exception:
            logger.debug("Failed to create ApplicationEventLog on form_valid", exc_info=True)

        try:
            if hasattr(self.job, 'increment_applications'):
                self.job.increment_applications()
            if hasattr(self.job, 'calculate_conversion_rate'):
                self.job.calculate_conversion_rate()
        except Exception:
            logger.debug("Failed to update job counters", exc_info=True)

        self.send_confirmation_email(application)
        self.send_admin_notification(application)

        self.request.session['last_application_id'] = application.id

        messages.success(
            self.request,
            "🎉 Your application has been submitted successfully! You'll receive a confirmation email shortly."
        )

        return redirect('careers:application_success', reference_code=application.reference_code)

    def get_client_ip(self):
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return self.request.META.get('REMOTE_ADDR')

    def get_device_type(self):
        user_agent = self.request.META.get('HTTP_USER_AGENT', '').lower()
        if 'mobile' in user_agent:
            return 'mobile'
        elif 'tablet' in user_agent:
            return 'tablet'
        else:
            return 'desktop'

    def calculate_skills_match(self, application, required_skills):
        return 75  # Placeholder - replace with real matching logic

    def send_confirmation_email(self, application):
        subject = f"Application Confirmation: {getattr(application.job, 'title', '')} at Jayarama Associates"
        context = {
            'application': application,
            'job': application.job,
            'tracking_url': self.request.build_absolute_uri(getattr(application, 'get_absolute_url', lambda: '#')()),
            'support_email': 'hr@jayaramaassociates.com',
            'company_name': 'Jayarama Associates',
        }
        try:
            html_message = render_to_string('careers/emails/application_confirmation.html', context)
            plain_message = strip_tags(html_message)
        except Exception:
            html_message = ''
            plain_message = ''

        try:
            email = EmailMultiAlternatives(subject=subject, body=plain_message,
                                           from_email=settings.DEFAULT_FROM_EMAIL, to=[application.email],
                                           reply_to=['hr@jayaramaassociates.com'])
            if html_message:
                email.attach_alternative(html_message, "text/html")
            email.send(fail_silently=False)

            ApplicationEventLog.objects.create(
                application=application,
                event_type='email_sent',
                description='Confirmation email sent to applicant',
                metadata={'email_type': 'confirmation', 'recipient': application.email}
            )
        except Exception as e:
            logger.exception("Failed to send confirmation email: %s", e)
            try:
                ApplicationEventLog.objects.create(
                    application=application,
                    event_type='email_sent',
                    description=f'Failed to send confirmation email: {str(e)}',
                    metadata={'email_type': 'confirmation', 'error': str(e)}
                )
            except Exception:
                pass

    def send_admin_notification(self, application):
        subject = f"📄 New Application: {getattr(application.job, 'title', '')} - {getattr(application, 'full_name', '')}"
        admin_emails = getattr(settings, 'CAREER_ADMIN_EMAILS', None) or [admin[1] for admin in getattr(settings, 'ADMINS', [])] or []
        if not admin_emails:
            return

        context = {
            'application': application,
            'job': application.job,
            'admin_url': self.request.build_absolute_uri(reverse('admin:careers_jobapplication_change', args=[application.id])),
        }
        try:
            html_message = render_to_string('careers/emails/admin_notification.html', context)
            plain_message = strip_tags(html_message)
        except Exception:
            html_message = ''
            plain_message = ''
        try:
            email = EmailMultiAlternatives(subject=subject, body=plain_message, from_email=settings.DEFAULT_FROM_EMAIL, to=admin_emails)
            if html_message:
                email.attach_alternative(html_message, "text/html")
            email.send(fail_silently=True)
        except Exception:
            logger.debug("Failed to send admin notification", exc_info=True)


class ApplicationSuccessView(DetailView):
    """Enhanced success page with tracking and next steps"""
    model = JobApplication
    template_name = 'careers/application_success.html'
    context_object_name = 'application'
    slug_field = 'reference_code'
    slug_url_kwarg = 'reference_code'

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        try:
            if hasattr(self.object, 'tracker'):
                self.object.tracker.increment_access()
        except Exception:
            logger.debug("Failed to increment tracker", exc_info=True)
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        application = self.object

        try:
            recommended_jobs_qs = JobOpening.objects.filter(job_category=application.job.job_category).exclude(id=application.job.id).filter(status='open')
            if model_has_field(JobOpening, 'published_date'):
                recommended_jobs_qs = recommended_jobs_qs.filter(published_date__lte=timezone.now())
            recommended_jobs = serialize_jobs_for_cache(recommended_jobs_qs, limit=3)
        except Exception:
            recommended_jobs = []

        timeline = self.get_application_timeline(application)

        checklist = [
            {'done': True, 'text': 'Application submitted'},
            {'done': getattr(application, 'consent_privacy_policy', False), 'text': 'Privacy policy accepted'},
            {'done': getattr(application, 'consent_terms', False), 'text': 'Terms & conditions accepted'},
            {'done': bool(getattr(application, 'resume', None)), 'text': 'Resume uploaded'},
            {'done': bool(getattr(application, 'cover_letter', None)), 'text': 'Cover letter uploaded'},
            {'done': bool(getattr(application, 'linkedin_url', None)), 'text': 'LinkedIn profile provided'},
        ]

        context.update({
            'job': application.job,
            'recommended_jobs': recommended_jobs,
            'timeline': timeline,
            'checklist': checklist,
            'next_steps': self.get_next_steps(),
            'support_contact': {
                'email': 'hr@jayaramaassociates.com',
                'phone': '+91 40 1234 5678',
                'hours': 'Mon-Fri, 9 AM - 6 PM IST',
            },
        })
        return context

    def get_application_timeline(self, application):
        created = getattr(application, APP_CREATED_FIELD, None) or getattr(application, 'created_at', None) or timezone.now()
        try:
            return [
                {'title': 'Application Submitted', 'description': 'Your application has been received', 'date': created, 'status': 'completed', 'icon': 'check-circle'},
                {'title': 'Application Review', 'description': 'HR team reviewing your application', 'date': created + timedelta(hours=24), 'status': 'current', 'icon': 'eye'},
                {'title': 'Initial Screening', 'description': 'Phone screening if shortlisted', 'date': created + timedelta(days=3), 'status': 'pending', 'icon': 'phone'},
                {'title': 'Technical Assessment', 'description': 'Skills assessment (if required)', 'date': created + timedelta(days=5), 'status': 'pending', 'icon': 'clipboard-check'},
                {'title': 'Interview Rounds', 'description': 'Multiple interview rounds', 'date': created + timedelta(days=7), 'status': 'pending', 'icon': 'users'},
                {'title': 'Final Decision', 'description': 'Offer or feedback', 'date': created + timedelta(days=10), 'status': 'pending', 'icon': 'award'},
            ]
        except Exception:
            return []

    def get_next_steps(self):
        return [
            {'title': 'Prepare for Interview', 'description': 'Review common interview questions and practice', 'action': 'View Interview Tips', 'url': reverse('careers:interview_tips'), 'icon': 'video'},
            {'title': 'Update Your Profile', 'description': 'Keep your resume and portfolio up to date', 'action': 'Edit Profile', 'url': '#', 'icon': 'user-edit'},
            {'title': 'Explore Other Opportunities', 'description': 'Browse similar positions at Jayarama Associates', 'action': 'View Similar Jobs', 'url': reverse('careers:job_list'), 'icon': 'search'},
        ]


class JobAlertSubscriptionView(CreateView):
    model = JobAlertSubscription
    form_class = JobAlertSubscriptionForm
    template_name = 'careers/components/alert_form.html'
    success_url = reverse_lazy('careers:home')

    def form_valid(self, form):
        subscription = form.save(commit=False)
        subscription.confirmation_token = uuid.uuid4()
        subscription.save()
        try:
            form.save_m2m()
        except Exception:
            pass

        self.send_confirmation_email(subscription)
        messages.success(self.request, "✅ Please check your email to confirm your job alert subscription.")
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Subscription created. Please check your email to confirm.', 'redirect_url': self.success_url})
        return redirect(self.success_url)

    def form_invalid(self, form):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': form.errors, 'message': 'Please correct the errors below.'}, status=400)
        messages.error(self.request, "Please correct the errors below.")
        return self.render_to_response(self.get_context_data(form=form))

    def send_confirmation_email(self, subscription):
        subject = "Confirm Your Job Alert Subscription - Jayarama Associates"
        confirm_url = self.request.build_absolute_uri(reverse('careers:confirm_alert', kwargs={'token': subscription.confirmation_token}))
        context = {'subscription': subscription, 'confirm_url': confirm_url, 'company_name': 'Jayarama Associates'}
        try:
            html_message = render_to_string('careers/emails/alert_confirmation.html', context)
            plain_message = strip_tags(html_message)
        except Exception:
            html_message = ''
            plain_message = ''
        try:
            email = EmailMultiAlternatives(subject=subject, body=plain_message, from_email=settings.DEFAULT_FROM_EMAIL, to=[subscription.email])
            if html_message:
                email.attach_alternative(html_message, "text/html")
            email.send(fail_silently=True)
        except Exception:
            logger.debug("Failed to send subscription confirmation", exc_info=True)


def confirm_alert_subscription(request, token):
    subscription = get_object_or_404(JobAlertSubscription, confirmation_token=token, is_confirmed=False)
    subscription.is_confirmed = True
    subscription.save()
    messages.success(request, "✅ Your job alert subscription has been confirmed!")
    try:
        send_mail(subject="Welcome to Jayarama Associates Job Alerts",
                  message="Thank you for subscribing to our job alerts.",
                  from_email=settings.DEFAULT_FROM_EMAIL,
                  recipient_list=[subscription.email], fail_silently=True)
    except Exception:
        pass
    return redirect('careers:home')


@method_decorator(csrf_exempt, name='dispatch')
class QuickApplyView(View):
    def post(self, request, job_id):
        job = get_object_or_404(JobOpening, pk=job_id, status='open')
        form = QuickApplyForm(request.POST, request.FILES)
        if form.is_valid():
            name = form.cleaned_data.get('name', '') or ''
            first_name = name.split()[0] if ' ' in name else name
            last_name = name.split()[-1] if ' ' in name else ''
            application = JobApplication(
                job=job, first_name=first_name, last_name=last_name,
                email=form.cleaned_data['email'], phone=form.cleaned_data['phone'],
                address_line1='Provided in quick apply', city='Not provided', state='Not provided',
                pincode='000000', country='India', total_experience=0, relevant_experience=0,
                highest_qualification='Not provided', university='Not provided', year_of_passing=0,
                resume=form.cleaned_data['resume'], consent_data_storage=True,
                consent_privacy_policy=True, consent_terms=True, source='quick_apply'
            )
            if form.cleaned_data.get('linkedin_url'):
                application.linkedin_url = form.cleaned_data['linkedin_url']
            application.save()
            try:
                send_mail(subject=f"Quick Application Submitted: {job.title}",
                          message=f"Thank you for your quick application for {job.title}. We'll contact you soon.",
                          from_email=settings.DEFAULT_FROM_EMAIL, recipient_list=[application.email], fail_silently=True)
            except Exception:
                pass
            return JsonResponse({'success': True, 'message': 'Application submitted successfully!', 'reference_code': application.reference_code, 'redirect_url': reverse('careers:application_success', kwargs={'reference_code': application.reference_code})})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


class SavedJobCreateView(LoginRequiredMixin, CreateView):
    model = SavedJob
    form_class = SavedJobForm

    @method_decorator(require_POST)
    def post(self, request, *args, **kwargs):
        job_id = request.POST.get('job_id')
        job = get_object_or_404(JobOpening, pk=job_id)
        saved_job, created = SavedJob.objects.get_or_create(user=request.user, job=job, defaults={'notes': request.POST.get('notes', '')})
        if not created:
            saved_job.notes = request.POST.get('notes', saved_job.notes)
            saved_job.save()
        return JsonResponse({'success': True, 'action': 'saved' if created else 'updated', 'message': 'Job saved successfully!' if created else 'Job updated!'})

class SavedJobListView(LoginRequiredMixin, ListView):
    model = SavedJob
    template_name = 'careers/saved_jobs_list.html'
    context_object_name = 'saved_jobs'
    paginate_by = 20
    login_url = settings.LOGIN_URL if hasattr(settings, 'LOGIN_URL') else 'login'

    def get_queryset(self):
        try:
            if model_has_field(SavedJob, 'created_at'):
                return SavedJob.objects.select_related('job').filter(user=self.request.user).order_by('-created_at')
            return SavedJob.objects.select_related('job').filter(user=self.request.user)
        except Exception:
            return SavedJob.objects.none()

class SavedJobDeleteView(LoginRequiredMixin, DeleteView):
    model = SavedJob
    template_name = 'careers/saved_job_confirm_delete.html'
    success_url = reverse_lazy('careers:saved_jobs')
    login_url = settings.LOGIN_URL if hasattr(settings, 'LOGIN_URL') else 'login'

    def get_queryset(self):
        return SavedJob.objects.filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Saved job removed.")
        return super().delete(request, *args, **kwargs)


class ApplicationTrackerView(DetailView):
    model = JobApplication
    template_name = 'careers/application_tracker.html'
    context_object_name = 'application'
    slug_field = 'reference_code'
    slug_url_kwarg = 'reference_code'

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        try:
            if hasattr(self.object, 'tracker'):
                self.object.tracker.increment_access()
        except Exception:
            pass
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        application = self.object
        try:
            history = ApplicationEventLog.objects.filter(application=application).order_by('-created_at')[:10]
        except Exception:
            history = ApplicationEventLog.objects.filter(application=application)[:10]

        status_timeline = self.get_status_timeline(application)
        estimated_timeline = self.get_estimated_timeline(application)
        can_contact = getattr(self, 'can_contact_support', lambda app: False)(application)
        next_update_days = getattr(self, 'get_next_update_days', lambda app: None)(application)

        context.update({
            'history': history,
            'status_timeline': status_timeline,
            'estimated_timeline': estimated_timeline,
            'can_contact': can_contact,
            'next_update_days': next_update_days,
        })
        return context

    def get_status_timeline(self, application):
        status_changes = ApplicationEventLog.objects.filter(application=application, event_type='status_change').order_by('created_at')
        timeline = []
        for event in status_changes:
            notes = ''
            try:
                notes = event.metadata.get('notes', '') if isinstance(event.metadata, dict) else ''
            except Exception:
                notes = ''
            timeline.append({'status': event.description.split(' to ')[-1] if ' to ' in event.description else event.description, 'date': event.created_at, 'notes': notes})
        return timeline

    def get_estimated_timeline(self, application):
        base_date = getattr(application, 'status_changed_at', None) or getattr(application, APP_CREATED_FIELD, None) or timezone.now()
        timelines = {
            'applied': [{'step': 'Initial Review', 'estimated_days': 3}, {'step': 'HR Screening', 'estimated_days': 7}, {'step': 'Technical Assessment', 'estimated_days': 10}, {'step': 'Final Interview', 'estimated_days': 14}, {'step': 'Decision', 'estimated_days': 21}],
            'shortlisted': [{'step': 'Interview Scheduling', 'estimated_days': 3}, {'step': 'First Interview', 'estimated_days': 7}, {'step': 'Second Interview', 'estimated_days': 10}, {'step': 'Final Decision', 'estimated_days': 14}],
            'interviewing': [{'step': 'Interview Completion', 'estimated_days': 7}, {'step': 'Feedback Collection', 'estimated_days': 10}, {'step': 'Decision', 'estimated_days': 14}],
        }
        return timelines.get(getattr(application, 'status', ''), [])


class CareersSitemapView(View):
    def get(self, request):
        try:
            jobs = JobOpening.objects.filter(status='open')
            if model_has_field(JobOpening, 'published_date'):
                jobs = jobs.filter(published_date__lte=timezone.now())
            jobs = list(jobs.values('id', 'title', 'slug', JOB_UPDATED_FIELD or 'id'))
        except Exception:
            jobs = []

        try:
            categories = list(JobCategory.objects.filter(is_active=True).values('id', 'name', 'slug'))
        except Exception:
            categories = []

        sitemap = {'jobs': jobs, 'categories': categories, 'static_pages': [{'url': reverse('careers:home'), 'priority': 1.0}, {'url': reverse('careers:job_list'), 'priority': 0.9}], 'last_updated': timezone.now().isoformat()}
        return JsonResponse(sitemap, safe=False)


class JobAnalyticsView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'careers/analytics/dashboard.html'

    def test_func(self):
        return self.request.user.has_perm('careers.can_view_analytics')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)

        try:
            stats = {
                'total_jobs': JobOpening.objects.count(),
                'open_jobs': JobOpening.objects.filter(status='open').count(),
                'total_applications': JobApplication.objects.count(),
                'applications_today': JobApplication.objects.filter(created_at__date=today).count() if model_has_field(JobApplication, 'created_at') else JobApplication.objects.count(),
                'applications_week': JobApplication.objects.filter(created_at__date__gte=week_ago).count() if model_has_field(JobApplication, 'created_at') else JobApplication.objects.count(),
                'conversion_rate': JobOpening.objects.aggregate(avg=Avg('conversion_rate'))['avg'] or 0,
            }
        except Exception:
            stats = {'total_jobs': 0, 'open_jobs': 0, 'total_applications': 0, 'applications_today': 0, 'applications_week': 0, 'conversion_rate': 0}

        try:
            top_jobs = JobOpening.objects.filter(status='open').annotate(application_rate=Case(When(views_count__gt=0, then=(F('applications_count') * Value(100.0)) / F('views_count')), default=Value(0), output_field=FloatField())).order_by('-application_rate')[:5]
        except Exception:
            top_jobs = JobOpening.objects.none()

        try:
            total_app_count = JobApplication.objects.count() or 1
            sources = JobApplication.objects.values('source').annotate(count=Count('id'), percentage=(Count('id') * 100) / total_app_count).order_by('-count')
        except Exception:
            sources = []

        timeline_data = self.get_timeline_data(month_ago)

        context.update({'stats': stats, 'top_jobs': top_jobs, 'sources': sources, 'timeline_data': timeline_data, 'date_ranges': {'today': today, 'week_ago': week_ago, 'month_ago': month_ago}})
        return context

    def get_timeline_data(self, start_date):
        dates, applications, views = [], [], []
        current_date = start_date
        today = timezone.now().date()
        while current_date <= today:
            try:
                date_apps = JobApplication.objects.filter(created_at__date=current_date).count() if model_has_field(JobApplication, 'created_at') else 0
            except Exception:
                date_apps = 0
            try:
                date_views = JobOpening.objects.filter(posted_date__date=current_date).aggregate(total=Sum('views_count'))['total'] or 0 if model_has_field(JobOpening, 'posted_date') else 0
            except Exception:
                date_views = 0
            dates.append(current_date.strftime('%Y-%m-%d'))
            applications.append(date_apps)
            views.append(date_views)
            current_date += timedelta(days=1)
        return {'dates': dates, 'applications': applications, 'views': views}


@require_GET
def search_suggestions(request):
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'suggestions': []})

    try:
        job_titles = list(JobOpening.objects.filter(title__icontains=query, status='open').values_list('title', flat=True).distinct()[:5])
    except Exception:
        job_titles = []

    skills = set()
    try:
        jobs_with_skills = JobOpening.objects.filter(required_skills__icontains=query, status='open')[:10]
        for job in jobs_with_skills:
            if job.required_skills and isinstance(job.required_skills, list):
                for skill in job.required_skills:
                    if query.lower() in skill.lower():
                        skills.add(skill)
    except Exception:
        pass

    try:
        locations = list(JobOpening.objects.filter(location__icontains=query, status='open').values_list('location', flat=True).distinct()[:5])
    except Exception:
        locations = []

    suggestions = {'jobs': job_titles, 'skills': list(skills)[:5], 'locations': locations}
    return JsonResponse(suggestions)


@require_POST
@csrf_exempt
def submit_feedback(request):
    try:
        data = json.loads(request.body)
    except Exception:
        data = {}
    # TODO: persist feedback
    return JsonResponse({'success': True, 'message': 'Thank you for your feedback!'})


@csrf_exempt
def linkedin_webhook(request):
    if request.method == 'GET':
        challenge = request.GET.get('challenge') or request.GET.get('hub.challenge')
        if challenge:
            return HttpResponse(challenge, content_type='text/plain')
        return HttpResponse('OK', content_type='text/plain')

    if request.method == 'POST':
        raw_body = request.body or b''
        signature_header = request.META.get('HTTP_X_LI_SIGNATURE') or request.META.get('HTTP_X_HUB_SIGNATURE') or request.META.get('HTTP_X_SIGNATURE')
        secret = getattr(settings, 'LINKEDIN_WEBHOOK_SECRET', None)
        if secret and signature_header:
            try:
                computed = hmac.new(key=secret.encode('utf-8'), msg=raw_body, digestmod=hashlib.sha256).hexdigest()
                received = signature_header.split('=')[-1].strip()
                if not hmac.compare_digest(computed, received):
                    logger.warning("LinkedIn webhook signature mismatch.")
                    return HttpResponse(status=403)
            except Exception:
                logger.exception("Error while verifying LinkedIn webhook signature")
                return HttpResponse(status=500)
        try:
            payload = json.loads(raw_body.decode('utf-8')) if raw_body else {}
        except Exception:
            payload = {}
        logger.info("LinkedIn webhook received: %s", json.dumps(payload)[:2000])
        try:
            ApplicationEventLog.objects.create(application=None, event_type='linkedin_webhook', description=f'LinkedIn webhook received: keys={list(payload.keys()) if isinstance(payload, dict) else []}', metadata=payload if isinstance(payload, dict) else {'raw': str(payload)}, performed_by=None)
        except Exception:
            logger.debug("Could not save ApplicationEventLog for LinkedIn webhook", exc_info=True)
        return HttpResponse('Received', status=200)
    return HttpResponse(status=405)


@csrf_exempt
@require_POST
def indeed_webhook(request):
    try:
        body = request.body.decode('utf-8')
        if not body:
            logger.warning("Indeed webhook received empty body")
            return HttpResponseBadRequest("Empty body")
        data = json.loads(body)
    except json.JSONDecodeError:
        logger.exception("Invalid JSON from Indeed webhook")
        return HttpResponseBadRequest("Invalid JSON")
    logger.info("Indeed webhook payload: %s", data)
    try:
        ApplicationEventLog.objects.create(application=None, event_type='indeed_webhook', description='Indeed webhook', metadata=data)
    except Exception:
        pass
    return JsonResponse({"status": "ok"})


@csrf_exempt
def calendar_webhook(request):
    if request.method == "GET":
        challenge = request.GET.get("challenge") or request.GET.get("hub.challenge")
        if challenge:
            logger.info("Calendar webhook verification request received: challenge=%s", challenge)
            return HttpResponse(challenge, content_type="text/plain")
        return JsonResponse({"status": "ok", "method": "GET"})

    if request.method == "POST":
        headers_of_interest = {
            "x-goog-resource-state": request.META.get("HTTP_X_GOOG_RESOURCE_STATE"),
            "x-goog-channel-id": request.META.get("HTTP_X_GOOG_CHANNEL_ID"),
            "x-hook-signature": request.META.get("HTTP_X_HOOK_SIGNATURE"),
            "x-ms-notification-id": request.META.get("HTTP_AZURE_NOTIFICATION_ID"),
        }
        logger.debug("Calendar webhook headers: %s", headers_of_interest)
        try:
            body = request.body.decode("utf-8")
            if not body:
                logger.warning("Calendar webhook POST with empty body")
                return HttpResponseBadRequest("Empty body")
            payload = json.loads(body)
        except json.JSONDecodeError:
            logger.exception("Calendar webhook: invalid JSON")
            return HttpResponseBadRequest("Invalid JSON")
        logger.info("Calendar webhook payload: %s", payload)
        try:
            ApplicationEventLog.objects.create(application=None, event_type='calendar_webhook', description='Calendar webhook', metadata=payload)
        except Exception:
            logger.debug("Could not save ApplicationEventLog for Calendar webhook", exc_info=True)
        return JsonResponse({"status": "received"})
    return HttpResponse(status=405)
