"""
CMS — Centralized Content Management Models
All site content, branding, theme, navigation, SEO, and integrations
are controlled through these models — no code changes needed.
"""
from django.db import models
from django.utils import timezone


# ── Branding ──────────────────────────────────────────────────────────────────

class BrandingConfig(models.Model):
    """Single-row config for all site branding assets."""
    site_name        = models.CharField(max_length=100, default='NEXUS')
    site_tagline     = models.CharField(max_length=300, blank=True)
    site_description = models.TextField(blank=True)
    # Logos
    logo_primary     = models.ImageField(upload_to='cms/branding/', null=True, blank=True, help_text='Primary logo (dark bg)')
    logo_dark        = models.ImageField(upload_to='cms/branding/', null=True, blank=True, help_text='Logo for light backgrounds')
    logo_footer      = models.ImageField(upload_to='cms/branding/', null=True, blank=True)
    logo_email       = models.ImageField(upload_to='cms/branding/', null=True, blank=True)
    favicon          = models.ImageField(upload_to='cms/branding/', null=True, blank=True)
    social_preview   = models.ImageField(upload_to='cms/branding/', null=True, blank=True, help_text='Default OG image (1200x630)')
    # Contact
    contact_email    = models.EmailField(blank=True)
    contact_phone    = models.CharField(max_length=30, blank=True)
    contact_address  = models.TextField(blank=True)
    # Socials
    social_twitter   = models.URLField(blank=True)
    social_instagram = models.URLField(blank=True)
    social_facebook  = models.URLField(blank=True)
    social_youtube   = models.URLField(blank=True)
    social_tiktok    = models.URLField(blank=True)
    social_discord   = models.URLField(blank=True)
    social_linkedin  = models.URLField(blank=True)
    # Legal
    copyright_text   = models.CharField(max_length=300, blank=True, default='© {year} NEXUS. All rights reserved.')
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Branding Config'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def get_copyright(self):
        return self.copyright_text.replace('{year}', str(timezone.now().year))

    def __str__(self):
        return f'Branding: {self.site_name}'


# ── Theme ─────────────────────────────────────────────────────────────────────

class ThemeConfig(models.Model):
    """Design tokens — generates dynamic CSS for the site."""
    # Colors
    primary_color    = models.CharField(max_length=20, default='#6c47ff')
    secondary_color  = models.CharField(max_length=20, default='#ff4778')
    accent_color     = models.CharField(max_length=20, default='#00d4aa')
    background_color = models.CharField(max_length=20, default='#080810')
    surface_color    = models.CharField(max_length=20, default='#13132a')
    text_primary     = models.CharField(max_length=20, default='#e8e8f0')
    text_secondary   = models.CharField(max_length=20, default='#8888aa')
    # Typography
    heading_font     = models.CharField(max_length=100, default='Syne')
    body_font        = models.CharField(max_length=100, default='DM Sans')
    heading_font_url = models.URLField(blank=True)
    body_font_url    = models.URLField(blank=True)
    base_font_size   = models.CharField(max_length=10, default='16px')
    # Layout
    border_radius    = models.CharField(max_length=10, default='12px')
    max_width        = models.CharField(max_length=10, default='1380px')
    # Buttons
    btn_radius       = models.CharField(max_length=10, default='8px')
    btn_primary_bg   = models.CharField(max_length=20, default='#6c47ff')
    btn_primary_text = models.CharField(max_length=20, default='#ffffff')
    # Mode
    default_mode     = models.CharField(max_length=10, choices=[('dark','Dark'),('light','Light'),('system','System')], default='dark')
    # Custom CSS
    custom_css       = models.TextField(blank=True, help_text='Additional CSS injected into every page')
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Theme Config'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return 'Theme Configuration'


# ── Homepage Sections ──────────────────────────────────────────────────────────

class HomepageSection(models.Model):
    SECTION_TYPES = [
        ('hero',        'Hero Banner'),
        ('featured',    'Featured Content'),
        ('cta',         'Call to Action'),
        ('stats',       'Statistics'),
        ('testimonials','Testimonials'),
        ('faq',         'FAQ'),
        ('pricing',     'Pricing'),
        ('partners',    'Partners / Logos'),
        ('newsletter',  'Newsletter Signup'),
        ('custom',      'Custom HTML Block'),
    ]
    section_type = models.CharField(max_length=30, choices=SECTION_TYPES)
    title        = models.CharField(max_length=300, blank=True)
    subtitle     = models.TextField(blank=True)
    content      = models.TextField(blank=True, help_text='Body text or custom HTML')
    image        = models.ImageField(upload_to='cms/homepage/', null=True, blank=True)
    video_url    = models.URLField(blank=True)
    cta_text     = models.CharField(max_length=100, blank=True)
    cta_url      = models.CharField(max_length=300, blank=True)
    cta2_text    = models.CharField(max_length=100, blank=True)
    cta2_url     = models.CharField(max_length=300, blank=True)
    bg_color     = models.CharField(max_length=20, blank=True)
    text_color   = models.CharField(max_length=20, blank=True)
    order        = models.PositiveIntegerField(default=0)
    is_visible   = models.BooleanField(default=True)
    data         = models.JSONField(default=dict, blank=True, help_text='Extra structured data (stats, FAQs, etc.)')
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order']
        verbose_name = 'Homepage Section'

    def __str__(self):
        return f'[{self.get_section_type_display()}] {self.title or "(untitled)"}'


