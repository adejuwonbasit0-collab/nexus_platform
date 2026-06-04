"""
python manage.py setup_nexus

Initializes the platform with default CMS content, feature flags, and
creates default static pages. Run this once after first migrate.
"""
from django.core.management.base import BaseCommand
from django.utils.text import slugify


class Command(BaseCommand):
    help = 'Initialize Nexus platform with default CMS data'

    def handle(self, *args, **options):
        self.stdout.write('Setting up Nexus platform...')

        # 1. Initialize branding
        from cms.models import BrandingConfig
        branding = BrandingConfig.get()
        if not branding.site_name or branding.site_name == 'NEXUS':
            branding.site_name        = 'NEXUS'
            branding.site_tagline     = 'The Premium Creative Platform'
            branding.site_description = 'Discover movies, music, art, and stories. Upload your work, build an audience, and get paid for what you create.'
            branding.contact_email    = 'hello@nexus.local'
            branding.copyright_text   = '© {year} NEXUS Platform. All rights reserved.'
            branding.save()
            self.stdout.write('  ✓ Branding configured')

        # 2. Initialize theme
        from cms.models import ThemeConfig
        ThemeConfig.get()
        self.stdout.write('  ✓ Theme initialized')

        # 3. Initialize global SEO
        from cms.models import GlobalSEO
        seo = GlobalSEO.get()
        if not seo.meta_title or seo.meta_title == 'NEXUS — Media Platform':
            seo.meta_title       = 'NEXUS — The Premium Creative Platform'
            seo.meta_description = 'Discover and enjoy premium movies, music, art, and blog content. Join thousands of creators and fans on NEXUS.'
            seo.twitter_card     = 'summary_large_image'
            seo.save()
            self.stdout.write('  ✓ SEO configured')

        # 4. Create default static pages
        from cms.models import StaticPage
        default_pages = [
            {
                'title': 'About NEXUS',
                'slug': 'about',
                'status': 'published',
                'show_in_footer': True,
                'content': '<h2>About NEXUS</h2><p>NEXUS is a premium media and content platform connecting creators with audiences worldwide.</p><p>We believe in fair creator compensation, quality content, and an amazing user experience.</p>',
            },
            {
                'title': 'Privacy Policy',
                'slug': 'privacy',
                'status': 'published',
                'show_in_footer': True,
                'content': '<h2>Privacy Policy</h2><p>This Privacy Policy explains how NEXUS collects, uses, and protects your personal information.</p><h3>Information We Collect</h3><p>We collect information you provide directly to us, including name, email address, and payment information.</p><h3>How We Use Your Information</h3><p>We use your information to provide and improve our services, process transactions, and send you updates.</p><p><em>Last updated: 2025</em></p>',
            },
            {
                'title': 'Terms of Service',
                'slug': 'terms',
                'status': 'published',
                'show_in_footer': True,
                'content': '<h2>Terms of Service</h2><p>By using NEXUS, you agree to these terms. Please read them carefully.</p><h3>Use of Service</h3><p>You must be at least 13 years old to use NEXUS. You are responsible for your account and all activity under it.</p><h3>Content Policy</h3><p>You may not upload content that is illegal, harmful, or violates others&apos; rights.</p><p><em>Last updated: 2025</em></p>',
            },
            {
                'title': 'Contact Us',
                'slug': 'contact',
                'status': 'published',
                'show_in_footer': True,
                'content': '<h2>Contact Us</h2><p>Have a question or need support? We\'re here to help.</p><p><strong>Email:</strong> hello@nexus.local</p><p><strong>Response time:</strong> Within 24 hours on business days.</p>',
            },
        ]
        for page_data in default_pages:
            if not StaticPage.objects.filter(slug=page_data['slug']).exists():
                StaticPage.objects.create(**page_data)
                self.stdout.write(f'  ✓ Page created: {page_data["title"]}')

        # 5. Default homepage hero section
        from cms.models import HomepageSection
        if not HomepageSection.objects.exists():
            HomepageSection.objects.create(
                section_type='hero',
                title='The Premium Creative Platform',
                subtitle='Discover movies, music, art, and stories. Upload your work, build an audience, and get paid for what you create.',
                cta_text='Get Started Free',
                cta_url='/auth/register/',
                cta2_text='Browse Content',
                cta2_url='/movies/',
                order=0,
                is_visible=True,
            )
            self.stdout.write('  ✓ Default homepage hero created')

        # 6. Feature flags
        from cms.models import FeatureFlag
        from django.conf import settings as django_settings
        for key, default_val in django_settings.DEFAULT_FEATURE_FLAGS.items():
            FeatureFlag.objects.get_or_create(
                key=key,
                defaults={
                    'name': key.replace('_', ' ').title(),
                    'is_enabled': default_val,
                    'rollout_pct': 100,
                }
            )
        self.stdout.write(f'  ✓ Feature flags initialized')

        # 7. Default email templates
        from cms.models import EmailTemplate
        default_templates = [
            {
                'template_type': 'welcome',
                'subject': 'Welcome to NEXUS, {{user.username}}!',
                'body_html': '''<div style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:32px;">
<h1 style="color:#6c47ff;">Welcome to NEXUS! 🎉</h1>
<p>Hi {{user.username}},</p>
<p>Thank you for joining NEXUS — the premium creative platform. We're thrilled to have you!</p>
<p>Start exploring content from creators around the world, or if you signed up as a creator, begin uploading your work today.</p>
<a href="{{site_url}}" style="display:inline-block;background:#6c47ff;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;">Explore NEXUS →</a>
<p style="color:#888;font-size:13px;margin-top:32px;">© {{year}} NEXUS Platform</p>
</div>''',
                'body_text': 'Welcome to NEXUS, {{user.username}}! Start exploring at {{site_url}}',
                'is_active': True,
            },
            {
                'template_type': 'content_approved',
                'subject': '✅ Your content has been approved!',
                'body_html': '''<div style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:32px;">
<h1 style="color:#27ae60;">Content Approved! ✅</h1>
<p>Hi {{user.username}},</p>
<p>Great news! Your content <strong>"{{content_title}}"</strong> has been approved and is now live on NEXUS.</p>
<p>Your audience can now discover and enjoy your work.</p>
<a href="{{site_url}}/creator/" style="display:inline-block;background:#6c47ff;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;">View in Creator Studio →</a>
</div>''',
                'body_text': 'Your content "{{content_title}}" has been approved!',
                'is_active': True,
            },
            {
                'template_type': 'content_rejected',
                'subject': 'Content Review Update',
                'body_html': '''<div style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:32px;">
<h1 style="color:#e74c3c;">Content Needs Revision</h1>
<p>Hi {{user.username}},</p>
<p>Your content <strong>"{{content_title}}"</strong> was not approved at this time.</p>
<p><strong>Reason:</strong> {{reason}}</p>
<p>Please review our content guidelines and resubmit.</p>
<a href="{{site_url}}/creator/" style="display:inline-block;background:#6c47ff;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;">Back to Creator Studio →</a>
</div>''',
                'body_text': 'Your content "{{content_title}}" was not approved. Reason: {{reason}}',
                'is_active': True,
            },
            {
                'template_type': 'payout_processed',
                'subject': '💸 Your withdrawal has been approved!',
                'body_html': '''<div style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:32px;">
<h1 style="color:#6c47ff;">Withdrawal Approved 💸</h1>
<p>Hi {{user.username}},</p>
<p>Your withdrawal of <strong>{{amount}}</strong> has been approved and is being processed.</p>
<p>Funds typically arrive within 1–3 business days depending on your bank.</p>
</div>''',
                'body_text': 'Your withdrawal of {{amount}} has been approved!',
                'is_active': True,
            },
        ]
        for tmpl in default_templates:
            EmailTemplate.objects.get_or_create(
                template_type=tmpl['template_type'],
                defaults={k: v for k, v in tmpl.items() if k != 'template_type'}
            )
        self.stdout.write(f'  ✓ Default email templates created')

        # Additional email templates
        extra_templates = [
            {
                'template_type': 'password_reset',
                'subject': 'Reset your NEXUS password',
                'body_html': '<div style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:32px;"><h1 style="color:#7c5cfc;">Password Reset</h1><p>Hi {{user.username}},</p><p>Click below to reset your password. This link expires in 24 hours.</p><a href="{{reset_link}}" style="display:inline-block;background:#7c5cfc;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;margin:16px 0;">Reset Password →</a><p style="color:#888;font-size:13px;">If you did not request this, ignore this email.</p></div>',
                'body_text': 'Reset your NEXUS password: {{reset_link}}',
                'is_active': True,
            },
            {
                'template_type': 'email_verification',
                'subject': 'Verify your NEXUS email address',
                'body_html': '<div style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:32px;"><h1 style="color:#7c5cfc;">Verify Your Email</h1><p>Hi {{user.username}},</p><p>Please verify your email address to complete your registration.</p><a href="{{verify_link}}" style="display:inline-block;background:#7c5cfc;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;margin:16px 0;">Verify Email →</a></div>',
                'body_text': 'Verify your email: {{verify_link}}',
                'is_active': True,
            },
            {
                'template_type': 'subscription_confirm',
                'subject': '🎉 Subscription activated — Welcome to Premium!',
                'body_html': '<div style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:32px;"><h1 style="color:#7c5cfc;">You are Premium! 🎉</h1><p>Hi {{user.username}},</p><p>Your <strong>{{plan_name}}</strong> subscription is now active. Enjoy unlimited access to all premium content on NEXUS.</p><a href="{{site_url}}" style="display:inline-block;background:#7c5cfc;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;margin:16px 0;">Start Exploring →</a></div>',
                'body_text': 'Your {{plan_name}} subscription is active!',
                'is_active': True,
            },
            {
                'template_type': 'payment_receipt',
                'subject': 'Payment Receipt — NEXUS',
                'body_html': '<div style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:32px;"><h1 style="color:#7c5cfc;">Payment Receipt</h1><p>Hi {{user.username}},</p><p>Thank you for your payment of <strong>{{currency}} {{amount}}</strong>.</p><table style="width:100%;border-collapse:collapse;margin:16px 0;"><tr style="border-bottom:1px solid #eee;"><td style="padding:8px 0;color:#666;">Reference</td><td style="padding:8px 0;font-family:monospace;">{{reference}}</td></tr><tr style="border-bottom:1px solid #eee;"><td style="padding:8px 0;color:#666;">Amount</td><td style="padding:8px 0;font-weight:600;">{{currency}} {{amount}}</td></tr><tr><td style="padding:8px 0;color:#666;">Date</td><td style="padding:8px 0;">{{date}}</td></tr></table></div>',
                'body_text': 'Payment of {{currency}} {{amount}} received. Reference: {{reference}}',
                'is_active': True,
            },
            {
                'template_type': 'creator_welcome',
                'subject': '🎨 Creator account activated — Start uploading!',
                'body_html': '<div style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:32px;"><h1 style="color:#7c5cfc;">Welcome, Creator! 🎨</h1><p>Hi {{user.username}},</p><p>Your creator account is ready. You can now upload content, build an audience, and earn from your work on NEXUS.</p><div style="background:#f9f6ff;border-radius:10px;padding:20px;margin:16px 0;"><strong>Getting started:</strong><ul style="margin:10px 0;padding-left:20px;color:#555;"><li>Upload your first piece of content</li><li>Set up your withdrawal details</li><li>Share your profile</li></ul></div><a href="{{site_url}}/creator/" style="display:inline-block;background:#7c5cfc;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;margin:8px 0;">Open Creator Studio →</a></div>',
                'body_text': 'Welcome to NEXUS Creator Studio! Visit {{site_url}}/creator/ to start.',
                'is_active': True,
            },
            {
                'template_type': 'admin_alert',
                'subject': '🚨 Admin Alert — NEXUS Platform',
                'body_html': '<div style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:32px;background:#fff;"><h1 style="color:#ef4444;">Admin Alert 🚨</h1><p><strong>Alert Type:</strong> {{alert_type}}</p><p><strong>Details:</strong> {{message}}</p><p><strong>Time:</strong> {{timestamp}}</p><p><a href="{{site_url}}/admin-panel/system/?tab=alerts">View in Admin Panel →</a></p></div>',
                'body_text': 'Admin Alert [{{alert_type}}]: {{message}} at {{timestamp}}',
                'is_active': True,
            },
        ]
        for tmpl in extra_templates:
            EmailTemplate.objects.get_or_create(
                template_type=tmpl['template_type'],
                defaults={k: v for k, v in tmpl.items() if k != 'template_type'}
            )
        self.stdout.write(f'  ✓ Additional email templates created')

        # 8. Maintenance mode (ensure exists, disabled)
        from cms.models import MaintenanceConfig
        MaintenanceConfig.get()
        self.stdout.write('  ✓ Maintenance config initialized')

        # 9. Default menus
        from cms.models import Menu, MenuItem
        primary_menu, created = Menu.objects.get_or_create(
            location='primary',
            defaults={'name': 'Primary Navigation', 'is_active': True}
        )
        if created:
            default_items = [
                ('Home', '/', '🏠', 0),
                ('Movies', '/movies/', '🎬', 1),
                ('Music', '/music/', '🎵', 2),
                ('Gallery', '/images/', '🖼️', 3),
                ('Blog', '/blog/', '📝', 4),
            ]
            for label, url, icon, order in default_items:
                MenuItem.objects.create(
                    menu=primary_menu, label=label, url=url,
                    icon=icon, order=order
                )
            self.stdout.write('  ✓ Default navigation menu created')

        footer_menu, created = Menu.objects.get_or_create(
            location='footer',
            defaults={'name': 'Footer Menu', 'is_active': True}
        )
        if created:
            footer_items = [
                ('About', '/page/about/', 0),
                ('Privacy Policy', '/page/privacy/', 1),
                ('Terms of Service', '/page/terms/', 2),
                ('Contact', '/page/contact/', 3),
            ]
            for label, url, order in footer_items:
                MenuItem.objects.create(menu=footer_menu, label=label, url=url, order=order)
            self.stdout.write('  ✓ Default footer menu created')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('✅ Nexus platform setup complete!'))
        self.stdout.write('')
        self.stdout.write('Next steps:')
        self.stdout.write('  1. Create admin user: python manage.py createsuperuser')
        self.stdout.write('  2. Set admin role in shell: User.objects.filter(username=...).update(role="admin")')
        self.stdout.write('  3. Run dev server: python manage.py runserver')
        self.stdout.write('  4. Visit admin panel: http://localhost:8000/admin-panel/')
