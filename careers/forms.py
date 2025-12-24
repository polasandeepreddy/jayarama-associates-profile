from django import forms
from django.core.validators import FileExtensionValidator, EmailValidator, RegexValidator
from django.utils import timezone
from django.contrib.auth.password_validation import validate_password
from .models import (
    JobApplication, JobAlertSubscription, SavedJob,
    JobOpening, JobCategory
)
import re


class AdvancedJobApplicationForm(forms.ModelForm):
    # Enhanced fields with validators
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'professional@email.com',
            'autocomplete': 'email',
            'spellcheck': 'false',
        }),
        validators=[EmailValidator(message="Please enter a valid email address")]
    )

    phone = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+91 98765 43210',
            'pattern': '^[+]?[0-9\s\-\(\)]{10,15}$',
        }),
        validators=[RegexValidator(
            regex=r'^[+]?[0-9\s\-\(\)]{10,15}$',
            message="Please enter a valid phone number"
        )]
    )

    resume = forms.FileField(
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control-file',
            'accept': '.pdf,.doc,.docx',
            'data-max-size': '5242880',  # 5MB
        }),
        validators=[
            FileExtensionValidator(['pdf', 'doc', 'docx']),
        ],
        help_text="Max 5MB. Allowed: PDF, DOC, DOCX"
    )

    cover_letter = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control-file',
            'accept': '.pdf,.doc,.docx',
        }),
        validators=[FileExtensionValidator(['pdf', 'doc', 'docx'])],
        help_text="Optional. Max 5MB"
    )

    linkedin_url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://linkedin.com/in/username',
            'pattern': '^https?://(www\.)?linkedin\.com/.*$',
        }),
        help_text="Optional. Include your LinkedIn profile URL"
    )

    portfolio_url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://yourportfolio.com',
        }),
        help_text="Optional. Link to your portfolio or website"
    )

    current_salary = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '0',
            'step': '1000',
            'placeholder': 'Current annual salary',
        }),
        help_text="Optional. Current annual salary (INR)"
    )

    expected_salary = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '0',
            'step': '1000',
            'placeholder': 'Expected annual salary',
        }),
        help_text="Optional. Expected annual salary (INR)"
    )

    total_experience = forms.DecimalField(
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '0',
            'max': '50',
            'step': '0.5',
            'placeholder': 'e.g., 5.5',
        }),
        help_text="Total professional experience in years"
    )

    relevant_experience = forms.DecimalField(
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '0',
            'max': '50',
            'step': '0.5',
            'placeholder': 'e.g., 3.5',
        }),
        help_text="Experience relevant to this position"
    )

    # Consent fields
    consent_data_storage = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        }),
        error_messages={'required': 'You must consent to data storage'}
    )

    consent_privacy_policy = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        }),
        error_messages={'required': 'You must accept the privacy policy'}
    )

    consent_terms = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        }),
        error_messages={'required': 'You must accept the terms and conditions'}
    )

    consent_future_opportunities = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        }),
        label="Keep my profile for future opportunities"
    )

    class Meta:
        model = JobApplication
        fields = [
            'first_name', 'last_name', 'email', 'phone', 'alternate_phone',
            'address_line1', 'address_line2', 'city', 'state', 'pincode', 'country',
            'current_company', 'current_position', 'current_salary', 'expected_salary',
            'salary_currency', 'notice_period', 'notice_period_days',
            'total_experience', 'relevant_experience', 'experience_summary',
            'highest_qualification', 'university', 'year_of_passing', 'cgpa',
            'additional_certifications', 'resume', 'cover_letter',
            'linkedin_url', 'portfolio_url', 'github_url',
            'consent_data_storage', 'consent_privacy_policy', 'consent_terms',
            'consent_future_opportunities'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'First Name',
                'autocomplete': 'given-name',
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Last Name',
                'autocomplete': 'family-name',
            }),
            'address_line1': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Street Address',
                'autocomplete': 'street-address',
            }),
            'address_line2': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Apartment, Suite, etc.',
                'autocomplete': 'address-line2',
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'City',
                'autocomplete': 'address-level2',
            }),
            'state': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'State/Province',
                'autocomplete': 'address-level1',
            }),
            'pincode': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Postal Code',
                'autocomplete': 'postal-code',
                'pattern': '[0-9]*',
            }),
            'current_company': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Current Company',
            }),
            'current_position': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Current Position',
            }),
            'experience_summary': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Brief summary of your relevant experience...',
                'maxlength': '1000',
            }),
            'highest_qualification': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., B.Tech Computer Science',
            }),
            'university': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'University/Institution',
            }),
            'year_of_passing': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1950',
                'max': str(timezone.now().year + 5),
                'placeholder': 'e.g., 2020',
            }),
            'cgpa': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '10',
                'step': '0.01',
                'placeholder': 'e.g., 8.5',
            }),
            'notice_period': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 30 days, 60 days, Immediate',
            }),
            'notice_period_days': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '180',
                'placeholder': 'Number of days',
            }),
            'salary_currency': forms.Select(attrs={
                'class': 'form-control',
            }),
        }

    def clean_resume(self):
        resume = self.cleaned_data.get('resume')
        if resume:
            # File size validation (5MB)
            if resume.size > 5 * 1024 * 1024:
                raise forms.ValidationError("Resume file size must be under 5MB.")

            # File name validation
            if not re.match(r'^[a-zA-Z0-9_\-\.\s]+$', resume.name):
                raise forms.ValidationError("File name contains invalid characters.")

        return resume

    def clean_cover_letter(self):
        cover_letter = self.cleaned_data.get('cover_letter')
        if cover_letter:
            if cover_letter.size > 5 * 1024 * 1024:
                raise forms.ValidationError("Cover letter file size must be under 5MB.")

        return cover_letter

    def clean_total_experience(self):
        total_exp = self.cleaned_data.get('total_experience')
        if total_exp and total_exp < 0:
            raise forms.ValidationError("Experience cannot be negative.")
        if total_exp and total_exp > 50:
            raise forms.ValidationError("Experience cannot exceed 50 years.")
        return total_exp

    def clean_relevant_experience(self):
        relevant_exp = self.cleaned_data.get('relevant_experience')
        total_exp = self.cleaned_data.get('total_experience')

        if relevant_exp and relevant_exp < 0:
            raise forms.ValidationError("Relevant experience cannot be negative.")

        if relevant_exp and total_exp and relevant_exp > total_exp:
            raise forms.ValidationError("Relevant experience cannot exceed total experience.")

        return relevant_exp

    def clean_email(self):
        email = self.cleaned_data.get('email')
        job = getattr(self.instance, 'job', None)

        if job and email:
            # Check if already applied (case-insensitive)
            existing = JobApplication.objects.filter(
                job=job,
                email__iexact=email
            ).exists()

            if existing:
                raise forms.ValidationError(
                    "You have already applied for this position with this email address."
                )

        return (email or '').lower()  # Store emails in lowercase (safe if None)

    def clean_phone(self):
        phone = self.cleaned_data.get('phone') or ''
        # Remove all non-digit characters except leading +
        cleaned = re.sub(r'[^\d+]', '', phone)

        # Validate length
        digits = re.sub(r'[^\d]', '', cleaned)
        if len(digits) < 10 or len(digits) > 15:
            raise forms.ValidationError("Phone number must be between 10-15 digits.")

        return cleaned

    def clean_linkedin_url(self):
        url = self.cleaned_data.get('linkedin_url')
        if url and 'linkedin.com' not in url:
            raise forms.ValidationError("Please enter a valid LinkedIn URL.")
        return url

    def clean(self):
        cleaned_data = super().clean()

        # Salary validation
        current_salary = cleaned_data.get('current_salary')
        expected_salary = cleaned_data.get('expected_salary')

        if current_salary and expected_salary:
            if expected_salary < current_salary:
                self.add_error('expected_salary',
                               "Expected salary should be greater than or equal to current salary.")

        return cleaned_data