# ── Content Blocks (reusable) ─────────────────────────────────────────────────

class ContentBlock(models.Model):
    BLOCK_TYPES = [
        ('cta',         'CTA Block'),
        ('banner',      'Banner'),
        ('testimonial', 'Testimonial'),
        ('feature',     'Feature Grid Item'),
        ('info_card',   'Info Card'),
        ('faq_item',    'FAQ Item'),
        ('stat',        'Statistic'),
        ('partner',     'Partner Logo'),
    ]
    block_type  = models.CharField(max_length=30, choices=BLOCK_TYPES)
    name        = models.CharField(max_length=200, help_text='Internal label')
    title       = models.CharField(max_length=300, blank=True)
    subtitle    = models.TextField(blank=True)
    body        = models.TextField(blank=True)
    image       = models.ImageField(upload_to='cms/blocks/', null=True, blank=True)
    icon        = models.CharField(max_length=100, blank=True, help_text='Emoji or icon class')
    link_text   = models.CharField(max_length=100, blank=True)
    link_url    = models.CharField(max_length=300, blank=True)
    data        = models.JSONField(default=dict, blank=True)
    is_active   = models.BooleanField(default=True)
    order       = models.PositiveIntegerField(default=0)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return f'[{self.block_type}] {self.name}'


# ── Navigation ────────────────────────────────────────────────────────────────

class Menu(models.Model):
    LOCATIONS = [
        ('primary',   'Primary Navigation'),
        ('footer',    'Footer Menu'),
        ('footer2',   'Footer Column 2'),
        ('footer3',   'Footer Column 3'),
        ('sidebar',   'Sidebar Menu'),
        ('mobile',    'Mobile Menu'),
        ('user',      'User Dropdown'),
    ]
    name     = models.CharField(max_length=100)
    location = models.CharField(max_length=20, choices=LOCATIONS, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.name} ({self.location})'


class MenuItem(models.Model):
    menu       = models.ForeignKey(Menu, on_delete=models.CASCADE, related_name='items')
    parent     = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='children')
    label      = models.CharField(max_length=100)
    url        = models.CharField(max_length=500)
    icon       = models.CharField(max_length=100, blank=True)
    open_new_tab = models.BooleanField(default=False)
    requires_login = models.BooleanField(default=False)
    requires_admin = models.BooleanField(default=False)
    order      = models.PositiveIntegerField(default=0)
    is_visible = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.menu.location} → {self.label}'


# ── Static Pages ──────────────────────────────────────────────────────────────

class StaticPage(models.Model):
    STATUS = [('draft','Draft'),('published','Published')]
    title      = models.CharField(max_length=300)
    slug       = models.SlugField(unique=True)
    content    = models.TextField()
    excerpt    = models.TextField(blank=True, max_length=500)
    status     = models.CharField(max_length=20, choices=STATUS, default='draft')
    show_in_footer = models.BooleanField(default=False)
    show_in_nav    = models.BooleanField(default=False)
    # SEO
    meta_title       = models.CharField(max_length=200, blank=True)
    meta_description = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


# ── SEO Management ────────────────────────────────────────────────────────────

