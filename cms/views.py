"""
CMS Admin Views — all CMS management endpoints for the admin panel.
"""
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.core.cache import cache
from django.utils import timezone

from .models import (
    BrandingConfig, ThemeConfig, HomepageSection, ContentBlock,
    Menu, MenuItem, StaticPage, GlobalSEO, PageSEO,
    Announcement, EmailTemplate, ScriptInjection,
    MaintenanceConfig, FeatureFlag
)


def _admin_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_admin():
            return redirect('/auth/login/')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


def _clear_cache():
    keys = ['cms_branding', 'cms_theme', 'cms_seo', 'cms_scripts',
            'cms_maintenance', 'cms_active_announcement']
    for k in keys:
        cache.delete(k)


# ── Branding ──────────────────────────────────────────────────────────────────

@_admin_required
def cms_branding(request):
    obj = BrandingConfig.get()
    if request.method == 'POST':
        fields = [
            'site_name', 'site_tagline', 'site_description',
            'contact_email', 'contact_phone', 'contact_address',
            'social_twitter', 'social_instagram', 'social_facebook',
            'social_youtube', 'social_tiktok', 'social_discord', 'social_linkedin',
            'copyright_text',
        ]
        for f in fields:
            val = request.POST.get(f, '')
            setattr(obj, f, val)
        # File uploads
        for fld in ['logo_primary', 'logo_dark', 'logo_footer', 'logo_email', 'favicon', 'social_preview']:
            if fld in request.FILES:
                setattr(obj, fld, request.FILES[fld])
        obj.save()
        _clear_cache()
        messages.success(request, 'Branding settings saved successfully.')
        return redirect('cms_branding')
    return render(request, 'admin_panel/cms/branding.html', {'obj': obj})


# ── Theme ─────────────────────────────────────────────────────────────────────

@_admin_required
def cms_theme(request):
    obj = ThemeConfig.get()
    if request.method == 'POST':
        fields = [
            'primary_color', 'secondary_color', 'accent_color',
            'background_color', 'surface_color', 'text_primary', 'text_secondary',
            'heading_font', 'body_font', 'heading_font_url', 'body_font_url',
            'base_font_size', 'border_radius', 'max_width',
            'btn_radius', 'btn_primary_bg', 'btn_primary_text',
            'default_mode', 'custom_css',
        ]
        for f in fields:
            val = request.POST.get(f, '')
            setattr(obj, f, val)
        obj.save()
        _clear_cache()
        messages.success(request, 'Theme saved. Changes are live immediately.')
        return redirect('cms_theme')
    return render(request, 'admin_panel/cms/theme.html', {'obj': obj})


@_admin_required
def cms_theme_css(request):
    """Serve dynamic CSS from theme config — linked in base.html."""
    obj = ThemeConfig.get()
    css = f"""
:root {{
  --accent:       {obj.primary_color};
  --accent2:      {obj.secondary_color};
  --accent3:      {obj.accent_color};
  --bg:           {obj.background_color};
  --bg2:          {obj.surface_color};
  --text:         {obj.text_primary};
  --text2:        {obj.text_secondary};
  --font-head:    '{obj.heading_font}', sans-serif;
  --font-body:    '{obj.body_font}', sans-serif;
  --radius:       {obj.border_radius};
  --max-w:        {obj.max_width};
  --btn-radius:   {obj.btn_radius};
  --btn-primary:  {obj.btn_primary_bg};
  --btn-text:     {obj.btn_primary_text};
  --border:       rgba(255,255,255,0.08);
}}
{obj.custom_css}
"""
    return HttpResponse(css, content_type='text/css')


# ── Homepage Manager ──────────────────────────────────────────────────────────

@_admin_required
def cms_homepage(request):
    sections = HomepageSection.objects.all()
    return render(request, 'admin_panel/cms/homepage.html', {'sections': sections})