class QuickApplyForm(forms.Form):
    """Form for quick one-click applications"""
    name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Full Name',
            'autocomplete': 'name',
        })
    )

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email Address',
            'autocomplete': 'email',
        })
    )

    phone = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Phone Number',
        })
    )

    resume = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.doc,.docx',
        })
    )

    linkedin_url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'LinkedIn Profile (Optional)',
        })
    )


class JobAlertSubscriptionForm(forms.ModelForm):
    # Use model field choices via _meta to be robust
    frequency = forms.ChoiceField(
        choices=JobAlertSubscription._meta.get_field('frequency').choices,
        initial='daily',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    job_categories = forms.ModelMultipleChoiceField(
        queryset=None,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        help_text="Select job categories to filter"
    )

    job_types = forms.MultipleChoiceField(
        choices=getattr(JobOpening, 'JOB_TYPE_CHOICES', ()),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        help_text="Select preferred job types"
    )

    experience_levels = forms.MultipleChoiceField(
        choices=getattr(JobOpening, 'EXPERIENCE_LEVEL_CHOICES', ()),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        help_text="Select experience levels"
    )

    class Meta:
        model = JobAlertSubscription
        fields = ['email', 'name', 'frequency', 'job_categories',
                  'job_types', 'experience_levels', 'locations',
                  'salary_min', 'salary_max', 'format']
        widgets = {
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'your.email@example.com',
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Your Name (Optional)',
            }),
            'locations': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Hyderabad, Bangalore, Remote',
            }),
            'salary_min': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Minimum Salary',
            }),
            'salary_max': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Maximum Salary',
            }),
            'format': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate queryset lazily to avoid circular import issues
        self.fields['job_categories'].queryset = JobCategory.objects.filter(is_active=True)

    def clean_email(self):
        email = self.cleaned_data.get('email')
        existing = JobAlertSubscription.objects.filter(email__iexact=email, is_active=True)

        if existing.exists():
            subscription = existing.first()
            if not subscription.is_confirmed:
                raise forms.ValidationError(
                    "Please check your email to confirm your existing subscription."
                )
            else:
                raise forms.ValidationError(
                    "You're already subscribed to job alerts with this email."
                )

        return (email or '').lower()

    def clean(self):
        cleaned_data = super().clean()
        salary_min = cleaned_data.get('salary_min')
        salary_max = cleaned_data.get('salary_max')

        if salary_min and salary_max and salary_min > salary_max:
            self.add_error('salary_min',
                           "Minimum salary cannot be greater than maximum salary.")

        return cleaned_data


