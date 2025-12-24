from django.shortcuts import render

def home(request):
    return render(request, 'pages/home.html')

def about(request):
    approach_steps = [
        {
            'step': 1,
            'title': 'Client Consultation',
            'description': 'We begin with a thorough understanding of your valuation objectives and constraints.',
        },
        {
            'step': 2,
            'title': 'Site Inspection & Data Collection',
            'description': 'On-site visits, property measurements and document reviews ensure factual accuracy.',
        },
        {
            'step': 3,
            'title': 'Market Research',
            'description': 'We analyze comparable transactions, market trends and socioeconomic indicators.',
        },
        {
            'step': 4,
            'title': 'Valuation Methodologies',
            'description': 'We apply recognized approaches—cost, sales comparison and income capitalization—to arrive at a defensible opinion of value.',
        },
        {
            'step': 5,
            'title': 'Quality Assurance',
            'description': 'All reports undergo peer review and compliance checks against industry standards.',
        },
        {
            'step': 6,
            'title': 'Delivery & Support',
            'description': 'We present clear, comprehensive reports and remain available to address follow-up questions.',
        },
    ]
    
    return render(request, 'pages/about.html', {'approach_steps': approach_steps})

def services(request):
    services_data = [
        {
            'icon': 'home',
            'title': 'Residential Property Valuations',
            'description': 'Comprehensive assessments for Open Plots, Individual Houses, Villas and Apartments with detailed market analysis.',
            'features': ['Individual Houses', 'Villas', 'Apartments', 'Condominiums'],
        },
        {
            'icon': 'building-2',
            'title': 'Commercial Property Valuations',
            'description': 'Professional valuations for Office Spaces, Buildings, Shops, Warehouses and Sheds tailored for business needs.',
            'features': ['Office Spaces', 'Commercial Spaces', 'Retail Properties', 'Warehouses'],
        },
        {
            'icon': 'factory',
            'title': 'Industrial & Special-Use Valuations',
            'description': 'Specialized expertise in Factories, Educational Institutions, Hospitals and Income Generating Properties assessments.',
            'features': ['Manufacturing Facilities', 'Logistics Hubs', 'Specialized Facilities', 'Industrial Parks'],
        },
#       {
#           'icon': 'landmark',
#            'title': 'Land Valuations',
#           'description': 'Expert evaluation of Open land and development sites',
#           'features': ['Open Land', 'Development Sites'],
#        },
        {
            'icon': 'file-text',
            'title': 'Tax Purpose Valuations',
            'description': 'Accurate valuations for income tax and capital gain tax purposes ensuring compliance and optimization.',
            'features': ['Capital Gain Tax Purpose', 'Income Tax Purpose'],
        },
#        {
#           'icon': 'piggy-bank',
#          'title': 'Mortgage Valuations',
#            'description': 'Reliable loan security assessments for banks and financial institutions with quick turnaround.',
#            'features': ['Loan Security Assessment', 'Bank Mortgage Valuations', 'Financial Institution Reports', 'Quick Processing'],
#        },
#        {
#           'icon': 'trending-up',
#            'title': 'Land Acquisition & Liquidation',
#            'description': 'Strategic valuations for acquisition projects and liquidation scenarios with market insights.',
#            'features': ['Acquisition Valuations', 'Liquidation Assessment', 'Market Analysis', 'Strategic Planning'],
#        },
#        {
#            'icon': 'building',
#            'title': 'Market Research & Other Services',
#            'description': 'Comprehensive market research, feasibility studies, and related consulting services.',
#            'features': ['Market Research', 'Feasibility Studies', 'Property Consulting', 'Custom Solutions'],
#        },
    ]
    
    return render(request, 'pages/services.html', {'services': services_data})

def contact(request):
    return render(request, 'pages/contact.html')


    
def thank_you_page(request):
    """Simple thank you page after form submission"""
    return render(request, 'thank_you.html')

from django.shortcuts import render
from django.http import JsonResponse
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.utils.html import strip_tags
from django.views.decorators.csrf import csrf_exempt
import logging

logger = logging.getLogger(__name__)

