from django.urls import path, include
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required
from . import views

app_name = 'careers'

urlpatterns = [
    # Home & Dashboard
    path('', views.CareersHomeView.as_view(), name='home'),
    path('dashboard/', login_required(views.JobAnalyticsView.as_view()), name='dashboard'),
    
    # Jobs
    path('jobs/', views.JobListView.as_view(), name='job_list'),
    path('jobs/category/<slug:slug>/', views.JobListView.as_view(), name='job_list_by_category'),
    path('jobs/<int:pk>/<slug:slug>/', views.JobDetailView.as_view(), name='job_detail'),
    path('jobs/<int:pk>/', views.JobDetailView.as_view(), name='job_detail_short'),
    
    # Applications
    path('jobs/<int:job_id>/apply/', views.JobApplicationCreateView.as_view(), name='apply'),
    path('apply/quick/<int:job_id>/', views.QuickApplyView.as_view(), name='quick_apply'),
    path('application/<str:reference_code>/success/', 
         views.ApplicationSuccessView.as_view(), name='application_success'),
    path('application/track/<str:reference_code>/', 
         views.ApplicationTrackerView.as_view(), name='application_tracker'),
    
    # Job Alerts
    path('alerts/subscribe/', views.JobAlertSubscriptionView.as_view(), name='subscribe_alert'),
    path('alerts/confirm/<uuid:token>/', views.confirm_alert_subscription, name='confirm_alert'),
    path('alerts/manage/', views.JobAlertSubscriptionView.as_view(), name='manage_alerts'),
    
    # Saved Jobs
    path('jobs/save/', views.SavedJobCreateView.as_view(), name='save_job'),
    path('saved-jobs/', login_required(views.SavedJobListView.as_view()), name='saved_jobs'),
    
    # Static Pages
    path('about/', TemplateView.as_view(template_name='careers/static/about.html'), name='about'),
    path('process/', TemplateView.as_view(template_name='careers/static/process.html'), name='process'),
    path('benefits/', TemplateView.as_view(template_name='careers/static/benefits.html'), name='benefits'),
    path('faq/', TemplateView.as_view(template_name='careers/static/faq.html'), name='faq'),
    path('interview-tips/', TemplateView.as_view(template_name='careers/static/interview_tips.html'), 
         name='interview_tips'),
    path('privacy/', TemplateView.as_view(template_name='careers/static/privacy.html'), name='privacy'),
    path('terms/', TemplateView.as_view(template_name='careers/static/terms.html'), name='terms'),
    
    # API Endpoints
    path('api/search/suggestions/', views.search_suggestions, name='search_suggestions'),
    path('api/feedback/', views.submit_feedback, name='submit_feedback'),
    path('api/sitemap.json', views.CareersSitemapView.as_view(), name='sitemap'),
    
    # Analytics
    path('analytics/', include([
        path('overview/', views.JobAnalyticsView.as_view(), name='analytics_overview'),
        path('jobs/', views.JobAnalyticsView.as_view(), name='analytics_jobs'),
        path('applications/', views.JobAnalyticsView.as_view(), name='analytics_applications'),
    ])),
    
    # Webhooks (for external integrations)
    path('webhooks/', include([
        path('linkedin/', views.linkedin_webhook, name='webhook_linkedin'),
        path('indeed/', views.indeed_webhook, name='webhook_indeed'),
        path('calendar/', views.calendar_webhook, name='webhook_calendar'),
    ])),
]