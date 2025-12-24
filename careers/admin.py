# careers/admin.py
from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.db.models import Count, Q, Avg, F, Case, When, Value, FloatField
from django.utils.html import format_html, mark_safe
from django.urls import reverse
from django.utils import timezone
from django.contrib import messages
from django.http import HttpResponse
import csv
import json

from .models import (
    JobCategory, JobOpening, JobApplication,
    JobAlertSubscription, ApplicationEventLog, SavedJob
)

# Helper util
def _first_existing_attr(instance, *attr_names):
    """Return first non-None attribute value from instance for given names."""
    for name in attr_names:
        if hasattr(instance, name):
            val = getattr(instance, name)
            if val is not None:
                return val
    return None

# Custom filters
class StatusFilter(SimpleListFilter):
    title = 'status'
    parameter_name = 'status'
    
    def lookups(self, request, model_admin):
        return [
            ('open', 'Open Positions'),
            ('closing_soon', 'Closing Soon (< 7 days)'),
            ('expired', 'Expired'),
            ('draft', 'Draft'),
            ('paused', 'Paused'),
            ('urgent', 'Urgent Priority'),
        ]
    
    def queryset(self, request, queryset):
        if self.value() == 'open':
            return queryset.filter(status='open')
        elif self.value() == 'closing_soon':
            deadline = timezone.now().date() + timezone.timedelta(days=7)
            return queryset.filter(
                status='open',
                application_deadline__lte=deadline
            )
        elif self.value() == 'expired':
            return queryset.filter(
                Q(application_deadline__lt=timezone.now().date()) |
                Q(vacancy_count=0)
            )
        elif self.value() == 'draft':
            return queryset.filter(status='draft')
        elif self.value() == 'paused':
            return queryset.filter(status='paused')
        elif self.value() == 'urgent':
            return queryset.filter(priority='urgent')

class ApplicationStatusFilter(SimpleListFilter):
    title = 'application status'
    parameter_name = 'app_status'
    
    def lookups(self, request, model_admin):
        return [
            ('new', 'New (Last 7 days)'),
            ('shortlisted', 'Shortlisted'),
            ('interview', 'In Interview Process'),
            ('rejected', 'Rejected'),
            ('hired', 'Hired'),
            ('no_action', 'No Action > 14 days'),
        ]
    
    def queryset(self, request, queryset):
        if self.value() == 'new':
            week_ago = timezone.now() - timezone.timedelta(days=7)
            return queryset.filter(created_at__gte=week_ago)
        elif self.value() == 'shortlisted':
            return queryset.filter(status__in=['shortlisted', 'interviewing'])
        elif self.value() == 'interview':
            return queryset.filter(status__startswith='interview_')
        elif self.value() == 'rejected':
            return queryset.filter(status='rejected')
        elif self.value() == 'hired':
            return queryset.filter(status__in=['accepted', 'offer_extended'])
        elif self.value() == 'no_action':
            two_weeks_ago = timezone.now() - timezone.timedelta(days=14)
            return queryset.filter(
                status='applied',
                created_at__lte=two_weeks_ago
            )

