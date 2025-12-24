# careers/models.py
from django.db import models
from django.utils import timezone
from django.core.validators import FileExtensionValidator, MinValueValidator, MaxValueValidator
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from django.urls import reverse
import uuid
from decimal import Decimal

User = get_user_model()

class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        abstract = True


class JobCategory(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, default='briefcase')
    color = models.CharField(max_length=7, default='#f59e0b')
    display_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Job Categories"
        ordering = ['display_order', 'name']
        indexes = [
            models.Index(fields=['slug', 'is_active']),
        ]

    def __str__(self):
        return self.name

    def _generate_unique_slug(self, base):
        """
        Ensure slug uniqueness for JobCategory.
        """
        slug_candidate = base
        index = 1
        while JobCategory.objects.filter(slug=slug_candidate).exclude(pk=self.pk).exists():
            slug_candidate = f"{base}-{index}"
            index += 1
        return slug_candidate

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or str(uuid.uuid4())[:8]
            self.slug = self._generate_unique_slug(base)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('careers:job_list_by_category', kwargs={'slug': self.slug})

    @property
    def active_jobs_count(self):
        return self.jobs.filter(status='open').count()


class JobOpening(TimeStampedModel):
    JOB_TYPE_CHOICES = [
        ('full_time', 'Full Time'),
        ('part_time', 'Part Time'),
        ('contract', 'Contract'),
        ('internship', 'Internship'),
        ('remote', 'Remote'),
        ('hybrid', 'Hybrid'),
        ('freelance', 'Freelance'),
    ]

    EXPERIENCE_LEVEL_CHOICES = [
        ('intern', 'Internship (0-1 years)'),
        ('entry', 'Entry Level (1-3 years)'),
        ('mid', 'Mid Level (3-7 years)'),
        ('senior', 'Senior Level (7-12 years)'),
        ('lead', 'Lead (12-15 years)'),
        ('executive', 'Executive (15+ years)'),
    ]

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('review', 'Under Review'),
        ('open', 'Open'),
        ('paused', 'Paused'),
        ('closed', 'Closed'),
        ('archived', 'Archived'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    # Core Information
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    reference_id = models.CharField(max_length=20, unique=True, db_index=True, blank=True)
    job_category = models.ForeignKey(JobCategory, on_delete=models.PROTECT, related_name='jobs')
    job_type = models.CharField(max_length=20, choices=JOB_TYPE_CHOICES, default='full_time')
    experience_level = models.CharField(max_length=20, choices=EXPERIENCE_LEVEL_CHOICES, default='mid')
    location = models.CharField(max_length=200)
    department = models.CharField(max_length=100)
    team = models.CharField(max_length=100, blank=True)

    # Compensation & Benefits
    salary_range_min = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    salary_range_max = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    salary_currency = models.CharField(max_length=10, default='INR')
    salary_period = models.CharField(max_length=20, default='year', choices=[
        ('hour', 'Per Hour'),
        ('day', 'Per Day'),
        ('week', 'Per Week'),
        ('month', 'Per Month'),
        ('year', 'Per Year'),
    ])
    is_salary_negotiable = models.BooleanField(default=False)
    show_salary = models.BooleanField(default=True)
    benefits = models.JSONField(default=list, blank=True, help_text="List of benefits as JSON array")

    # Job Details
    short_description = models.TextField(max_length=300)
    detailed_description = models.TextField()
    key_responsibilities = models.TextField()
    qualifications = models.TextField()
    required_skills = models.JSONField(default=list, help_text="Skills as JSON array")
    preferred_skills = models.JSONField(default=list, blank=True)
    tools_technologies = models.JSONField(default=list, blank=True)

    # Application Details
    application_deadline = models.DateTimeField(null=True, blank=True)
    vacancy_count = models.PositiveIntegerField(default=1)
    estimated_duration = models.CharField(max_length=50, blank=True, help_text="e.g., 6 months contract")

    # Status & Metadata
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal')
    is_featured = models.BooleanField(default=False)
    is_remote_allowed = models.BooleanField(default=False)
    requires_travel = models.BooleanField(default=False)
    travel_percentage = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])

    # Metrics
    views_count = models.PositiveIntegerField(default=0)
    applications_count = models.PositiveIntegerField(default=0)
    shortlisted_count = models.PositiveIntegerField(default=0)
    conversion_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)

    # Dates
    posted_date = models.DateTimeField(auto_now_add=True, db_index=True)
    published_date = models.DateTimeField(null=True, blank=True)
    closed_date = models.DateTimeField(null=True, blank=True)

    # SEO & Sharing
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(blank=True)
    og_image = models.ImageField(upload_to='careers/og-images/', blank=True, null=True)
    share_count = models.PositiveIntegerField(default=0)

    # Workflow
    hiring_manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_jobs')
    recruiter = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='recruited_jobs')
    approver = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_jobs')

    class Meta:
        ordering = ['-priority', '-posted_date']
        indexes = [
            models.Index(fields=['status', 'published_date']),
            models.Index(fields=['job_type', 'experience_level']),
            models.Index(fields=['location', 'is_remote_allowed']),
            models.Index(fields=['salary_range_min', 'salary_range_max']),
        ]
        permissions = [
            ("can_publish_job", "Can publish job openings"),
            ("can_manage_job", "Can manage job openings"),
            ("can_view_analytics", "Can view job analytics"),
        ]

    def __str__(self):
        return f"{self.title} ({self.reference_id})"

    def _generate_unique_slug(self, base):
        """
        Ensure slug uniqueness for JobOpening.
        """
        slug_candidate = base
        index = 1
        while JobOpening.objects.filter(slug=slug_candidate).exclude(pk=self.pk).exists():
            slug_candidate = f"{base}-{index}"
            index += 1
        return slug_candidate

    def save(self, *args, **kwargs):
        # Ensure a reference_id exists before building slug
        if not self.reference_id:
            # make sure length stays within max_length
            self.reference_id = f"JA-{uuid.uuid4().hex[:8].upper()}"

        if not self.slug:
            base = slugify(f"{self.title}-{self.reference_id}") or f"{uuid.uuid4().hex[:8]}"
            self.slug = self._generate_unique_slug(base)

        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('careers:job_detail', kwargs={'pk': self.pk, 'slug': self.slug})

    @property
    def is_active(self):
        if self.status != 'open':
            return False
        if self.application_deadline and self.application_deadline < timezone.now():
            return False
        if self.vacancy_count <= 0:
            return False
        return True

    @property
    def remaining_days(self):
        if not self.application_deadline:
            return None
        delta = self.application_deadline - timezone.now()
        return max(0, delta.days)

    @property
    def is_closing_soon(self):
        remaining = self.remaining_days
        return remaining is not None and remaining <= 7

    @property
    def formatted_salary(self):
        if not self.show_salary:
            return "Competitive Salary"

        if self.salary_range_min and self.salary_range_max:
            # Using Decimal for precision; format with commas and no decimals for display
            min_val = f"{self.salary_currency} {int(self.salary_range_min):,}"
            max_val = f"{self.salary_currency} {int(self.salary_range_max):,}"
            period = dict(self._meta.get_field('salary_period').choices).get(self.salary_period, self.salary_period)
            return f"{min_val} - {max_val} {period}"
        elif self.salary_range_min:
            period = dict(self._meta.get_field('salary_period').choices).get(self.salary_period, self.salary_period)
            return f"{self.salary_currency} {int(self.salary_range_min):,}+ {period}"
        else:
            return "Salary disclosed during interview"

    def increment_views(self):
        self.views_count += 1
        self.save(update_fields=['views_count'])

    def increment_applications(self):
        self.applications_count += 1
        self.save(update_fields=['applications_count'])

    def calculate_conversion_rate(self):
        if self.views_count > 0:
            self.conversion_rate = (Decimal(self.applications_count) / Decimal(self.views_count)) * 100
            self.save(update_fields=['conversion_rate'])