class JobSearchFilterForm(forms.Form):
    """Advanced job search form"""
    keyword = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Job title, skills, or keywords',
            'autocomplete': 'off',
        })
    )

    location = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'City, state, or remote',
            'autocomplete': 'off',
        })
    )

    job_type = forms.MultipleChoiceField(
        required=False,
        choices=getattr(JobOpening, 'JOB_TYPE_CHOICES', ()),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        initial=['full_time', 'remote', 'hybrid']
    )

    experience_level = forms.MultipleChoiceField(
        required=False,
        choices=getattr(JobOpening, 'EXPERIENCE_LEVEL_CHOICES', ()),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )

    category = forms.ModelMultipleChoiceField(
        required=False,
        queryset=None,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )

    salary_range = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'Any Salary'),
            ('0-300000', 'Up to ₹3L'),
            ('300000-600000', '₹3L - ₹6L'),
            ('600000-1200000', '₹6L - ₹12L'),
            ('1200000-2400000', '₹12L - ₹24L'),
            ('2400000+', '₹24L+'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    sort_by = forms.ChoiceField(
        required=False,
        choices=[
            ('relevance', 'Relevance'),
            ('newest', 'Newest First'),
            ('salary_high', 'Salary (High to Low)'),
            ('salary_low', 'Salary (Low to High)'),
            ('deadline', 'Application Deadline'),
        ],
        initial='newest',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    posted_within = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'Any Time'),
            ('1', 'Last 24 hours'),
            ('7', 'Last 7 days'),
            ('30', 'Last 30 days'),
            ('90', 'Last 3 months'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    remote_only = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Remote Only'
    )

    featured_only = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Featured Jobs Only'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = JobCategory.objects.filter(is_active=True)


class SavedJobForm(forms.ModelForm):
    class Meta:
        model = SavedJob
        fields = ['notes', 'reminder_date']
        widgets = {
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Add notes about this job...',
            }),
            'reminder_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local',
            }),
        }


class ApplicationStatusUpdateForm(forms.Form):
    """Form for HR to update application status"""
    status = forms.ChoiceField(
        choices=getattr(JobApplication, 'STATUS_CHOICES', ()),
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Add notes about this status change...',
        })
    )

    notify_candidate = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Notify candidate via email'
    )

    interview_date = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local',
        })
    )