@_admin_required
def cms_homepage_section_create(request):
    if request.method == 'POST':
        s = HomepageSection()
        s.section_type = request.POST.get('section_type', 'hero')
        s.title        = request.POST.get('title', '')
        s.subtitle     = request.POST.get('subtitle', '')
        s.content      = request.POST.get('content', '')
        s.cta_text     = request.POST.get('cta_text', '')
        s.cta_url      = request.POST.get('cta_url', '')
        s.cta2_text    = request.POST.get('cta2_text', '')
        s.cta2_url     = request.POST.get('cta2_url', '')
        s.bg_color     = request.POST.get('bg_color', '')
        s.text_color   = request.POST.get('text_color', '')
        s.order        = int(request.POST.get('order', 0))
        s.is_visible   = request.POST.get('is_visible') == 'on'
        s.video_url    = request.POST.get('video_url', '')
        if 'image' in request.FILES:
            s.image = request.FILES['image']
        # Handle JSON data field
        data_raw = request.POST.get('data', '{}')
        try:
            s.data = json.loads(data_raw)
        except Exception:
            s.data = {}
        s.save()
        messages.success(request, f'Section "{s.title or s.section_type}" created.')
        return redirect('cms_homepage')
    section_types = HomepageSection.SECTION_TYPES
    return render(request, 'admin_panel/cms/homepage_section_form.html', {
        'section_types': section_types, 'action': 'Create'
    })


@_admin_required
def cms_homepage_section_edit(request, pk):
    s = get_object_or_404(HomepageSection, pk=pk)
    if request.method == 'POST':
        s.section_type = request.POST.get('section_type', s.section_type)
        s.title        = request.POST.get('title', '')
        s.subtitle     = request.POST.get('subtitle', '')
        s.content      = request.POST.get('content', '')
        s.cta_text     = request.POST.get('cta_text', '')
        s.cta_url      = request.POST.get('cta_url', '')
        s.cta2_text    = request.POST.get('cta2_text', '')
        s.cta2_url     = request.POST.get('cta2_url', '')
        s.bg_color     = request.POST.get('bg_color', '')
        s.text_color   = request.POST.get('text_color', '')
        s.order        = int(request.POST.get('order', s.order))
        s.is_visible   = request.POST.get('is_visible') == 'on'
        s.video_url    = request.POST.get('video_url', '')
        if 'image' in request.FILES:
            s.image = request.FILES['image']
        data_raw = request.POST.get('data', '{}')
        try:
            s.data = json.loads(data_raw)
        except Exception:
            pass
        s.save()
        messages.success(request, 'Section updated.')
        return redirect('cms_homepage')
    return render(request, 'admin_panel/cms/homepage_section_form.html', {
        'section': s, 'section_types': HomepageSection.SECTION_TYPES, 'action': 'Edit'
    })


@_admin_required
@require_POST
def cms_homepage_section_delete(request, pk):
    s = get_object_or_404(HomepageSection, pk=pk)
    s.delete()
    messages.success(request, 'Section deleted.')
    return redirect('cms_homepage')


@_admin_required
@require_POST
def cms_homepage_reorder(request):
    """AJAX: receive ordered list of section PKs and update order field."""
    try:
        data = json.loads(request.body)
        for idx, pk in enumerate(data.get('order', [])):
            HomepageSection.objects.filter(pk=pk).update(order=idx)
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


# ── Menu Manager ──────────────────────────────────────────────────────────────

@_admin_required
def cms_menus(request):
    menus = Menu.objects.prefetch_related('items').all()
    return render(request, 'admin_panel/cms/menus.html', {'menus': menus})


@_admin_required
def cms_menu_edit(request, location):
    menu, _ = Menu.objects.get_or_create(
        location=location,
        defaults={'name': location.replace('_', ' ').title()}
    )
    items = menu.items.filter(parent=None).prefetch_related('children')
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_item':
            MenuItem.objects.create(
                menu=menu,
                label=request.POST.get('label', ''),
                url=request.POST.get('url', '/'),
                icon=request.POST.get('icon', ''),
                order=menu.items.count(),
                open_new_tab=request.POST.get('open_new_tab') == 'on',
                requires_login=request.POST.get('requires_login') == 'on',
            )
            messages.success(request, 'Menu item added.')
        elif action == 'delete_item':
            MenuItem.objects.filter(pk=request.POST.get('item_pk'), menu=menu).delete()
            messages.success(request, 'Menu item removed.')
        elif action == 'toggle':
            menu.is_active = not menu.is_active
            menu.save()
        return redirect('cms_menu_edit', location=location)
    locations = Menu.LOCATIONS
    return render(request, 'admin_panel/cms/menu_edit.html', {
        'menu': menu, 'items': items, 'locations': locations
    })


# ── Static Pages ──────────────────────────────────────────────────────────────

@_admin_required
def cms_pages(request):
    pages = StaticPage.objects.all().order_by('title')
    return render(request, 'admin_panel/cms/pages.html', {'pages': pages})


