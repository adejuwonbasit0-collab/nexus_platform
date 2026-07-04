from django.db import migrations


PAGES = [
    ('About Us', 'about', True, True, '''
<h2>About Us</h2>
<p>We're a media platform built for people who create and people who watch, listen, and read — music, movies, series, images, and blog posts, all in one place.</p>
<h3>What we do</h3>
<ul>
  <li><strong>For listeners &amp; viewers:</strong> stream music and movies, discover new artists and genres, build playlists, and follow the creators you love.</li>
  <li><strong>For creators:</strong> upload your own tracks, films, series, photography, and articles, track your performance, and get paid through Creator Studio.</li>
</ul>
<h3>Our approach</h3>
<p>We believe a media platform should be fast, honest about how it works, and fair to the people who make the content that keeps it alive. That means clear moderation, transparent payouts, and a product that keeps improving based on what our community actually asks for.</p>
<h3>Get in touch</h3>
<p>Questions, feedback, or partnership ideas? Visit our <a href="/pages/contact/">Contact page</a> — we read everything that comes in.</p>
'''),

    ('Contact', 'contact', True, True, '''
<h2>Contact Us</h2>
<p>We'd love to hear from you — whether it's a question, a bug report, a partnership idea, or feedback on the platform.</p>
<h3>General support</h3>
<p>Email: <a href="mailto:support@nexus.com">support@nexus.com</a><br>We aim to respond within 1–2 business days.</p>
<h3>Creator &amp; payments questions</h3>
<p>Email: <a href="mailto:creators@nexus.com">creators@nexus.com</a> for anything related to uploads, Creator Studio, earnings, or withdrawals.</p>
<h3>Report content</h3>
<p>If you've found content that violates our <a href="/pages/community-guidelines/">Community Guidelines</a> or infringes a copyright, please use the "Report" option on the content itself, or email <a href="mailto:trust@nexus.com">trust@nexus.com</a> with a link and a short description.</p>
<h3>Business &amp; press</h3>
<p>Email: <a href="mailto:hello@nexus.com">hello@nexus.com</a></p>
'''),

    ('Privacy Policy', 'privacy', True, True, '''
<h2>Privacy Policy</h2>
<p><em>Last updated: {last_updated}</em></p>
<p>This Privacy Policy explains what information we collect, how we use it, and the choices you have. By using this platform, you agree to the practices described here.</p>

<h3>1. Information We Collect</h3>
<ul>
  <li><strong>Account information:</strong> name, email address, username, and password (stored securely, never in plain text).</li>
  <li><strong>Content you provide:</strong> music, videos, images, blog posts, comments, playlists, and any other content you upload or create.</li>
  <li><strong>Usage data:</strong> pages viewed, tracks/movies played, search queries, and general interaction with the platform, used to power recommendations and analytics.</li>
  <li><strong>Payment information:</strong> for creators receiving payouts or users making purchases, payment details are processed by our payment providers (e.g. Stripe, Paystack, Flutterwave) — we do not store full card numbers on our own servers.</li>
  <li><strong>Device &amp; log data:</strong> IP address, browser type, and device information, used for security and troubleshooting.</li>
</ul>

<h3>2. How We Use Your Information</h3>
<ul>
  <li>To operate and improve the platform (streaming, search, recommendations).</li>
  <li>To process payments, subscriptions, and creator payouts.</li>
  <li>To communicate with you about your account, security, or policy updates.</li>
  <li>To detect and prevent fraud, abuse, and violations of our Terms of Service.</li>
  <li>To comply with legal obligations where required.</li>
</ul>

<h3>3. Sharing Your Information</h3>
<p>We do not sell your personal data. We share information only with:</p>
<ul>
  <li>Service providers who help us run the platform (hosting, payment processing, email delivery), under confidentiality obligations.</li>
  <li>Law enforcement or regulators, only when required by law.</li>
  <li>Other users, limited to what you choose to make public (e.g. your profile, uploads, and public comments).</li>
</ul>

<h3>4. Cookies</h3>
<p>We use cookies to keep you signed in, remember your preferences, and understand how the platform is used. See our <a href="/pages/cookie-policy/">Cookie Policy</a> for details.</p>

<h3>5. Your Rights</h3>
<p>Depending on where you live, you may have the right to access, correct, export, or delete your personal data. You can manage most of this yourself from your account settings, or contact us at <a href="mailto:privacy@nexus.com">privacy@nexus.com</a> for anything else.</p>

<h3>6. Data Retention</h3>
<p>We keep your information for as long as your account is active, or as needed to provide the service, comply with legal obligations, resolve disputes, and enforce our agreements.</p>

<h3>7. Children's Privacy</h3>
<p>This platform is not directed at children under 13 (or the relevant minimum age in your country), and we do not knowingly collect personal information from them.</p>

<h3>8. Changes to This Policy</h3>
<p>We may update this Privacy Policy from time to time. Material changes will be announced on the platform. Continued use after an update means you accept the revised policy.</p>

<h3>9. Contact</h3>
<p>Questions about this policy? Email <a href="mailto:privacy@nexus.com">privacy@nexus.com</a>.</p>
'''),

    ('Terms of Service', 'terms', True, True, '''
<h2>Terms of Service</h2>
<p><em>Last updated: {last_updated}</em></p>
<p>These Terms of Service ("Terms") govern your use of this platform. By creating an account or using the site, you agree to these Terms.</p>

<h3>1. Your Account</h3>
<ul>
  <li>You must provide accurate information when creating an account and keep your login credentials secure.</li>
  <li>You must be at least 13 years old (or the minimum age in your country) to use this platform.</li>
  <li>You're responsible for all activity that happens under your account.</li>
</ul>

<h3>2. Content You Upload</h3>
<ul>
  <li>You retain ownership of the music, videos, images, and posts you upload.</li>
  <li>By uploading, you grant us a non-exclusive, worldwide license to host, stream, and display your content on the platform so we can operate the service.</li>
  <li>You confirm that you own the rights to what you upload, or have permission from the rights holder. Uploading copyrighted material you don't have the rights to is prohibited and may result in removal and account suspension.</li>
</ul>

<h3>3. Acceptable Use</h3>
<p>You agree not to:</p>
<ul>
  <li>Upload illegal, hateful, harassing, or sexually exploitative content, especially anything involving minors.</li>
  <li>Infringe someone else's copyright, trademark, or other intellectual property rights.</li>
  <li>Attempt to hack, disrupt, or reverse-engineer the platform.</li>
  <li>Use bots or scripts to artificially inflate plays, views, or earnings.</li>
</ul>
<p>See our full <a href="/pages/community-guidelines/">Community Guidelines</a> for more detail.</p>

<h3>4. Creator Payments &amp; Payouts</h3>
<ul>
  <li>Creators may earn revenue through subscriptions, tips, downloads, or other monetization features available in Creator Studio.</li>
  <li>Payouts are subject to identity verification and minimum withdrawal thresholds where applicable.</li>
  <li>We reserve the right to withhold or reverse payouts connected to fraudulent activity, chargebacks, or content that violates these Terms.</li>
</ul>

<h3>5. Subscriptions &amp; Purchases</h3>
<p>Paid subscriptions and one-off purchases are billed as described at the time of purchase. See our <a href="/pages/refund-policy/">Refund Policy</a> for cancellation and refund terms.</p>

<h3>6. Termination</h3>
<p>We may suspend or terminate accounts that violate these Terms, infringe others' rights, or pose a risk to the platform or its users. You may also delete your own account at any time from account settings.</p>

<h3>7. Disclaimers</h3>
<p>The platform is provided "as is." We do our best to keep it available and secure, but we don't guarantee uninterrupted service and aren't liable for content uploaded by other users.</p>

<h3>8. Changes to These Terms</h3>
<p>We may update these Terms periodically. Continued use of the platform after changes take effect means you accept the updated Terms.</p>

<h3>9. Contact</h3>
<p>Questions about these Terms? Email <a href="mailto:legal@nexus.com">legal@nexus.com</a>.</p>
'''),

    ('Refund Policy', 'refund-policy', True, True, '''
<h2>Refund Policy</h2>
<p><em>Last updated: {last_updated}</em></p>
<p>We want you to feel confident paying for anything on this platform. Here's exactly how refunds work.</p>

<h3>1. Subscriptions</h3>
<ul>
  <li>You can cancel your subscription at any time from account settings — you'll keep access until the end of the current billing period, and you won't be charged again.</li>
  <li>If you're charged in error (e.g. a duplicate charge or a charge after you cancelled), contact us within 14 days and we'll issue a full refund.</li>
  <li>Partial-month refunds for early cancellation aren't provided by default, except where required by local consumer law.</li>
</ul>

<h3>2. One-Time Purchases (downloads, premium tracks/movies, tips)</h3>
<ul>
  <li>Because digital content is delivered instantly, one-time purchases are generally non-refundable once the content has been accessed or downloaded.</li>
  <li>If a purchase failed to deliver (e.g. a broken download, a track/movie that won't play due to a platform error), contact support within 7 days and we'll fix it or refund it.</li>
</ul>

<h3>3. How to Request a Refund</h3>
<ol>
  <li>Email <a href="mailto:billing@nexus.com">billing@nexus.com</a> with your account email and the transaction date.</li>
  <li>We'll review the request, usually within 3–5 business days.</li>
  <li>Approved refunds are returned to your original payment method and may take 5–10 business days to appear, depending on your bank or payment provider.</li>
</ol>

<h3>4. Creator Payouts</h3>
<p>This Refund Policy covers payments <em>you make</em> to the platform. If a refund is issued for content a creator was paid for, the corresponding amount may be deducted from that creator's future payout, in line with our Terms of Service.</p>

<h3>5. Chargebacks</h3>
<p>Please contact us before filing a chargeback with your bank — we can usually resolve billing issues faster directly. Accounts with repeated unwarranted chargebacks may be suspended.</p>

<h3>6. Questions</h3>
<p>Reach out to <a href="mailto:billing@nexus.com">billing@nexus.com</a> any time — we're happy to walk through a specific charge with you.</p>
'''),

    ('FAQ', 'faq', True, True, '''
<h2>Frequently Asked Questions</h2>

<h3>Getting Started</h3>
<p><strong>Do I need an account to listen or watch?</strong><br>You can browse freely, but you'll need a free account to save playlists, like tracks, comment, or access premium content.</p>
<p><strong>Is there a free plan?</strong><br>Yes — core streaming is free. Premium plans unlock ad-free listening, offline downloads, and exclusive content where available.</p>

<h3>For Listeners &amp; Viewers</h3>
<p><strong>Can I create playlists?</strong><br>Yes, from any track page or your dashboard — click "Add to Playlist" to create a new one or add to an existing one.</p>
<p><strong>Why isn't a song/movie playing?</strong><br>This can happen if the file is still processing, or if a creator hasn't attached playable media yet. Try refreshing, or check back later.</p>

<h3>For Creators</h3>
<p><strong>How do I start uploading?</strong><br>Head to <a href="/creator/">Creator Studio</a> — apply for a creator account if you haven't already, then upload music, video, images, or blog posts directly.</p>
<p><strong>How do I get paid?</strong><br>Earnings from subscriptions, tips, and premium content accumulate in your in-app Wallet (Creator Studio → Wallet), where you can request a withdrawal once you hit the minimum threshold.</p>
<p><strong>Why is my upload "Pending"?</strong><br>New uploads go through a quick moderation check before going live, to keep the platform safe and spam-free. Most uploads are reviewed within 24–48 hours.</p>

<h3>Account &amp; Billing</h3>
<p><strong>How do I cancel my subscription?</strong><br>Go to Account Settings → Subscription → Cancel. You'll keep access until the end of your current billing period.</p>
<p><strong>Can I get a refund?</strong><br>See our full <a href="/pages/refund-policy/">Refund Policy</a> for the details on subscriptions and one-time purchases.</p>

<h3>Still need help?</h3>
<p>Visit our <a href="/pages/contact/">Contact page</a> — we're happy to help with anything not covered here.</p>
'''),

    ('Community Guidelines', 'community-guidelines', True, True, '''
<h2>Community Guidelines</h2>
<p>These guidelines exist to keep the platform safe, fair, and enjoyable for everyone — listeners, viewers, and creators alike.</p>

<h3>Do</h3>
<ul>
  <li>Upload content you own or have permission to share.</li>
  <li>Credit collaborators, producers, and featured artists accurately.</li>
  <li>Keep comments respectful, even in disagreement.</li>
  <li>Report content or behavior that breaks these guidelines.</li>
</ul>

<h3>Don't</h3>
<ul>
  <li>Upload copyrighted music, movies, or images you don't have rights to.</li>
  <li>Post hateful, harassing, sexually exploitative, or violent content — content involving or sexualizing minors is never allowed, in any form, and is reported to the relevant authorities.</li>
  <li>Spam, use bots, or artificially inflate plays, likes, or follower counts.</li>
  <li>Impersonate another person or creator.</li>
  <li>Share others' private information without consent.</li>
</ul>

<h3>Enforcement</h3>
<p>Depending on severity, violations may result in content removal, a warning, temporary restriction, or permanent account suspension. Copyright-infringing content is removed on valid request from the rights holder, in line with our <a href="/pages/terms/">Terms of Service</a>.</p>

<h3>Reporting</h3>
<p>Use the "Report" option on any track, movie, image, post, or comment, or email <a href="mailto:trust@nexus.com">trust@nexus.com</a>. Reports are reviewed by our moderation team, not automatically actioned.</p>
'''),

    ('Cookie Policy', 'cookie-policy', True, True, '''
<h2>Cookie Policy</h2>
<p>This Cookie Policy explains how we use cookies and similar technologies on this platform.</p>

<h3>What Are Cookies</h3>
<p>Cookies are small text files stored on your device that help websites remember information about your visit.</p>

<h3>How We Use Them</h3>
<ul>
  <li><strong>Essential cookies:</strong> keep you signed in and let core features (like the player and cart) work correctly. The platform won't function properly without these.</li>
  <li><strong>Preference cookies:</strong> remember settings like theme, volume, and playback quality.</li>
  <li><strong>Analytics cookies:</strong> help us understand how the platform is used so we can improve it.</li>
</ul>

<h3>Managing Cookies</h3>
<p>Most browsers let you block or delete cookies through their settings. Blocking essential cookies may prevent parts of the platform (like staying logged in) from working correctly.</p>

<h3>Changes</h3>
<p>We may update this Cookie Policy from time to time; material changes will be announced on the platform.</p>

<h3>Contact</h3>
<p>Questions? Email <a href="mailto:privacy@nexus.com">privacy@nexus.com</a>.</p>
'''),
]


def seed_pages(apps, schema_editor):
    StaticPage = apps.get_model('cms', 'StaticPage')
    from django.utils import timezone
    today = timezone.now().strftime('%B %d, %Y')

    for title, slug, show_in_footer, show_in_nav, content in PAGES:
        content = content.replace('{last_updated}', today)
        obj, created = StaticPage.objects.get_or_create(
            slug=slug,
            defaults={
                'title': title,
                'content': content,
                'status': 'published',
                'show_in_footer': show_in_footer,
                'show_in_nav': show_in_nav,
            },
        )
        if not created:
            # Only replace content that still looks like the old one-line
            # placeholder text, so any real editing an admin already did
            # (more than ~400 characters) is left untouched.
            if len(obj.content or '') < 400:
                obj.content = content
                obj.status = 'published'
                obj.show_in_footer = obj.show_in_footer or show_in_footer
                obj.save(update_fields=['content', 'status', 'show_in_footer'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('cms', '0003_brandingconfig_default_player_banner'),
    ]

    operations = [
        migrations.RunPython(seed_pages, noop),
    ]
