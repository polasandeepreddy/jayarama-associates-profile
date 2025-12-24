# forms.py
from django import forms
from django.core.validators import validate_email, RegexValidator

class ContactForm(forms.Form):
    PROPERTY_TYPES = [
        ('residential', 'Residential Property'),
        ('commercial', 'Commercial Property'),
        ('industrial', 'Industrial Property'),
        ('land', 'Land/Plot'),
        ('other', 'Other'),
    ]
    
    first_name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': 'John',
        })
    )
    
    last_name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': 'Doe',
        })
    )
    
    phone = forms.CharField(
        max_length=15,
        required=True,
        validators=[
            RegexValidator(
                regex=r'^[0-9]{10}$',
                message='Please enter a valid 10-digit phone number'
            )
        ],
        widget=forms.TextInput(attrs={
            'placeholder': '9876543210',
        })
    )
    
    email = forms.EmailField(
        required=True,
        validators=[validate_email],
        widget=forms.EmailInput(attrs={
            'placeholder': 'john@example.com',
        })
    )
    
    property_type = forms.ChoiceField(
        choices=PROPERTY_TYPES,
        required=True,
        initial='residential',
        widget=forms.Select()
    )
    
    description = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={
            'placeholder': 'Describe your property in detail...',
            'rows': 3,
        })
    )
    
    terms_accepted = forms.BooleanField(
        required=True,
        error_messages={'required': 'You must agree to the terms and conditions'}
    )