@_admin_required
def cms_page_create(request):
    if request.method == 'POST':
        from django.utils.text import slugify
        title = request.POST.get('title', '')
        slug  = request.POST.get('slug', '') or slugify(title)
        if StaticPage.objects.filter(slug=slug).exists():
            messages.error(request, f'Slug "{slug}" already exists.')
            return render(request, 'admin_panel/cms/page_form.html', {'action': 'Create'})
        page = StaticPage.objects.create(
            title=title, slug=slug,
            content=request.POST.get('content', ''),
            excerpt=request.POST.get('excerpt', ''),
            status=request.POST.get('status', 'draft'),
            show_in_footer=request.POST.get('show_in_footer') == 'on',
            show_in_nav=request.POST.get('show_in_nav') == 'on',
            meta_title=request.POST.get('meta_title', ''),
            meta_description=request.POST.get('meta_description', ''),
        )
        messages.success(request, f'Page "{page.title}" created.')
        return redirect('cms_pages')
    return render(request, 'admin_panel/cms/page_form.html', {'action': 'Create'})


@_admin_required
def cms_page_edit(request, pk):
    page = get_object_or_404(StaticPage, pk=pk)
    if request.method == 'POST':
        page.title       = request.POST.get('title', page.title)
        page.content     = request.POST.get('content', page.content)
        page.excerpt     = request.POST.get('excerpt', '')
        page.status      = request.POST.get('status', page.status)
        page.show_in_footer = request.POST.get('show_in_footer') == 'on'
        page.show_in_nav    = request.POST.get('show_in_nav') == 'on'
        page.meta_title       = request.POST.get('meta_title', '')
        page.meta_description = request.POST.get('meta_description', '')
        page.save()
        messages.success(request, 'Page updated.')
        return redirect('cms_pages')
    return render(request, 'admin_panel/cms/page_form.html', {'page': page, 'action': 'Edit'})


@_admin_required
@require_POST
def cms_page_delete(request, pk):
    page = get_object_or_404(StaticPage, pk=pk)
    page.delete()
    messages.success(request, 'Page deleted.')
    return redirect('cms_pages')


# ── SEO ───────────────────────────────────────────────────────────────────────

@_admin_required
def cms_seo(request):
    global_seo = GlobalSEO.get()
    page_seos  = PageSEO.objects.all().order_by('path')
    if request.method == 'POST':
        action = request.POST.get('action', 'global')
        if action == 'global':
            fields = [
                'meta_title', 'meta_description', 'meta_keywords',
                'og_title', 'og_description', 'twitter_card', 'twitter_handle',
                'canonical_domain', 'robots_txt',
                'google_site_verification', 'bing_site_verification',
            ]
            for f in fields:
                setattr(global_seo, f, request.POST.get(f, ''))
            global_seo.allow_indexing = request.POST.get('allow_indexing') == 'on'
            if 'og_image' in request.FILES:
                global_seo.og_image = request.FILES['og_image']
            global_seo.save()
            _clear_cache()
            messages.success(request, 'Global SEO settings saved.')
        elif action == 'add_page_seo':
            path = request.POST.get('path', '').strip()
            if path:
                obj, _ = PageSEO.objects.get_or_create(path=path)
                obj.meta_title       = request.POST.get('page_meta_title', '')
                obj.meta_description = request.POST.get('page_meta_description', '')
                obj.no_index         = request.POST.get('no_index') == 'on'
                obj.canonical_url    = request.POST.get('canonical_url', '')
                obj.save()
                cache.delete(f'page_seo_{path}')
                messages.success(request, f'SEO for {path} saved.')
        elif action == 'delete_page_seo':
            PageSEO.objects.filter(pk=request.POST.get('page_seo_pk')).delete()
            messages.success(request, 'Page SEO entry removed.')
        return redirect('cms_seo')
    return render(request, 'admin_panel/cms/seo.html', {
        'global_seo': global_seo, 'page_seos': page_seos
    })


@_admin_required
def cms_robots_txt(request):
    """Serve robots.txt from CMS."""
    try:
        seo = GlobalSEO.get()
        content = seo.robots_txt
    except Exception:
        content = 'User-agent: *\nAllow: /'
    return HttpResponse(content, content_type='text/plain')


# ── Announcements ─────────────────────────────────────────────────────────────

@_admin_required
def cms_announcements(request):
    announcements = Announcement.objects.all().order_by('-created_at')
    return render(request, 'admin_panel/cms/announcements.html', {
        'announcements': announcements, 'types': Announcement.TYPES
    })