@csrf_exempt
def contact_submit(request):
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':

        # --- INPUTS (UNCHANGED) ---
        f_name = request.POST.get('first_name', '').strip()
        l_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        p_type = request.POST.get('property_type', '').strip()
        desc = request.POST.get('description', 'No details provided.')

        whatsapp_phone = ''.join(filter(str.isdigit, phone))

        try:
            # ======================================================
            # 1. ADMIN EMAIL (RESPONSIVE DASHBOARD – ENHANCED)
            # ======================================================
            admin_html = f"""
            <div style="width:100%;background:#f1f5f9;padding:20px 0;">
                <table width="100%" cellpadding="0" cellspacing="0"
                    style="max-width:600px;margin:auto;background:#fff;border-radius:12px;
                    font-family:Segoe UI,Arial,sans-serif;border:1px solid #e2e8f0;">
                    
                    <tr>
                        <td style="background:#1e293b;padding:30px;text-align:center;">
                            <h1 style="color:#38bdf8;font-size:14px;margin:0;text-transform:uppercase;letter-spacing:2px;">
                                New Property Inquiry
                            </h1>
                            <p style="color:#fff;font-size:24px;margin:10px 0 0;font-weight:bold;">
                                {f_name} {l_name}
                            </p>
                        </td>
                    </tr>

                    <tr>
                        <td style="padding:20px;">
                            <p style="color:#64748b;font-size:12px;text-transform:uppercase;font-weight:bold;">
                                Property Type
                            </p>
                            <p style="color:#0f172a;font-size:16px;">
                                <strong>{p_type}</strong>
                            </p>

                            <div style="margin:20px 0;background:#f8fafc;padding:15px;border-radius:8px;
                                        font-size:14px;color:#334155;line-height:1.6;">
                                <strong>Client Note:</strong><br>{desc}
                            </div>

                            <table width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td style="padding:5px;">
                                        <a href="tel:{phone}" style="display:block;background:#2563eb;color:#fff;
                                            padding:15px;text-align:center;border-radius:8px;
                                            font-weight:bold;text-decoration:none;">
                                            📞 Call Client
                                        </a>
                                    </td>
                                    <td style="padding:5px;">
                                        <a href="https://wa.me/{whatsapp_phone}" style="display:block;background:#22c55e;color:#fff;
                                            padding:15px;text-align:center;border-radius:8px;
                                            font-weight:bold;text-decoration:none;">
                                            💬 WhatsApp
                                        </a>
                                    </td>
                                </tr>
                            </table>

                        </td>
                    </tr>
                </table>
            </div>
            """

            # ======================================================
            # 2. USER EMAIL (LUXURY CONFIRMATION – ENHANCED)
            # ======================================================
            user_html = f"""
            <div style="width:100%;background:#ffffff;padding:40px 0;">
                <table width="100%" cellpadding="0" cellspacing="0"
                    style="max-width:600px;margin:auto;font-family:Arial,sans-serif;text-align:center;">
                    
                    <tr>
                        <td>
                            <div style="width:60px;height:60px;line-height:60px;
                                        background:#f0fdf4;border-radius:50%;
                                        margin:0 auto 20px;font-size:30px;">
                                ✅
                            </div>

                            <h2 style="color:#0f172a;font-size:28px;">
                                Hello {f_name},
                            </h2>

                            <p style="color:#475569;font-size:16px;line-height:1.6;">
                                We’ve received your valuation request for
                                <strong>{p_type}</strong>.
                                Our expert will contact you shortly.
                            </p>

                            <div style="margin:30px auto;background:#f8fafc;border-radius:12px;
                                        padding:20px;border:1px solid #e2e8f0;">
                                <p style="margin:0;color:#64748b;font-size:12px;text-transform:uppercase;">
                                    We will call you at
                                </p>
                                <p style="margin-top:5px;color:#2563eb;font-size:20px;font-weight:bold;">
                                    {phone}
                                </p>
                            </div>

                            <p style="color:#94a3b8;font-size:13px;">
                                If this wasn’t you, please ignore this email.
                            </p>

                            <hr style="border:none;border-top:1px solid #f1f5f9;margin:30px 0;">

                            <p style="color:#1e293b;font-size:14px;font-weight:bold;">
                                Jayarama Associates – Valuation Desk
                            </p>
                        </td>
                    </tr>
                </table>
            </div>
            """

            # ======================================================
            # SMART MAIL ENGINE (ADVANCED, SAFE, REUSABLE)
            # ======================================================
            def send_smart_mail(subject, html_content, recipient):
                text_content = strip_tags(html_content)

                msg = EmailMultiAlternatives(
                    subject=subject,
                    body=text_content,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[recipient],
                    reply_to=[settings.DEFAULT_FROM_EMAIL],
                )

                msg.attach_alternative(html_content, "text/html")
                msg.extra_headers = {
                    "X-Priority": "1",
                    "X-Mailer": "Django-Mailer",
                }

                msg.send(fail_silently=False)

            # SEND EMAILS
            send_smart_mail(f"🚀 New Lead: {f_name}", admin_html, settings.ADMIN_EMAIL)
            send_smart_mail(f"Valuation Confirmed: {f_name}", user_html, email)

            return JsonResponse({'success': True})

        except Exception as e:
            logger.exception("Contact form email failure")
            return JsonResponse({'success': False, 'message': str(e)})

    return JsonResponse({'success': False, 'message': 'Invalid Request'})