# Inline admins
class JobApplicationInline(admin.TabularInline):
    model = JobApplication
    extra = 0
    fields = ['full_name', 'email', 'status_badge', 'application_date']
    readonly_fields = ['full_name', 'email', 'status_badge', 'application_date']
    
    def status_badge(self, obj):
        colors = {
            'applied': 'blue',
            'reviewed': 'orange',
            'shortlisted': 'green',
            'interviewing': 'purple',
            'rejected': 'red',
            'accepted': 'darkgreen',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 12px; font-size: 12px;">{}</span>',
            colors.get(obj.status, 'gray'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def application_date(self, obj):
        """
        Inline callable for application date. Falls back to common fields.
        """
        dt = _first_existing_attr(obj, 'application_date', 'applied_at', 'created_at', 'created', 'timestamp')
        if dt and hasattr(dt, 'strftime'):
            return timezone.localtime(dt).strftime('%Y-%m-%d %H:%M')
        return dt or ''
    application_date.short_description = 'Application Date'
    
    def has_add_permission(self, request, obj=None):
        return False

class ApplicationEventLogInline(admin.TabularInline):
    model = ApplicationEventLog
    extra = 0
    fields = ['event_type', 'description', 'created_at', 'performed_by']
    readonly_fields = ['event_type', 'description', 'created_at', 'performed_by']
    
    def has_add_permission(self, request, obj=None):
        return False

# Main admins
@admin.register(JobCategory)
class JobCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'active_jobs_count', 'display_order', 'is_active']
    list_editable = ['display_order', 'is_active']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    list_filter = ['is_active']
    actions = ['activate_categories', 'deactivate_categories']
    
    def active_jobs_count(self, obj):
        return getattr(obj, 'active_jobs_count', 0)
    active_jobs_count.short_description = 'Active Jobs'
    
    def activate_categories(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} categories activated.')
    activate_categories.short_description = "Activate selected categories"
    
    def deactivate_categories(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} categories deactivated.')
    deactivate_categories.short_description = "Deactivate selected categories"

@admin.register(JobOpening)
class JobOpeningAdmin(admin.ModelAdmin):
    # Include raw 'priority' in list_display so list_editable can use it.
    list_display = [
        'title', 'reference_id', 'job_category', 'job_type',
        'priority', 'priority_badge', 'status_badge', 'applications_count',
        'views_count', 'conversion_rate', 'posted_date', 'action_links'
    ]
    list_display_links = ['title']
    list_filter = [StatusFilter, 'job_type', 'experience_level', 'job_category', 'priority']
    search_fields = ['title', 'reference_id', 'description', 'location']
    list_editable = ['priority']
    readonly_fields = [
        'views_count', 'applications_count', 'conversion_rate',
        'posted_date', 'last_modified', 'created_at'
    ]
    filter_horizontal = []
    date_hierarchy = 'posted_date'
    actions = [
        'export_as_csv', 'export_as_json', 'mark_as_featured',
        'close_positions', 'publish_jobs', 'duplicate_jobs'
    ]
    inlines = [JobApplicationInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'slug', 'reference_id', 'job_category', 'short_description')
        }),
        ('Job Details', {
            'fields': (
                'job_type', 'experience_level', 'location', 'department', 'team',
                'detailed_description', 'key_responsibilities', 'qualifications',
                'required_skills', 'preferred_skills', 'tools_technologies'
            )
        }),
        ('Compensation & Benefits', {
            'fields': (
                'salary_range_min', 'salary_range_max', 'salary_currency',
                'salary_period', 'is_salary_negotiable', 'show_salary', 'benefits'
            )
        }),
        ('Application Details', {
            'fields': (
                'application_deadline', 'vacancy_count', 'estimated_duration'
            )
        }),
        ('Status & Settings', {
            'fields': (
                'status', 'priority', 'is_featured', 'is_remote_allowed',
                'requires_travel', 'travel_percentage'
            )
        }),
        ('Metrics', {
            'fields': (
                'views_count', 'applications_count', 'shortlisted_count',
                'conversion_rate', 'share_count'
            )
        }),
        ('Dates', {
            'fields': ('posted_date', 'published_date', 'closed_date')
        }),
        ('Workflow', {
            'fields': ('hiring_manager', 'recruiter', 'approver'),
            'classes': ('collapse',)
        }),
        ('SEO & Sharing', {
            'fields': ('meta_title', 'meta_description', 'og_image'),
            'classes': ('collapse',)
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'open': 'green',
            'closed': 'red',
            'draft': 'gray',
            'paused': 'orange',
            'review': 'blue',
            'archived': 'darkgray',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 12px; font-size: 12px;">{}</span>',
            colors.get(obj.status, 'gray'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def priority_badge(self, obj):
        colors = {
            'urgent': 'red',
            'high': 'orange',
            'normal': 'green',
            'low': 'blue',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 12px; font-size: 12px;">{}</span>',
            colors.get(obj.priority, 'gray'),
            obj.get_priority_display() if hasattr(obj, 'get_priority_display') else obj.priority
        )
    priority_badge.short_description = 'Priority'
    
    def conversion_rate(self, obj):
        try:
            return f"{obj.conversion_rate:.1f}%"
        except Exception:
            return "0.0%"
    conversion_rate.short_description = 'Conv. Rate'
    
    def action_links(self, obj):
        links = [
            f'<a href="{reverse("admin:careers_jobopening_change", args=[obj.id])}">Edit</a>',
            f'<a href="{obj.get_absolute_url()}" target="_blank">View</a>',
            f'<a href="{reverse("admin:careers_jobapplication_changelist")}?job__id__exact={obj.id}">Apps</a>',
        ]
        return mark_safe(' | '.join(links))
    action_links.short_description = 'Actions'
    
    def export_as_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename=jobs_export.csv'
        
        writer = csv.writer(response)
        writer.writerow([
            'Reference ID', 'Title', 'Category', 'Type', 'Location',
            'Status', 'Posted Date', 'Applications', 'Views', 'Conversion Rate'
        ])
        
        for job in queryset:
            writer.writerow([
                job.reference_id, job.title, getattr(job.job_category, 'name', ''),
                job.get_job_type_display() if hasattr(job, 'get_job_type_display') else job.job_type,
                job.location,
                job.get_status_display() if hasattr(job, 'get_status_display') else job.status,
                job.posted_date.strftime('%Y-%m-%d') if getattr(job, 'posted_date', None) else '',
                getattr(job, 'applications_count', 0) or 0,
                getattr(job, 'views_count', 0) or 0,
                f"{(job.conversion_rate or 0):.1f}%"
            ])
        
        return response
    export_as_csv.short_description = "Export selected jobs to CSV"
    
    def export_as_json(self, request, queryset):
        data = []
        for job in queryset:
            data.append({
                'id': job.id,
                'reference_id': job.reference_id,
                'title': job.title,
                'category': getattr(job.job_category, 'name', ''),
                'type': job.get_job_type_display() if hasattr(job, 'get_job_type_display') else job.job_type,
                'location': job.location,
                'status': job.get_status_display() if hasattr(job, 'get_status_display') else job.status,
                'posted_date': job.posted_date.isoformat() if getattr(job, 'posted_date', None) else None,
                'applications': getattr(job, 'applications_count', 0) or 0,
                'views': getattr(job, 'views_count', 0) or 0,
                'conversion_rate': float(job.conversion_rate or 0),
            })
        
        response = HttpResponse(json.dumps(data, indent=2), content_type='application/json')
        response['Content-Disposition'] = 'attachment; filename=jobs_export.json'
        return response
    export_as_json.short_description = "Export selected jobs to JSON"
    
    def mark_as_featured(self, request, queryset):
        updated = queryset.update(is_featured=True)
        self.message_user(request, f'{updated} jobs marked as featured.')
    mark_as_featured.short_description = "Mark as featured"
    
    def close_positions(self, request, queryset):
        updated = queryset.update(status='closed', closed_date=timezone.now())
        self.message_user(request, f'{updated} jobs closed.')
    close_positions.short_description = "Close selected positions"
    
    def publish_jobs(self, request, queryset):
        updated = queryset.filter(status='draft').update(
            status='open',
            published_date=timezone.now()
        )
        self.message_user(request, f'{updated} jobs published.')
    publish_jobs.short_description = "Publish draft jobs"
    
    def duplicate_jobs(self, request, queryset):
        count = 0
        for job in queryset:
            original_ref = job.reference_id or ''
            job.pk = None
            job.reference_id = f"{original_ref}-COPY"
            job.title = f"{job.title} (Copy)"
            job.status = 'draft'
            job.views_count = 0
            job.applications_count = 0
            job.conversion_rate = 0
            job.save()
            count += 1
        
        self.message_user(request, f'{count} jobs duplicated as drafts.')
    duplicate_jobs.short_description = "Duplicate selected jobs"
    
    def posted_date(self, obj):
        """
        If model has posted_date use it, otherwise fallback to created_at / published_date.
        """
        dt = _first_existing_attr(obj, 'posted_date', 'published_date', 'created_at', 'created')
        if dt and hasattr(dt, 'strftime'):
            return timezone.localtime(dt).strftime('%Y-%m-%d')
        return dt or ''
    posted_date.short_description = 'Posted Date'
    if hasattr(JobOpening, 'posted_date'):
        posted_date.admin_order_field = 'posted_date'
    
    def last_modified(self, obj):
        """
        Return a last-modified timestamp for the JobOpening.
        Falls back to common fields: 'last_modified', 'updated_at', 'modified_at', 'updated'
        """
        dt = _first_existing_attr(obj, 'last_modified', 'updated_at', 'modified_at', 'updated')
        if dt and hasattr(dt, 'strftime'):
            return timezone.localtime(dt).strftime('%Y-%m-%d %H:%M:%S')
        return dt or ''
    last_modified.short_description = 'Last modified'
    if hasattr(JobOpening, 'updated_at'):
        last_modified.admin_order_field = 'updated_at'


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = [
        'full_name', 'email', 'job_title', 'status_badge',
        'rating_stars', 'experience', 'skills_match', 'application_date', 'action_links'
    ]
    list_filter = [
        ApplicationStatusFilter, 'status', 'rating', 'source',
        'job__job_category', 'job__job_type'
    ]
    search_fields = [
        'first_name', 'last_name', 'email', 'phone',
        'job__title', 'job__reference_id', 'reference_code'
    ]
    readonly_fields = [
        'application_date', 'status_changed_at', 'ip_address',
        'user_agent', 'device_type', 'reference_code', 'application_id'
    ]
    list_per_page = 50
    actions = [
        'export_applications_csv', 'mark_as_shortlisted',
        'mark_as_rejected', 'schedule_interview', 'send_email'
    ]
    inlines = [ApplicationEventLogInline]
    
    fieldsets = (
        ('Application Information', {
            'fields': ('job', 'reference_code', 'status', 'status_changed_at', 'source')
        }),
        ('Personal Information', {
            'fields': (
                'first_name', 'last_name', 'email', 'phone', 'alternate_phone'
            )
        }),
        ('Address', {
            'fields': (
                'address_line1', 'address_line2',
                'city', 'state', 'pincode', 'country'
            )
        }),
        ('Professional Information', {
            'fields': (
                'current_company', 'current_position',
                'current_salary', 'expected_salary', 'salary_currency',
                'notice_period', 'notice_period_days'
            )
        }),
        ('Experience & Education', {
            'fields': (
                'total_experience', 'relevant_experience', 'experience_summary',
                'highest_qualification', 'university', 'year_of_passing', 'cgpa',
                'additional_certifications'
            )
        }),
        ('Documents & Links', {
            'fields': (
                'resume', 'cover_letter', 'portfolio_url',
                'linkedin_url', 'github_url'
            )
        }),
        ('Evaluation', {
            'fields': (
                'rating', 'skills_match_percentage', 'cultural_fit_score',
                'evaluation_notes', 'status_notes'
            )
        }),
        ('Interview & Offer', {
            'fields': ('interview_schedule', 'interview_feedback', 'offer_details'),
            'classes': ('collapse',)
        }),
        ('Consent', {
            'fields': (
                'consent_data_storage', 'consent_future_opportunities',
                'consent_privacy_policy', 'consent_terms'
            ),
            'classes': ('collapse',)
        }),
        ('Technical Info', {
            'fields': ('ip_address', 'user_agent', 'device_type',
                      'utm_source', 'utm_medium', 'utm_campaign'),
            'classes': ('collapse',)
        }),
    )
    
    def job_title(self, obj):
        if not getattr(obj, 'job', None):
            return ''
        url = reverse('admin:careers_jobopening_change', args=[obj.job.id])
        return format_html('<a href="{}">{}</a>', url, obj.job.title)
    job_title.short_description = 'Job Position'
    
    def status_badge(self, obj):
        status_key = obj.status.split('_')[0] if obj.status and '_' in obj.status else (obj.status or '')
        colors = {
            'applied': 'blue',
            'reviewed': 'orange',
            'shortlisted': 'green',
            'interview': 'purple',
            'rejected': 'red',
            'accepted': 'darkgreen',
            'offer': 'teal',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 12px; font-size: 12px;">{}</span>',
            colors.get(status_key, 'gray'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def experience(self, obj):
        return f"{getattr(obj, 'total_experience', 0) or 0} yrs ({getattr(obj, 'relevant_experience', 0) or 0} relevant)"
    experience.short_description = 'Experience'
    
    def rating_stars(self, obj):
        try:
            rating = int(getattr(obj, 'rating', 0) or 0)
        except Exception:
            rating = 0
        stars = '★' * rating + '☆' * (5 - rating)
        color = {
            5: 'gold', 4: 'goldenrod', 3: 'orange', 2: 'coral', 1: 'lightcoral', 0: 'gray'
        }.get(rating, 'gray')
        return format_html(
            '<span style="color: {}; font-size: 14px;">{}</span>',
            color, stars
        )
    rating_stars.short_description = 'Rating'
    
    def skills_match(self, obj):
        try:
            val = int(getattr(obj, 'skills_match_percentage', 0) or 0)
        except Exception:
            val = 0
        color = 'green' if val >= 80 else 'orange' if val >= 60 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}%</span>',
            color, val
        )
    skills_match.short_description = 'Skills Match'
    
    def action_links(self, obj):
        links = []
        
        # View resume
        if getattr(obj, 'resume', None):
            try:
                links.append(f'<a href="{obj.resume.url}" target="_blank">Resume</a>')
            except Exception:
                pass
        
        # Email applicant
        if getattr(obj, 'email', None):
            links.append(f'<a href="mailto:{obj.email}">Email</a>')
        
        # View in tracker (guarded)
        if getattr(obj, 'reference_code', None):
            try:
                tracker_url = reverse('careers:application_tracker', kwargs={'reference_code': obj.reference_code})
                links.append(f'<a href="{tracker_url}" target="_blank">Tracker</a>')
            except Exception:
                pass
        
        return mark_safe(' | '.join(links))
    action_links.short_description = 'Actions'
    
    def application_date(self, obj):
        """
        Admin callable that returns application date.
        Falls back to common timestamp fields: 'application_date', 'applied_at', 'created_at', 'created'
        """
        dt = _first_existing_attr(obj, 'application_date', 'applied_at', 'created_at', 'created', 'timestamp')
        if dt and hasattr(dt, 'strftime'):
            return timezone.localtime(dt).strftime('%Y-%m-%d %H:%M:%S')
        return dt or ''
    application_date.short_description = 'Application Date'
    if hasattr(JobApplication, 'created_at'):
        application_date.admin_order_field = 'created_at'
    
    def export_applications_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="applications_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Reference', 'Name', 'Email', 'Phone', 'Job Title',
            'Status', 'Experience', 'Current Company', 'Rating',
            'Skills Match %', 'Application Date'
        ])
        
        for app in queryset:
            writer.writerow([
                getattr(app, 'reference_code', ''),
                getattr(app, 'full_name', ''),
                getattr(app, 'email', ''),
                getattr(app, 'phone', ''),
                app.job.title if getattr(app, 'job', None) else '',
                app.get_status_display() if hasattr(app, 'get_status_display') else getattr(app, 'status', ''),
                f"{getattr(app, 'total_experience', 0)} years",
                getattr(app, 'current_company', 'N/A') or 'N/A',
                getattr(app, 'rating', 0) or 0,
                f"{(getattr(app, 'skills_match_percentage', 0) or 0)}%",
                getattr(app, 'application_date', '').strftime('%Y-%m-%d %H:%M') if getattr(app, 'application_date', None) and hasattr(getattr(app, 'application_date'), 'strftime') else getattr(app, 'created_at', '') and getattr(app, 'created_at').strftime('%Y-%m-%d %H:%M') if getattr(app, 'created_at', None) and hasattr(getattr(app, 'created_at'), 'strftime') else ''
            ])
        
        return response
    export_applications_csv.short_description = "Export applications to CSV"
    
    def mark_as_shortlisted(self, request, queryset):
        updated = queryset.update(status='shortlisted')
        self.message_user(request, f'{updated} applications marked as shortlisted.')
    mark_as_shortlisted.short_description = "Mark as shortlisted"
    
    def mark_as_rejected(self, request, queryset):
        updated = queryset.update(status='rejected')
        self.message_user(request, f'{updated} applications marked as rejected.')
    mark_as_rejected.short_description = "Mark as rejected"
    
    def schedule_interview(self, request, queryset):
        # This would typically redirect to a scheduling form
        updated = queryset.update(status='interview_scheduled')
        self.message_user(request, f'{updated} applications marked for interview scheduling.')
    schedule_interview.short_description = "Schedule interview"
    
    def send_email(self, request, queryset):
        # This would open an email composition dialog
        emails = list(queryset.values_list('email', flat=True).distinct())
        self.message_user(request, f'Ready to email {len(emails)} applicants. (Emails: {len(emails)})')
    send_email.short_description = "Send email to selected"

@admin.register(JobAlertSubscription)
class JobAlertSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['email', 'name', 'frequency', 'is_active', 
                    'is_confirmed', 'notification_count', 'created_at']
    list_filter = ['is_active', 'is_confirmed', 'frequency']
    search_fields = ['email', 'name']
    readonly_fields = ['created_at', 'confirmation_token', 'last_notified']
    actions = ['resend_confirmation', 'export_subscribers']
    
    def resend_confirmation(self, request, queryset):
        for subscription in queryset.filter(is_confirmed=False):
            # Resend confirmation email logic (implement real logic if available)
            pass
        self.message_user(request, f'Confirmation emails resent to {queryset.count()} subscribers.')
    resend_confirmation.short_description = "Resend confirmation email"
    
    def export_subscribers(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="job_alert_subscribers.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Email', 'Name', 'Frequency', 'Active', 'Confirmed', 'Created'])
        
        for sub in queryset:
            writer.writerow([
                sub.email,
                sub.name,
                sub.frequency,
                'Yes' if sub.is_active else 'No',
                'Yes' if sub.is_confirmed else 'No',
                sub.created_at.strftime('%Y-%m-%d') if getattr(sub, 'created_at', None) else ''
            ])
        
        return response
    export_subscribers.short_description = "Export subscribers to CSV"

@admin.register(ApplicationEventLog)
class ApplicationEventLogAdmin(admin.ModelAdmin):
    list_display = ['application', 'event_type', 'description', 'created_at', 'performed_by']
    list_filter = ['event_type', 'created_at']
    search_fields = ['application__reference_code', 'application__full_name', 'description']
    readonly_fields = ['application', 'event_type', 'description', 'metadata', 
                       'performed_by', 'ip_address', 'created_at']
    date_hierarchy = 'created_at'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False

@admin.register(SavedJob)
class SavedJobAdmin(admin.ModelAdmin):
    list_display = ['user', 'job', 'created_at', 'reminder_date']
    list_filter = ['created_at', 'reminder_date']
    search_fields = ['user__email', 'job__title', 'notes']
    raw_id_fields = ['user', 'job']
    
    def has_add_permission(self, request):
        return False

# Register analytics dashboard
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

@staff_member_required
def careers_analytics(request):
    """Custom analytics dashboard"""
    # Calculate metrics
    total_jobs = JobOpening.objects.count()
    open_jobs = JobOpening.objects.filter(status='open').count()
    total_applications = JobApplication.objects.count()
    
    # Recent applications
    recent_apps = JobApplication.objects.select_related('job').order_by('-created_at')[:10]
    
    # Job performance - safe division for views_count == 0
    job_performance = JobOpening.objects.annotate(
        application_rate=Case(
            When(views_count__gt=0, then=(F('applications_count') * Value(100.0)) / F('views_count')),
            default=Value(0),
            output_field=FloatField()
        )
    ).order_by('-application_rate')[:10]
    
    context = {
        'total_jobs': total_jobs,
        'open_jobs': open_jobs,
        'total_applications': total_applications,
        'recent_apps': recent_apps,
        'job_performance': job_performance,
    }
    
    return render(request, 'admin/careers/analytics.html', context)

# Add analytics to admin index
admin.site.index_template = 'admin/careers_index.html'