@_admin_required
def cms_announcement_create(request):
    if request.method == 'POST':
        a = Announcement()
        a.announcement_type = request.POST.get('announcement_type', 'banner')
        a.title      = request.POST.get('title', '')
        a.message    = request.POST.get('message', '')
        a.link_text  = request.POST.get('link_text', '')
        a.link_url   = request.POST.get('link_url', '')
        a.bg_color   = request.POST.get('bg_color', '#6c47ff')
        a.text_color = request.POST.get('text_color', '#ffffff')
        a.is_active  = request.POST.get('is_active') == 'on'
        a.is_dismissible = request.POST.get('is_dismissible') == 'on'
        a.show_to_logged_in = request.POST.get('show_to_logged_in') == 'on'
        a.show_to_guests    = request.POST.get('show_to_guests') == 'on'
        starts = request.POST.get('starts_at', '')
        ends   = request.POST.get('ends_at', '')
        if starts:
            from django.utils.dateparse import parse_datetime
            a.starts_at = parse_datetime(starts)
        if ends:
            from django.utils.dateparse import parse_datetime
            a.ends_at = parse_datetime(ends)
        a.save()
        _clear_cache()
        messages.success(request, 'Announcement created.')
        return redirect('cms_announcements')
    return render(request, 'admin_panel/cms/announcement_form.html', {
        'types': Announcement.TYPES, 'action': 'Create'
    })


@_admin_required
@require_POST
def cms_announcement_toggle(request, pk):
    a = get_object_or_404(Announcement, pk=pk)
    a.is_active = not a.is_active
    a.save()
    _clear_cache()
    return JsonResponse({'active': a.is_active})


@_admin_required
@require_POST
def cms_announcement_delete(request, pk):
    get_object_or_404(Announcement, pk=pk).delete()
    _clear_cache()
    messages.success(request, 'Announcement deleted.')
    return redirect('cms_announcements')


# ── Email Templates ───────────────────────────────────────────────────────────

@_admin_required
def cms_email_templates(request):
    templates = EmailTemplate.objects.all().order_by('template_type')
    all_types = EmailTemplate.TEMPLATE_TYPES
    return render(request, 'admin_panel/cms/email_templates.html', {
        'templates': templates, 'all_types': all_types
    })


@_admin_required
def cms_email_template_edit(request, template_type):
    obj, created = EmailTemplate.objects.get_or_create(
        template_type=template_type,
        defaults={
            'subject': f'{template_type.replace("_"," ").title()} — NEXUS',
            'body_html': '<p>Hello {{user.username}},</p>\n<p>Your message here.</p>',
        }
    )
    if request.method == 'POST':
        obj.subject    = request.POST.get('subject', obj.subject)
        obj.body_html  = request.POST.get('body_html', obj.body_html)
        obj.body_text  = request.POST.get('body_text', '')
        obj.from_name  = request.POST.get('from_name', '')
        obj.from_email = request.POST.get('from_email', '')
        obj.is_active  = request.POST.get('is_active') == 'on'
        obj.save()
        messages.success(request, 'Email template saved.')
        return redirect('cms_email_templates')
    return render(request, 'admin_panel/cms/email_template_form.html', {
        'obj': obj, 'is_new': created
    })


# ── Scripts ───────────────────────────────────────────────────────────────────

@_admin_required
def cms_scripts(request):
    scripts = ScriptInjection.objects.all().order_by('position', 'order')
    return render(request, 'admin_panel/cms/scripts.html', {'scripts': scripts})


@_admin_required
def cms_script_create(request):
    if request.method == 'POST':
        ScriptInjection.objects.create(
            name=request.POST.get('name', ''),
            description=request.POST.get('description', ''),
            position=request.POST.get('position', 'head'),
            script=request.POST.get('script', ''),
            is_active=request.POST.get('is_active') == 'on',
            load_on_pages=request.POST.get('load_on_pages', '*'),
            order=int(request.POST.get('order', 0)),
        )
        _clear_cache()
        messages.success(request, 'Script added.')
        return redirect('cms_scripts')
    return render(request, 'admin_panel/cms/script_form.html', {
        'positions': ScriptInjection.POSITIONS, 'action': 'Add'
    })


@_admin_required
def cms_script_edit(request, pk):
    script = get_object_or_404(ScriptInjection, pk=pk)
    if request.method == 'POST':
        script.name        = request.POST.get('name', script.name)
        script.description = request.POST.get('description', '')
        script.position    = request.POST.get('position', script.position)
        script.script      = request.POST.get('script', script.script)
        script.is_active   = request.POST.get('is_active') == 'on'
        script.load_on_pages = request.POST.get('load_on_pages', '*')
        script.order       = int(request.POST.get('order', 0))
        script.save()
        _clear_cache()
        messages.success(request, 'Script updated.')
        return redirect('cms_scripts')
    return render(request, 'admin_panel/cms/script_form.html', {
        'script': script, 'positions': ScriptInjection.POSITIONS, 'action': 'Edit'
    })


