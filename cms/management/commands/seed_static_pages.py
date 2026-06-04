"""
python manage.py seed_static_pages

Creates About, Terms of Service, Privacy Policy, Contact, and FAQ static pages
in the CMS if they don't already exist.
"""
from django.core.management.base import BaseCommand
from cms.models import StaticPage


PAGES = [
    {
        'title': 'About Us',
        'slug': 'about',
        'excerpt': 'Learn about NEXUS, our mission, and the team behind the platform.',
        'content': '''<h2>What is NEXUS?</h2>
<p>NEXUS is a premium media and content platform designed to connect creators with audiences worldwide. We believe great content deserves a great home.</p>
<h2>Our Mission</h2>
<p>We're building the most creator-friendly platform on the internet — one where your work is valued, your audience can find you, and you get paid fairly for your creativity.</p>
<h2>What We Offer</h2>
<ul>
  <li><strong>Movies & Series</strong> — Stream and download films, documentaries, and original series</li>
  <li><strong>Music</strong> — Discover new artists, listen to albums, and support musicians directly</li>
  <li><strong>Gallery</strong> — Browse and download stunning HD and AI-generated images</li>
  <li><strong>Blog</strong> — Read thoughtful articles from talented writers</li>
  <li><strong>AI Studio</strong> — Generate stunning images using the power of AI</li>
</ul>
<h2>Contact Us</h2>
<p>Have questions or want to get in touch? Visit our <a href="/page/contact/">Contact page</a> or email us directly.</p>''',
    },
    {
        'title': 'Terms of Service',
        'slug': 'terms',
        'excerpt': 'Read our terms and conditions for using the NEXUS platform.',
        'content': '''<p><strong>Last updated:</strong> January 2025</p>
<h2>1. Acceptance of Terms</h2>
<p>By accessing or using NEXUS, you agree to be bound by these Terms of Service. If you do not agree, please do not use the platform.</p>
<h2>2. User Accounts</h2>
<p>You are responsible for maintaining the confidentiality of your account credentials. You agree to notify us immediately of any unauthorised use of your account.</p>
<h2>3. Content Policy</h2>
<p>Users may not upload, post, or transmit content that is unlawful, harmful, abusive, harassing, defamatory, or otherwise objectionable. All uploaded content must be original or properly licensed.</p>
<h2>4. Creator Monetisation</h2>
<p>Creators on the platform may earn revenue through subscriptions and downloads. NEXUS retains a platform fee as outlined in the Creator Agreement. Earnings are paid monthly via the payment method on file.</p>
<h2>5. Intellectual Property</h2>
<p>Creators retain ownership of their uploaded content. By uploading to NEXUS, you grant us a limited licence to display, distribute, and promote your content on the platform.</p>
<h2>6. Premium Content</h2>
<p>Premium content requires an active subscription or one-time purchase. Refunds are evaluated on a case-by-case basis within 7 days of purchase.</p>
<h2>7. Termination</h2>
<p>We reserve the right to suspend or terminate accounts that violate these terms, with or without notice.</p>
<h2>8. Changes to Terms</h2>
<p>We may update these terms at any time. Continued use of the platform after changes constitutes acceptance of the revised terms.</p>
<h2>9. Contact</h2>
<p>For questions about these terms, please <a href="/page/contact/">contact us</a>.</p>''',
    },
    {
        'title': 'Privacy Policy',
        'slug': 'privacy',
        'excerpt': 'How NEXUS collects, uses, and protects your personal information.',
        'content': '''<p><strong>Last updated:</strong> January 2025</p>
<h2>1. Information We Collect</h2>
<p>We collect information you provide when creating an account (name, email, password), as well as usage data such as content viewed, searches performed, and interactions on the platform.</p>
<h2>2. How We Use Your Information</h2>
<ul>
  <li>To provide and improve our services</li>
  <li>To personalise your content experience</li>
  <li>To process payments and manage subscriptions</li>
  <li>To send service-related communications</li>
  <li>To detect and prevent fraud or abuse</li>
</ul>
<h2>3. Data Sharing</h2>
<p>We do not sell your personal data. We may share data with trusted third-party services (payment processors, cloud infrastructure) strictly as needed to provide our services.</p>
<h2>4. Cookies</h2>
<p>We use cookies to keep you logged in, remember your preferences, and understand how you use the platform. You can disable cookies in your browser settings, though some features may not function correctly.</p>
<h2>5. Data Retention</h2>
<p>We retain your account data for as long as your account is active. You may request deletion of your data at any time by contacting us.</p>
<h2>6. Security</h2>
<p>We use industry-standard security measures including encrypted connections (HTTPS) and hashed password storage. However, no system is completely secure, and we cannot guarantee absolute security.</p>
<h2>7. Your Rights</h2>
<p>Depending on your location, you may have rights to access, correct, or delete your personal data. To exercise these rights, please <a href="/page/contact/">contact us</a>.</p>
<h2>8. Contact</h2>
<p>For privacy-related questions, please <a href="/page/contact/">contact us</a>.</p>''',
    },
    {
        'title': 'Contact Us',
        'slug': 'contact',
        'excerpt': 'Get in touch with the NEXUS team — we\'d love to hear from you.',
        'content': '''<h2>Get In Touch</h2>
<p>Whether you have a question, want to report an issue, or are interested in creator partnerships, we're here to help.</p>
<h2>Support</h2>
<p>For account or technical issues, please email: <a href="mailto:support@nexus.platform">support@nexus.platform</a></p>
<h2>Creator Enquiries</h2>
<p>Interested in becoming a creator or growing your audience on NEXUS? Email: <a href="mailto:creators@nexus.platform">creators@nexus.platform</a></p>
<h2>Business & Partnerships</h2>
<p>For advertising, partnerships, or business enquiries: <a href="mailto:hello@nexus.platform">hello@nexus.platform</a></p>
<h2>Response Time</h2>
<p>We aim to respond to all enquiries within 2 business days.</p>
<hr>
<p style="color:var(--tx2);font-size:13px;">Note: Update the email addresses above in the CMS admin panel once you have configured your platform email.</p>''',
    },
    {
        'title': 'FAQ',
        'slug': 'faq',
        'excerpt': 'Frequently asked questions about NEXUS.',
        'content': '''<h2>General</h2>
<h3>Is NEXUS free to use?</h3>
<p>Yes! NEXUS is free to join. Free members can access all free-tier content. Premium content requires a subscription or one-time purchase.</p>
<h3>What subscription plans are available?</h3>
<p>Visit our <a href="/subscriptions/">Subscriptions page</a> to see the latest plans and pricing.</p>
<h2>Creators</h2>
<h3>How do I become a creator?</h3>
<p>Register for a free account and select "Creator" as your role, or upgrade your existing account from your profile settings.</p>
<h3>How do I earn money?</h3>
<p>Creators earn revenue from downloads, premium content purchases, and subscription revenue sharing. Earnings are paid monthly.</p>
<h3>What file formats are supported?</h3>
<p>We support MP4 and MKV for video, MP3/WAV/FLAC for audio, JPG/PNG/WEBP for images, and PDF for documents.</p>
<h2>Technical</h2>
<h3>What are the upload size limits?</h3>
<p>The maximum file size per upload is 500 MB for video, 50 MB for audio, and 25 MB for images.</p>
<h3>How does the AI image generator work?</h3>
<p>Our <a href="/ai/studio/">AI Studio</a> uses state-of-the-art image generation models. Simply type a description and the AI will create an image in seconds.</p>
<h3>I found a bug. How do I report it?</h3>
<p>Please <a href="/page/contact/">contact us</a> with details of the issue and we will investigate promptly.</p>''',
    },
]


class Command(BaseCommand):
    help = 'Creates default static pages (About, Terms, Privacy, Contact, FAQ) in the CMS'

    def handle(self, *args, **options):
        created_count = 0
        for page_data in PAGES:
            page, created = StaticPage.objects.get_or_create(
                slug=page_data['slug'],
                defaults={
                    'title': page_data['title'],
                    'excerpt': page_data['excerpt'],
                    'content': page_data['content'],
                    'status': 'published',
                    'show_in_footer': True,
                    'meta_title': f"{page_data['title']} — NEXUS",
                    'meta_description': page_data['excerpt'],
                },
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'  ✓ Created: {page_data["title"]} (/page/{page_data["slug"]}/)'))
            else:
                self.stdout.write(f'  – Already exists: {page_data["title"]}')

        if created_count:
            self.stdout.write(self.style.SUCCESS(f'\nDone — {created_count} page(s) created. Visit /page/about/ to confirm.'))
        else:
            self.stdout.write('\nAll pages already exist. No changes made.')