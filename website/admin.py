from django.contrib import admin
from .models import ContactSubmission


@admin.register(ContactSubmission)
class ContactSubmissionAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'email', 'phone', 'property_type', 'created_at', 'is_read')
    list_filter = ('property_type', 'is_read', 'created_at')
    search_fields = ('first_name', 'last_name', 'email', 'phone', 'description')
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 20
    actions = ['mark_as_read']
    
    fieldsets = (
        ('Personal Information', {
            'fields': ('first_name', 'last_name', 'email', 'phone')
        }),
        ('Property Details', {
            'fields': ('property_type', 'description')
        }),
        ('Terms & Status', {
            'fields': ('terms_accepted', 'is_read')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)
        self.message_user(request, f"{queryset.count()} submissions marked as read.")
    mark_as_read.short_description = "Mark selected submissions as read"