@_admin_required
@require_POST
def cms_script_toggle(request, pk):
    s = get_object_or_404(ScriptInjection, pk=pk)
    s.is_active = not s.is_active
    s.save()
    _clear_cache()
    return JsonResponse({'active': s.is_active})


@_admin_required
@require_POST
def cms_script_delete(request, pk):
    get_object_or_404(ScriptInjection, pk=pk).delete()
    _clear_cache()
    messages.success(request, 'Script deleted.')
    return redirect('cms_scripts')


# ── Maintenance Mode ──────────────────────────────────────────────────────────

@_admin_required
def cms_maintenance(request):
    cfg = MaintenanceConfig.get()
    if request.method == 'POST':
        cfg.is_active        = request.POST.get('is_active') == 'on'
        cfg.title            = request.POST.get('title', cfg.title)
        cfg.message          = request.POST.get('message', cfg.message)
        cfg.allow_admins     = request.POST.get('allow_admins') == 'on'
        cfg.allowed_ips      = request.POST.get('allowed_ips', '')
        est = request.POST.get('estimated_return', '')
        if est:
            from django.utils.dateparse import parse_datetime
            cfg.estimated_return = parse_datetime(est)
        else:
            cfg.estimated_return = None
        cfg.save()
        _clear_cache()
        messages.success(request, f'Maintenance mode {"enabled" if cfg.is_active else "disabled"}.')
        return redirect('cms_maintenance')
    return render(request, 'admin_panel/cms/maintenance.html', {'cfg': cfg})


# ── Feature Flags ─────────────────────────────────────────────────────────────

@_admin_required
def cms_feature_flags(request):
    from django.conf import settings as django_settings
    # Ensure all default flags exist in DB
    for key, default_val in django_settings.DEFAULT_FEATURE_FLAGS.items():
        FeatureFlag.objects.get_or_create(
            key=key,
            defaults={
                'name': key.replace('_', ' ').title(),
                'is_enabled': default_val,
            }
        )
    flags = FeatureFlag.objects.all().order_by('module', 'key')
    return render(request, 'admin_panel/cms/feature_flags.html', {'flags': flags})


@_admin_required
@require_POST
def cms_feature_flag_toggle(request, pk):
    flag = get_object_or_404(FeatureFlag, pk=pk)
    flag.is_enabled = not flag.is_enabled
    flag.save()
    return JsonResponse({'enabled': flag.is_enabled})


@_admin_required
@require_POST
def cms_feature_flag_save(request, pk):
    flag = get_object_or_404(FeatureFlag, pk=pk)
    flag.rollout_pct = min(100, max(0, int(request.POST.get('rollout_pct', 100))))
    flag.name        = request.POST.get('name', flag.name)
    flag.description = request.POST.get('description', flag.description)
    flag.save()
    messages.success(request, f'Feature flag "{flag.key}" updated.')
    return redirect('cms_feature_flags')


# ── Public: Static Pages ──────────────────────────────────────────────────────

def static_page_view(request, slug):
    # Default content for standard pages
    defaults = {
        'privacy': ('Privacy Policy', '<h2>Privacy Policy</h2><p>We respect your privacy. This page is under construction — please check back soon.</p>'),
        'terms':   ('Terms of Service', '<h2>Terms of Service</h2><p>By using this platform you agree to our terms. This page is under construction — please check back soon.</p>'),
        'about':   ('About Us', '<h2>About Us</h2><p>Welcome to our platform. This page is under construction — please check back soon.</p>'),
        'contact': ('Contact Us', '<h2>Contact Us</h2><p>Please use the contact email in the footer to reach us. This page is under construction.</p>'),
        'faq':     ('FAQ', '<h2>Frequently Asked Questions</h2><p>This page is under construction — please check back soon.</p>'),
    }
    try:
        page = StaticPage.objects.get(slug=slug, status='published')
    except StaticPage.DoesNotExist:
        if slug in defaults:
            title, content = defaults[slug]
            page, _ = StaticPage.objects.get_or_create(
                slug=slug,
                defaults={'title': title, 'content': content, 'status': 'published'},
            )
            if not page.status == 'published':
                return render(request, 'cms/static_page.html', {'page': page})
        else:
            from django.http import Http404
            raise Http404
    return render(request, 'cms/static_page.html', {'page': page})