class GlobalSEO(models.Model):
    """Site-wide SEO defaults."""
    meta_title       = models.CharField(max_length=200, default='NEXUS — Media Platform')
    meta_description = models.CharField(max_length=320, blank=True)
    meta_keywords    = models.CharField(max_length=500, blank=True)
    og_title         = models.CharField(max_length=200, blank=True)
    og_description   = models.TextField(blank=True)
    og_image         = models.ImageField(upload_to='cms/seo/', null=True, blank=True)
    twitter_card     = models.CharField(max_length=30, default='summary_large_image')
    twitter_handle   = models.CharField(max_length=50, blank=True)
    canonical_domain = models.CharField(max_length=200, blank=True, help_text='e.g. https://yourdomain.com')
    # Indexing
    allow_indexing   = models.BooleanField(default=True)
    robots_txt       = models.TextField(default='User-agent: *\nAllow: /\nDisallow: /admin-panel/\nDisallow: /auth/\nDisallow: /creator/\n')
    # Schema
    schema_org_type  = models.CharField(max_length=50, default='WebSite')
    # Analytics placeholder
    google_site_verification = models.CharField(max_length=200, blank=True)
    bing_site_verification   = models.CharField(max_length=200, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Global SEO'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return 'Global SEO Settings'


class PageSEO(models.Model):
    """Per-URL SEO override."""
    path             = models.CharField(max_length=500, unique=True)
    meta_title       = models.CharField(max_length=200, blank=True)
    meta_description = models.CharField(max_length=320, blank=True)
    og_image         = models.ImageField(upload_to='cms/seo/pages/', null=True, blank=True)
    no_index         = models.BooleanField(default=False)
    canonical_url    = models.URLField(blank=True)
    updated_at       = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'SEO: {self.path}'


# ── Announcements & Banners ────────────────────────────────────────────────────

class Announcement(models.Model):
    TYPES = [
        ('banner',      'Top Banner Bar'),
        ('promo',       'Promo Bar'),
        ('popup',       'Modal Popup'),
        ('notice',      'Site-Wide Notice'),
    ]
    announcement_type = models.CharField(max_length=20, choices=TYPES, default='banner')
    title       = models.CharField(max_length=300)
    message     = models.TextField()
    link_text   = models.CharField(max_length=100, blank=True)
    link_url    = models.CharField(max_length=300, blank=True)
    bg_color    = models.CharField(max_length=20, default='#6c47ff')
    text_color  = models.CharField(max_length=20, default='#ffffff')
    is_active   = models.BooleanField(default=True)
    is_dismissible = models.BooleanField(default=True)
    show_to_logged_in  = models.BooleanField(default=True)
    show_to_guests     = models.BooleanField(default=True)
    starts_at   = models.DateTimeField(null=True, blank=True)
    ends_at     = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    def is_currently_active(self):
        now = timezone.now()
        if not self.is_active:
            return False
        if self.starts_at and now < self.starts_at:
            return False
        if self.ends_at and now > self.ends_at:
            return False
        return True

    def __str__(self):
        return f'[{self.announcement_type}] {self.title}'


# ── Email Templates ───────────────────────────────────────────────────────────

class EmailTemplate(models.Model):
    TEMPLATE_TYPES = [
        ('welcome',            'Welcome Email'),
        ('password_reset',     'Password Reset'),
        ('email_verification', 'Email Verification'),
        ('subscription_confirm','Subscription Confirmed'),
        ('payment_receipt',    'Payment Receipt'),
        ('content_approved',   'Content Approved'),
        ('content_rejected',   'Content Rejected'),
        ('payout_processed',   'Payout Processed'),
        ('creator_welcome',    'Creator Welcome'),
        ('admin_alert',        'Admin Alert'),
        ('custom',             'Custom Template'),
    ]
    template_type = models.CharField(max_length=30, choices=TEMPLATE_TYPES, unique=True)
    subject       = models.CharField(max_length=300)
    body_html     = models.TextField(help_text='HTML email body. Use {{variable}} placeholders.')
    body_text     = models.TextField(blank=True, help_text='Plain text fallback')
    from_name     = models.CharField(max_length=100, blank=True)
    from_email    = models.EmailField(blank=True)
    is_active     = models.BooleanField(default=True)
    updated_at    = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.get_template_type_display()} — {self.subject}'


# ── Script & Integration Center ───────────────────────────────────────────────

class ScriptInjection(models.Model):
    POSITIONS = [
        ('head',        'Inside <head>'),
        ('body_start',  'After <body> open'),
        ('body_end',    'Before </body>'),
    ]
    name        = models.CharField(max_length=200)
    description = models.CharField(max_length=500, blank=True)
    position    = models.CharField(max_length=20, choices=POSITIONS, default='head')
    script      = models.TextField(help_text='Full <script> tag or raw JS/HTML')
    is_active   = models.BooleanField(default=True)
    load_on_pages = models.CharField(max_length=500, blank=True, default='*',
                                     help_text='* for all pages, or comma-separated URL prefixes')
    order       = models.PositiveIntegerField(default=0)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['position', 'order']

    def __str__(self):
        return f'[{self.position}] {self.name}'


# ── Maintenance Mode ──────────────────────────────────────────────────────────

class MaintenanceConfig(models.Model):
    is_active        = models.BooleanField(default=False)
    title            = models.CharField(max_length=200, default='Under Maintenance')
    message          = models.TextField(default='We are performing scheduled maintenance. We\'ll be back shortly.')
    estimated_return = models.DateTimeField(null=True, blank=True)
    allow_admins     = models.BooleanField(default=True)
    allowed_ips      = models.TextField(blank=True, help_text='Comma-separated IPs that bypass maintenance')
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Maintenance Config'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f'Maintenance Mode: {"ON" if self.is_active else "OFF"}'


# ── Feature Flags ─────────────────────────────────────────────────────────────

class FeatureFlag(models.Model):
    key         = models.CharField(max_length=100, unique=True)
    name        = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    module      = models.CharField(max_length=50, blank=True)
    is_enabled  = models.BooleanField(default=True)
    rollout_pct = models.IntegerField(default=100, help_text='0-100% of users who see this feature')
    updated_at  = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.key} = {"ON" if self.is_enabled else "OFF"}'

    @classmethod
    def is_active(cls, key, user=None):
        try:
            flag = cls.objects.get(key=key)
            if not flag.is_enabled:
                return False
            if flag.rollout_pct >= 100:
                return True
            if user and user.is_authenticated:
                return (user.id % 100) < flag.rollout_pct
            return False
        except cls.DoesNotExist:
            from django.conf import settings
            return settings.DEFAULT_FEATURE_FLAGS.get(key, False)