class JobApplication(TimeStampedModel):
    STATUS_CHOICES = [
        ('applied', 'Applied'),
        ('reviewed', 'Reviewed'),
        ('shortlisted', 'Shortlisted'),
        ('phone_screen', 'Phone Screening'),
        ('assessment', 'Assessment'),
        ('interview_1', 'First Interview'),
        ('interview_2', 'Second Interview'),
        ('interview_3', 'Final Interview'),
        ('background_check', 'Background Check'),
        ('offer_pending', 'Offer Pending'),
        ('offer_extended', 'Offer Extended'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
        ('on_hold', 'On Hold'),
    ]

    SOURCE_CHOICES = [
        ('career_site', 'Career Site'),
        ('linkedin', 'LinkedIn'),
        ('indeed', 'Indeed'),
        ('glassdoor', 'Glassdoor'),
        ('referral', 'Employee Referral'),
        ('agency', 'Recruitment Agency'),
        ('campus', 'Campus Recruitment'),
        ('social_media', 'Social Media'),
        ('other', 'Other'),
    ]

    # Application Reference
    job = models.ForeignKey(JobOpening, on_delete=models.CASCADE, related_name='applications')
    application_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    reference_code = models.CharField(max_length=20, unique=True, blank=True)

    # Personal Information
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(db_index=True)
    phone = models.CharField(max_length=20, db_index=True)
    alternate_phone = models.CharField(max_length=20, blank=True)

    # Address
    address_line1 = models.CharField(max_length=200)
    address_line2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)
    country = models.CharField(max_length=100, default='India')

    # Professional Information
    current_company = models.CharField(max_length=200, blank=True)
    current_position = models.CharField(max_length=200, blank=True)
    current_salary = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    expected_salary = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    salary_currency = models.CharField(max_length=10, default='INR')
    notice_period = models.CharField(max_length=50, blank=True)
    notice_period_days = models.IntegerField(null=True, blank=True)

    # Experience
    total_experience = models.DecimalField(max_digits=4, decimal_places=1)
    relevant_experience = models.DecimalField(max_digits=4, decimal_places=1)
    experience_summary = models.TextField(blank=True)

    # Education
    highest_qualification = models.CharField(max_length=200)
    university = models.CharField(max_length=200)
    year_of_passing = models.PositiveIntegerField()
    cgpa = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    additional_certifications = models.JSONField(default=list, blank=True)

    # Documents
    resume = models.FileField(
        upload_to='careers/resumes/%Y/%m/%d/',
        validators=[FileExtensionValidator(['pdf', 'doc', 'docx'])]
    )
    cover_letter = models.FileField(
        upload_to='careers/cover_letters/%Y/%m/%d/',
        validators=[FileExtensionValidator(['pdf', 'doc', 'docx'])],
        blank=True,
        null=True
    )
    portfolio_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    github_url = models.URLField(blank=True)

    # Status & Workflow
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='applied')
    status_changed_at = models.DateTimeField(auto_now_add=True)
    status_notes = models.TextField(blank=True)

    # Evaluation
    rating = models.PositiveIntegerField(default=0, choices=[(i, i) for i in range(6)])
    evaluation_notes = models.TextField(blank=True)
    skills_match_percentage = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    cultural_fit_score = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])

    # Interview & Offers
    interview_schedule = models.JSONField(default=dict, blank=True)
    interview_feedback = models.JSONField(default=dict, blank=True)
    offer_details = models.JSONField(default=dict, blank=True)

    # Metadata
    source = models.CharField(max_length=50, choices=SOURCE_CHOICES, default='career_site')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    device_type = models.CharField(max_length=50, blank=True)
    utm_source = models.CharField(max_length=100, blank=True)
    utm_medium = models.CharField(max_length=100, blank=True)
    utm_campaign = models.CharField(max_length=100, blank=True)

    # Privacy & Consent
    consent_data_storage = models.BooleanField(default=False)
    consent_future_opportunities = models.BooleanField(default=False)
    consent_privacy_policy = models.BooleanField(default=False)
    consent_terms = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        unique_together = ['email', 'job']
        indexes = [
            models.Index(fields=['email', 'status']),
            models.Index(fields=['job', 'status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['rating', 'created_at']),
        ]
        permissions = [
            ("can_view_all_applications", "Can view all applications"),
            ("can_change_status", "Can change application status"),
            ("can_schedule_interview", "Can schedule interviews"),
            ("can_view_analytics", "Can view application analytics"),
        ]

    def __str__(self):
        return f"{self.full_name} - {self.job.title} ({self.reference_code})"

    def save(self, *args, **kwargs):
        if not self.reference_code:
            self.reference_code = f"APP-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def get_absolute_url(self):
        return reverse('careers:application_tracker', kwargs={'reference_code': self.reference_code})

    def update_status(self, new_status, notes=""):
        self.status = new_status
        self.status_notes = notes
        self.status_changed_at = timezone.now()
        self.save(update_fields=['status', 'status_notes', 'status_changed_at'])

    def calculate_skills_match(self, required_skills):
        if not required_skills:
            return 0
        # Placeholder — implement real matching algorithm as needed
        return self.skills_match_percentage


class JobAlertSubscription(TimeStampedModel):
    email = models.EmailField(unique=True, db_index=True)
    name = models.CharField(max_length=100, blank=True)

    # Preferences
    job_categories = models.ManyToManyField(JobCategory, blank=True)
    job_types = models.JSONField(default=list, blank=True)
    experience_levels = models.JSONField(default=list, blank=True)
    locations = models.JSONField(default=list, blank=True)
    salary_min = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    salary_max = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # Status
    is_active = models.BooleanField(default=True)
    is_confirmed = models.BooleanField(default=False)
    confirmation_token = models.UUIDField(default=uuid.uuid4, unique=True)
    last_notified = models.DateTimeField(null=True, blank=True)
    notification_count = models.PositiveIntegerField(default=0)

    # Settings
    frequency = models.CharField(max_length=20, default='daily', choices=[
        ('immediate', 'Immediate'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('biweekly', 'Bi-weekly'),
    ])
    format = models.CharField(max_length=20, default='html', choices=[
        ('html', 'HTML'),
        ('text', 'Plain Text'),
    ])

    class Meta:
        indexes = [
            models.Index(fields=['email', 'is_active']),
            models.Index(fields=['is_active', 'frequency']),
        ]

    def __str__(self):
        return f"{self.email} ({self.frequency})"

    def send_confirmation_email(self):
        # Email sending logic
        pass

    def send_alert_email(self, jobs):
        # Alert email logic
        pass


class ApplicationEventLog(TimeStampedModel):
    EVENT_TYPES = [
        ('status_change', 'Status Change'),
        ('document_upload', 'Document Upload'),
        ('interview_scheduled', 'Interview Scheduled'),
        ('email_sent', 'Email Sent'),
        ('note_added', 'Note Added'),
        ('rating_changed', 'Rating Changed'),
        ('viewed', 'Application Viewed'),
    ]

    application = models.ForeignKey('JobApplication', on_delete=models.CASCADE, related_name='event_logs')
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    description = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['application', 'event_type']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.application.reference_code} - {self.event_type}"


class SavedJob(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_jobs')
    job = models.ForeignKey(JobOpening, on_delete=models.CASCADE, related_name='saved_by')
    notes = models.TextField(blank=True)
    reminder_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['user', 'job']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} saved {self.job.title}"


class ApplicationTracker(TimeStampedModel):
    application = models.OneToOneField(JobApplication, on_delete=models.CASCADE, related_name='tracker')
    tracking_code = models.CharField(max_length=20, unique=True)
    last_accessed = models.DateTimeField(auto_now=True)
    access_count = models.PositiveIntegerField(default=0)
    email_notifications = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=['tracking_code']),
        ]

    def __str__(self):
        return f"Tracker for {self.application.reference_code}"

    def increment_access(self):
        self.access_count += 1
        self.save(update_fields=['access_count', 'last_accessed'])
