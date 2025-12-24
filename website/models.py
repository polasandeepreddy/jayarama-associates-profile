from django.db import models
from django.utils import timezone

class ContactSubmission(models.Model):
    PROPERTY_TYPES = [
        ('residential', 'Residential'),
        ('commercial', 'Commercial'),
        ('industrial', 'Industrial'),
        ('land', 'Land'),
        ('other', 'Other'),
    ]
    
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    email = models.EmailField()
    property_type = models.CharField(max_length=50, choices=PROPERTY_TYPES, default='residential')
    description = models.TextField(blank=True)
    terms_accepted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_read = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Contact Submission'
        verbose_name_plural = 'Contact Submissions'
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.property_type}"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def mark_as_read(self):
        self.is_read = True
        self.save()