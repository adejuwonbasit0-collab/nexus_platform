#!/usr/bin/env python
"""Seed script — run with: python seed_data.py"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nexus_platform.settings')
django.setup()

from accounts.models import User
from content.models import Content, Series, Season, Episode, Category, Tag
from core.models import SiteSettings
from monetization.models import CommissionSettings
from cms.models import StaticPage

print("🌱 Seeding NEXUS Platform...")

# ── Site Settings ─────────────────────────────────────────────────────────────
defaults = {
    'site_name': 'NEXUS',
    'site_tagline': 'AI-Powered Media Universe',
    'twitter_url': 'https://x.com/nexusplatform',
    'instagram_url': 'https://instagram.com/nexusplatform',
    'youtube_url': 'https://youtube.com/@nexusplatform',
    'about_url': '/about',
    'contact_url': '/contact',
    'privacy_url': '/privacy',
    'terms_url': '/terms',
    'ai_enabled': '1',
    'ai_moderation_enabled': '1',
    'ai_system_prompt': (
        'You are NEXUS AI, a friendly assistant for a media platform. '
        'Help users find content, generate images, and navigate the platform. '
        'Be concise and helpful.'
    ),
}
for key, value in defaults.items():
    SiteSettings.objects.get_or_create(key=key, defaults={'value': value})
print("  ✓ Site settings")

# ── Categories ────────────────────────────────────────────────────────────────
cats = [
    ('Nature',       'nature',       'image', '🌿'),
    ('Architecture', 'architecture', 'image', '🏛'),
    ('Abstract',     'abstract',     'image', '🎨'),
    ('Action',       'action',       'video', '⚡'),
    ('Drama',        'drama',        'video', '🎭'),
    ('Documentary',  'documentary',  'video', '📽'),
    ('Hip-Hop',      'hip-hop',      'music', '🎤'),
    ('Electronic',   'electronic',   'music', '🎛'),
    ('Ambient',      'ambient',      'music', '🌊'),
    ('Tutorial',     'tutorial',     'blog',  '📚'),
    ('News',         'news',         'blog',  '📰'),
    ('Opinion',      'opinion',      'blog',  '💬'),
]
for name, slug, ctype, icon in cats:
    Category.objects.get_or_create(slug=slug, defaults={'name': name, 'content_type': ctype, 'icon': icon})
print("  ✓ Categories")

# ── Tags ──────────────────────────────────────────────────────────────────────
for t in ['4K', 'AI-Generated', 'Free', 'Premium', 'HD', 'Cinematic', 'Minimalist', 'Dark', 'Colorful']:
    Tag.objects.get_or_create(name=t)
print("  ✓ Tags")

# ── Commission Rates ──────────────────────────────────────────────────────────
rates = [
    ('image',  'view',     '0.0005'),
    ('image',  'download', '0.05'),
    ('video',  'view',     '0.001'),
    ('video',  'download', '0.10'),
    ('music',  'view',     '0.0008'),
    ('music',  'download', '0.08'),
    ('blog',   'view',     '0.0003'),
    ('blog',   'download', '0.02'),
]
for ctype, action, amount in rates:
    CommissionSettings.objects.get_or_create(
        content_type=ctype, action=action, defaults={'amount': amount}
    )
print("  ✓ Commission rates")

# ── Users ─────────────────────────────────────────────────────────────────────
if not User.objects.filter(username='admin').exists():
    admin = User.objects.create_superuser('admin', 'admin@nexus.com', 'admin123', role='admin')
    print("  ✓ Admin user   → username: admin  / password: admin123")
else:
    print("  ℹ Admin user already exists")

creators = [
    ('alice_creates', 'alice@nexus.com',   'creator123'),
    ('bob_films',     'bob@nexus.com',     'creator123'),
    ('chloe_beats',   'chloe@nexus.com',   'creator123'),
]
creator_objs = []
for uname, email, pwd in creators:
    u, created = User.objects.get_or_create(
        username=uname,
        defaults={'email': email, 'role': 'creator', 'is_verified': True}
    )
    if created:
        u.set_password(pwd)
        u.save()
    creator_objs.append(u)

if creator_objs:
    print(f"  ✓ Creator accounts (password: creator123): {', '.join(u.username for u in creator_objs)}")

# ── Demo Content ──────────────────────────────────────────────────────────────
nat_cat   = Category.objects.get(slug='nature')
arch_cat  = Category.objects.get(slug='architecture')
drama_cat = Category.objects.get(slug='drama')
hiphop_cat= Category.objects.get(slug='hip-hop')
tut_cat   = Category.objects.get(slug='tutorial')

alice, bob, chloe = creator_objs

demo_images = [
    ('Neon Forest Dreams',        alice,  'free',    nat_cat,   True),
    ('Urban Geometry #1',         alice,  'free',    arch_cat,  False),
    ('Abstract Flow Series',      bob,    'premium', arch_cat,  True),
    ('Misty Mountain Morning',    bob,    'free',    nat_cat,   False),
    ('Cyberpunk Alleyway',        chloe,  'premium', arch_cat,  True),
    ('Ocean at Dusk',             alice,  'free',    nat_cat,   False),
]
for title, creator, tier, cat, featured in demo_images:
    Content.objects.get_or_create(
        title=title,
        defaults=dict(
            creator=creator, content_type='image', tier=tier,
            category=cat, status='approved', featured=featured,
            description=f'A stunning {cat.name.lower()} photograph by {creator.username}.',
            views=__import__('random').randint(50, 2000),
            likes_count=__import__('random').randint(5, 200),
        )
    )

demo_videos = [
    ('The Last Signal',           bob,   'free',    drama_cat),
    ('City of Tomorrow',          alice, 'premium', drama_cat),
    ('Wilderness Chronicles',     chloe, 'free',    drama_cat),
]
for title, creator, tier, cat in demo_videos:
    Content.objects.get_or_create(
        title=title,
        defaults=dict(
            creator=creator, content_type='video', tier=tier,
            category=cat, status='approved',
            description=f'A {cat.name.lower()} film by {creator.username}.',
            views=__import__('random').randint(100, 5000),
            likes_count=__import__('random').randint(20, 500),
        )
    )

demo_music = [
    ('Midnight Frequencies',  chloe, 'free',    hiphop_cat),
    ('Neon Pulse',            chloe, 'free',    hiphop_cat),
    ('Urban Echoes Vol.1',    bob,   'premium', hiphop_cat),
]
for title, creator, tier, cat in demo_music:
    Content.objects.get_or_create(
        title=title,
        defaults=dict(
            creator=creator, content_type='music', tier=tier,
            category=cat, status='approved',
            description=f'Original track by {creator.username}.',
            views=__import__('random').randint(80, 3000),
        )
    )

demo_blogs = [
    ('How to Shoot Stunning Night Photography', alice, tut_cat),
    ('The Art of Minimalist Composition',       bob,   tut_cat),
    ('Building Your Creator Brand in 2025',     chloe, tut_cat),
]
for title, creator, cat in demo_blogs:
    Content.objects.get_or_create(
        title=title,
        defaults=dict(
            creator=creator, content_type='blog', tier='free',
            category=cat, status='approved',
            description='An in-depth guide for creators and visual artists.',
            body=(
                f'# {title}\n\nWelcome to this comprehensive guide by {creator.username}.\n\n'
                'In this article we cover the most important aspects of the topic and give you '
                'actionable advice you can use right away.\n\n'
                '## Key Takeaways\n\n'
                '- Understand your audience and their expectations.\n'
                '- Invest in quality over quantity.\n'
                '- Consistency is the foundation of every successful creator.\n\n'
                'Keep experimenting, stay authentic, and the results will follow.'
            ),
            views=__import__('random').randint(30, 800),
        )
    )

print("  ✓ Demo content (images, videos, music, blogs)")

# ── Demo Series ───────────────────────────────────────────────────────────────
series, _ = Series.objects.get_or_create(
    title='Echoes of Tomorrow',
    defaults=dict(
        creator=bob, description='A sci-fi drama about humanity navigating AI, love, and survival.',
        tier='free', status='approved', genre='Sci-Fi Drama',
    )
)
for snum in range(1, 3):
    season, _ = Season.objects.get_or_create(series=series, number=snum, defaults={'title': f'Season {snum}'})
    for enum in range(1, 5):
        Episode.objects.get_or_create(
            season=season, number=enum,
            defaults=dict(
                title=f'S{snum}E{enum}: {"Pilot" if enum == 1 else f"Chapter {enum}"}',
                description=f'Season {snum}, Episode {enum} of {series.title}.',
                views=__import__('random').randint(50, 1500),
            )
        )

print("  ✓ Demo series (Echoes of Tomorrow — 2 seasons, 4 episodes each)")

# ── Default Static Pages ─────────────────────────────────────────────────────
pages = [
    ('About Us', 'about', '<h2>About NEXUS</h2><p>Welcome to NEXUS — a creator-first media platform.</p>'),
    ('Contact', 'contact', '<h2>Contact Us</h2><p>Please reach out via email: support@nexus.com</p>'),
    ('Privacy Policy', 'privacy', '<h2>Privacy Policy</h2><p>Your privacy matters to us.</p>'),
    ('Terms of Service', 'terms', '<h2>Terms of Service</h2><p>By using NEXUS you agree to these terms.</p>'),
    ('FAQ', 'faq', '<h2>Frequently Asked Questions</h2><p>Common questions and answers.</p>'),
]
for title, slug, html in pages:
    StaticPage.objects.get_or_create(
        slug=slug,
        defaults={
            'title': title,
            'content': html,
            'status': 'published',
            'show_in_footer': True,
        }
    )
print("  ✓ Default static pages (about, contact, privacy, terms, faq)")
print("\n✅ Seeding complete!\n")
print("=" * 50)
print("  Platform URL : http://127.0.0.1:8000/")
print("  Admin Panel  : http://127.0.0.1:8000/admin-panel/")
print("  Django Admin : http://127.0.0.1:8000/django-admin/")
print("  Admin Login  : admin / admin123")
print("  Creator Login: alice_creates / creator123")
print("=" * 50)
