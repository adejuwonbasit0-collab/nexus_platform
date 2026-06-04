"""
Unified hub views — CMS, Settings, Automation, System Health
Each is a single URL with tabs handled in the template.
"""
import json, time, logging
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger('nexus')


def _admin(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_admin():
            return redirect('/auth/login/?next=' + request.path)
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


# ─────────────────────────────────────────────────────────────
# CMS HUB  (/admin-panel/cms/)
# ─────────────────────────────────────────────────────────────
@_admin
def cms_hub(request):
    from cms.models import (
        BrandingConfig, ThemeConfig, HomepageSection, GlobalSEO,
        Menu, MenuItem, StaticPage, Announcement, EmailTemplate,
        ScriptInjection, MaintenanceConfig, FeatureFlag, PageSEO
    )
    from django.conf import settings as ds

    ctx = {}
    active_tab = request.GET.get('tab', 'branding')

    # ── POST handlers ────────────────────────────────────────
    if request.method == 'POST':
        action = request.POST.get('_action', '')

        # BRANDING
        if action == 'branding':
            obj = BrandingConfig.get()
            for f in ['site_name','site_tagline','site_description','contact_email',
                      'contact_phone','contact_address','copyright_text',
                      'social_twitter','social_instagram','social_facebook',
                      'social_youtube','social_tiktok','social_discord','social_linkedin']:
                setattr(obj, f, request.POST.get(f, ''))
            for fld in ['logo_primary','logo_dark','logo_footer','logo_email','favicon','social_preview']:
                if fld in request.FILES:
                    setattr(obj, fld, request.FILES[fld])
            obj.save(); cache.delete('cms_branding')
            messages.success(request, 'Branding saved.')
            return redirect('/admin-panel/cms/?tab=branding')

        # THEME
        elif action == 'theme':
            obj = ThemeConfig.get()
            for f in ['primary_color','secondary_color','accent_color','background_color',
                      'surface_color','text_primary','text_secondary','heading_font','body_font',
                      'heading_font_url','body_font_url','base_font_size','border_radius',
                      'max_width','btn_radius','btn_primary_bg','btn_primary_text',
                      'default_mode','custom_css']:
                setattr(obj, f, request.POST.get(f, getattr(obj, f)))
            obj.save(); cache.delete('cms_theme')
            messages.success(request, 'Theme saved — live immediately.')
            return redirect('/admin-panel/cms/?tab=theme')

        # HOMEPAGE SECTION CRUD
        elif action == 'hp_create':
            s = HomepageSection()
            for f in ['section_type','title','subtitle','content','cta_text','cta_url',
                      'cta2_text','cta2_url','bg_color','text_color','video_url']:
                setattr(s, f, request.POST.get(f,''))
            s.order = int(request.POST.get('order', 0))
            s.is_visible = request.POST.get('is_visible') == 'on'
            if 'image' in request.FILES: s.image = request.FILES['image']
            try: s.data = json.loads(request.POST.get('data','{}'))
            except: s.data = {}
            s.save()
            messages.success(request, 'Section created.')
            return redirect('/admin-panel/cms/?tab=homepage')
        elif action == 'hp_delete':
            HomepageSection.objects.filter(pk=request.POST.get('pk')).delete()
            messages.success(request, 'Section deleted.')
            return redirect('/admin-panel/cms/?tab=homepage')
        elif action == 'hp_toggle':
            s = get_object_or_404(HomepageSection, pk=request.POST.get('pk'))
            s.is_visible = not s.is_visible; s.save()
            return JsonResponse({'visible': s.is_visible})
        elif action == 'hp_reorder':
            try:
                data = json.loads(request.body)
                for i,pk in enumerate(data.get('order',[])):
                    HomepageSection.objects.filter(pk=pk).update(order=i)
                return JsonResponse({'ok': True})
            except: return JsonResponse({'ok': False}, status=400)

        # MENUS
        elif action == 'menu_add_item':
            location = request.POST.get('location','primary')
            menu, _ = Menu.objects.get_or_create(location=location,
                        defaults={'name': location.replace('_',' ').title()})
            MenuItem.objects.create(
                menu=menu, label=request.POST.get('label',''),
                url=request.POST.get('url','/'), icon=request.POST.get('icon',''),
                order=menu.items.count(),
                open_new_tab=request.POST.get('open_new_tab')=='on',
                requires_login=request.POST.get('requires_login')=='on',
            )
            messages.success(request, 'Menu item added.')
            return redirect('/admin-panel/cms/?tab=menus')
        elif action == 'menu_delete_item':
            MenuItem.objects.filter(pk=request.POST.get('item_pk')).delete()
            messages.success(request, 'Item removed.')
            return redirect('/admin-panel/cms/?tab=menus')

        # STATIC PAGES
        elif action == 'page_create':
            from django.utils.text import slugify
            title = request.POST.get('title','')
            slug  = request.POST.get('slug','') or slugify(title)
            if StaticPage.objects.filter(slug=slug).exists():
                messages.error(request, f'Slug "{slug}" already taken.')
            else:
                StaticPage.objects.create(
                    title=title, slug=slug,
                    content=request.POST.get('content',''),
                    status=request.POST.get('status','draft'),
                    show_in_footer=request.POST.get('show_in_footer')=='on',
                    show_in_nav=request.POST.get('show_in_nav')=='on',
                    meta_title=request.POST.get('meta_title',''),
                    meta_description=request.POST.get('meta_description',''),
                )
                messages.success(request, f'Page "{title}" created.')
            return redirect('/admin-panel/cms/?tab=pages')
        elif action == 'page_edit':
            p = get_object_or_404(StaticPage, pk=request.POST.get('pk'))
            p.title=request.POST.get('title',p.title)
            p.content=request.POST.get('content',p.content)
            p.status=request.POST.get('status',p.status)
            p.show_in_footer=request.POST.get('show_in_footer')=='on'
            p.show_in_nav=request.POST.get('show_in_nav')=='on'
            p.meta_title=request.POST.get('meta_title','')
            p.meta_description=request.POST.get('meta_description','')
            p.save(); messages.success(request, 'Page updated.')
            return redirect('/admin-panel/cms/?tab=pages')
        elif action == 'page_delete':
            StaticPage.objects.filter(pk=request.POST.get('pk')).delete()
            messages.success(request, 'Page deleted.')
            return redirect('/admin-panel/cms/?tab=pages')

        # SEO
        elif action == 'seo_global':
            seo = GlobalSEO.get()
            for f in ['meta_title','meta_description','meta_keywords','og_title',
                      'og_description','twitter_card','twitter_handle','canonical_domain',
                      'robots_txt','google_site_verification','bing_site_verification']:
                setattr(seo, f, request.POST.get(f,''))
            seo.allow_indexing = request.POST.get('allow_indexing')=='on'
            if 'og_image' in request.FILES: seo.og_image = request.FILES['og_image']
            seo.save(); cache.delete('cms_seo')
            messages.success(request, 'SEO settings saved.')
            return redirect('/admin-panel/cms/?tab=seo')

        # ANNOUNCEMENTS
        elif action == 'ann_create':
            from django.utils.dateparse import parse_datetime
            a = Announcement()
            a.announcement_type=request.POST.get('announcement_type','banner')
            a.title=request.POST.get('title','')
            a.message=request.POST.get('message','')
            a.link_text=request.POST.get('link_text','')
            a.link_url=request.POST.get('link_url','')
            a.bg_color=request.POST.get('bg_color','#7c5cfc')
            a.text_color=request.POST.get('text_color','#ffffff')
            a.is_active=request.POST.get('is_active')=='on'
            a.is_dismissible=request.POST.get('is_dismissible')=='on'
            a.show_to_logged_in=request.POST.get('show_to_logged_in')=='on'
            a.show_to_guests=request.POST.get('show_to_guests')=='on'
            starts=request.POST.get('starts_at','')
            ends=request.POST.get('ends_at','')
            if starts: a.starts_at=parse_datetime(starts)
            if ends: a.ends_at=parse_datetime(ends)
            a.save(); cache.delete('cms_active_announcement')
            messages.success(request, 'Announcement created.')
            return redirect('/admin-panel/cms/?tab=announcements')
        elif action == 'ann_toggle':
            a = get_object_or_404(Announcement, pk=request.POST.get('pk'))
            a.is_active=not a.is_active; a.save()
            cache.delete('cms_active_announcement')
            return JsonResponse({'active': a.is_active})
        elif action == 'ann_delete':
            Announcement.objects.filter(pk=request.POST.get('pk')).delete()
            cache.delete('cms_active_announcement')
            messages.success(request, 'Announcement deleted.')
            return redirect('/admin-panel/cms/?tab=announcements')

        # EMAIL TEMPLATES
        elif action == 'email_tmpl_save':
            ttype = request.POST.get('template_type','')
            obj, _ = EmailTemplate.objects.get_or_create(
                template_type=ttype,
                defaults={'subject':'New Template','body_html':'<p>Hello</p>'}
            )
            obj.subject=request.POST.get('subject',obj.subject)
            obj.body_html=request.POST.get('body_html',obj.body_html)
            obj.body_text=request.POST.get('body_text','')
            obj.from_name=request.POST.get('from_name','')
            obj.from_email=request.POST.get('from_email','')
            obj.is_active=request.POST.get('is_active')=='on'
            obj.save()
            messages.success(request, 'Template saved.')
            return redirect('/admin-panel/cms/?tab=email_templates')

        # SCRIPTS
        elif action == 'script_create':
            ScriptInjection.objects.create(
                name=request.POST.get('name',''),
                description=request.POST.get('description',''),
                position=request.POST.get('position','head'),
                script=request.POST.get('script',''),
                is_active=request.POST.get('is_active')=='on',
                load_on_pages=request.POST.get('load_on_pages','*'),
                order=int(request.POST.get('order',0)),
            )
            cache.delete('cms_scripts')
            messages.success(request, 'Script added.')
            return redirect('/admin-panel/cms/?tab=scripts')
        elif action == 'script_edit':
            s = get_object_or_404(ScriptInjection, pk=request.POST.get('pk'))
            s.name=request.POST.get('name',s.name)
            s.description=request.POST.get('description','')
            s.position=request.POST.get('position',s.position)
            s.script=request.POST.get('script',s.script)
            s.is_active=request.POST.get('is_active')=='on'
            s.load_on_pages=request.POST.get('load_on_pages','*')
            s.order=int(request.POST.get('order',0))
            s.save(); cache.delete('cms_scripts')
            messages.success(request, 'Script updated.')
            return redirect('/admin-panel/cms/?tab=scripts')
        elif action == 'script_toggle':
            s = get_object_or_404(ScriptInjection, pk=request.POST.get('pk'))
            s.is_active=not s.is_active; s.save(); cache.delete('cms_scripts')
            return JsonResponse({'active': s.is_active})
        elif action == 'script_delete':
            ScriptInjection.objects.filter(pk=request.POST.get('pk')).delete()
            cache.delete('cms_scripts')
            messages.success(request, 'Script deleted.')
            return redirect('/admin-panel/cms/?tab=scripts')

        # MAINTENANCE
        elif action == 'maintenance':
            from django.utils.dateparse import parse_datetime
            cfg = MaintenanceConfig.get()
            cfg.is_active=request.POST.get('is_active')=='on'
            cfg.title=request.POST.get('title',cfg.title)
            cfg.message=request.POST.get('message',cfg.message)
            cfg.allow_admins=request.POST.get('allow_admins')=='on'
            cfg.allowed_ips=request.POST.get('allowed_ips','')
            est=request.POST.get('estimated_return','')
            cfg.estimated_return=parse_datetime(est) if est else None
            cfg.save(); cache.delete('cms_maintenance')
            messages.success(request, f'Maintenance mode {"ENABLED" if cfg.is_active else "disabled"}.')
            return redirect('/admin-panel/cms/?tab=maintenance')

        # FEATURE FLAGS
        elif action == 'flag_toggle':
            flag = get_object_or_404(FeatureFlag, pk=request.POST.get('pk'))
            flag.is_enabled=not flag.is_enabled; flag.save()
            return JsonResponse({'enabled': flag.is_enabled})
        elif action == 'flag_save':
            flag = get_object_or_404(FeatureFlag, pk=request.POST.get('pk'))
            flag.rollout_pct=min(100,max(0,int(request.POST.get('rollout_pct',100))))
            flag.save()
            messages.success(request, 'Flag updated.')
            return redirect('/admin-panel/cms/?tab=feature_flags')

    # ── Build context for all tabs ──────────────────────────────
    ctx['active_tab']   = active_tab
    ctx['branding']     = BrandingConfig.get()
    ctx['theme_obj']    = ThemeConfig.get()
    ctx['hp_sections']  = HomepageSection.objects.all()
    ctx['hp_types']     = HomepageSection.SECTION_TYPES
    ctx['menus']        = Menu.objects.prefetch_related('items__children').all()
    ctx['menu_locs']    = Menu.LOCATIONS
    ctx['pages']        = StaticPage.objects.all().order_by('title')
    ctx['global_seo']   = GlobalSEO.get()
    ctx['page_seos']    = PageSEO.objects.all().order_by('path')
    ctx['announcements']= Announcement.objects.all().order_by('-created_at')
    ctx['ann_types']    = Announcement.TYPES
    ctx['email_templates'] = EmailTemplate.objects.all()
    ctx['email_types']  = EmailTemplate.TEMPLATE_TYPES
    ctx['scripts']      = ScriptInjection.objects.all().order_by('position','order')
    ctx['script_positions'] = ScriptInjection.POSITIONS
    ctx['maintenance']  = MaintenanceConfig.get()
    ctx['flags']        = FeatureFlag.objects.all().order_by('module','key')

    # Ensure all default flags exist
    for key, default_val in ds.DEFAULT_FEATURE_FLAGS.items():
        FeatureFlag.objects.get_or_create(key=key,
            defaults={'name':key.replace('_',' ').title(),'is_enabled':default_val})

    return render(request, 'admin_panel/cms_hub.html', ctx)


# ─────────────────────────────────────────────────────────────
# AUTOMATION HUB  (/admin-panel/automation/)
# ─────────────────────────────────────────────────────────────
@_admin
def automation_hub(request):
    from automation.models import (ScheduledJob, WorkflowDefinition,
                                   WorkflowAction, WorkflowRun, EmailSequence)
    ctx = {'active_tab': request.GET.get('tab','jobs')}

    if request.method == 'POST':
        action = request.POST.get('_action','')
        if action == 'job_create':
            ScheduledJob.objects.create(
                name=request.POST.get('name',''),
                description=request.POST.get('description',''),
                task_name=request.POST.get('task_name',''),
                interval=request.POST.get('interval','daily'),
                cron_expr=request.POST.get('cron_expr',''),
                status='active', created_by=request.user,
            )
            messages.success(request, 'Job created.')
            return redirect('/admin-panel/automation/?tab=jobs')

        elif action == 'wf_create':
            wf = WorkflowDefinition.objects.create(
                name=request.POST.get('name',''),
                description=request.POST.get('description',''),
                trigger_event=request.POST.get('trigger_event',''),
                is_active=request.POST.get('is_active')=='on',
            )
            messages.success(request, f'Workflow "{wf.name}" created.')
            return redirect('/admin-panel/automation/?tab=workflows')

        elif action == 'wf_add_action':
            wf = get_object_or_404(WorkflowDefinition, pk=request.POST.get('wf_pk'))
            try: config = json.loads(request.POST.get('config','{}'))
            except: config = {}
            WorkflowAction.objects.create(
                workflow=wf, action_type=request.POST.get('action_type','send_email'),
                order=wf.actions.count(), config=config,
            )
            messages.success(request, 'Action added.')
            return redirect('/admin-panel/automation/?tab=workflows')

        elif action == 'wf_delete_action':
            WorkflowAction.objects.filter(pk=request.POST.get('action_pk')).delete()
            messages.success(request, 'Action removed.')
            return redirect('/admin-panel/automation/?tab=workflows')

    ctx['jobs']         = ScheduledJob.objects.all()
    ctx['intervals']    = ScheduledJob.INTERVALS
    ctx['workflows']    = WorkflowDefinition.objects.prefetch_related('actions').all()
    ctx['trigger_events'] = WorkflowDefinition.TRIGGER_EVENTS
    ctx['action_types'] = WorkflowAction.ACTION_TYPES
    ctx['recent_runs']  = WorkflowRun.objects.select_related('workflow').order_by('-started_at')[:30]
    ctx['stats'] = {
        'active_jobs':      ScheduledJob.objects.filter(status='active').count(),
        'active_workflows': WorkflowDefinition.objects.filter(is_active=True).count(),
        'total_runs':       WorkflowRun.objects.count(),
        'failed_runs':      WorkflowRun.objects.filter(status='failed').count(),
    }
    return render(request, 'admin_panel/automation_hub.html', ctx)


@_admin
@require_POST
def job_toggle(request, pk):
    from automation.models import ScheduledJob
    job = get_object_or_404(ScheduledJob, pk=pk)
    job.status = 'paused' if job.status == 'active' else 'active'
    job.save()
    return JsonResponse({'status': job.status})


@_admin
@require_POST
def job_delete(request, pk):
    from automation.models import ScheduledJob
    get_object_or_404(ScheduledJob, pk=pk).delete()
    messages.success(request, 'Job deleted.')
    return redirect('/admin-panel/automation/?tab=jobs')


@_admin
@require_POST
def wf_toggle(request, pk):
    from automation.models import WorkflowDefinition
    wf = get_object_or_404(WorkflowDefinition, pk=pk)
    wf.is_active = not wf.is_active; wf.save()
    return JsonResponse({'active': wf.is_active})


@_admin
@require_POST
def wf_delete(request, pk):
    from automation.models import WorkflowDefinition
    get_object_or_404(WorkflowDefinition, pk=pk).delete()
    messages.success(request, 'Workflow deleted.')
    return redirect('/admin-panel/automation/?tab=workflows')


@_admin
@require_POST
def wf_test(request, pk):
    from automation.models import WorkflowDefinition
    from automation.engine import WorkflowEngine
    wf = get_object_or_404(WorkflowDefinition, pk=pk)
    WorkflowEngine.fire(wf.trigger_event, {
        'test': True, 'user_id': request.user.pk,
        'user_email': request.user.email, 'username': request.user.username,
    })
    messages.success(request, f'Test fire sent for "{wf.name}".')
    return redirect('/admin-panel/automation/?tab=workflows')


# ─────────────────────────────────────────────────────────────
# SYSTEM HUB  (/admin-panel/system/)
# ─────────────────────────────────────────────────────────────
@_admin
def system_hub(request):
    from observability.health import SystemHealthChecker
    from observability.models import AuditLog, SecurityAlert, ErrorLog, SystemMetricSnapshot
    from django.core.paginator import Paginator

    ctx = {'active_tab': request.GET.get('tab', 'health')}
    checker = SystemHealthChecker()
    ctx['health'] = checker.get_metrics()

    # Audit logs with filter
    aq  = AuditLog.objects.select_related('user').order_by('-timestamp')
    af  = request.GET.get('action_filter','')
    if af: aq = aq.filter(action=af)
    ctx['audit_page']   = Paginator(aq, 40).get_page(request.GET.get('apage',1))
    ctx['audit_actions']= AuditLog.ACTIONS
    ctx['action_filter']= af

    # Error logs
    eq  = ErrorLog.objects.select_related('user').order_by('-occurred_at')
    lf  = request.GET.get('level_filter','')
    if lf: eq = eq.filter(level=lf)
    ctx['error_page']   = Paginator(eq, 40).get_page(request.GET.get('epage',1))
    ctx['error_levels'] = ErrorLog.LEVELS
    ctx['level_filter'] = lf

    # Alerts
    ctx['open_alerts']   = SecurityAlert.objects.filter(is_resolved=False).order_by('-created_at')
    ctx['closed_alerts'] = SecurityAlert.objects.filter(is_resolved=True).order_by('-resolved_at')[:20]

    # Stats
    now = timezone.now()
    ctx['sys_stats'] = {
        'errors_24h': ErrorLog.objects.filter(occurred_at__gte=now-__import__('datetime').timedelta(hours=24)).count(),
        'open_alerts': SecurityAlert.objects.filter(is_resolved=False).count(),
        'audit_today': AuditLog.objects.filter(timestamp__date=now.date()).count(),
        'snapshots': SystemMetricSnapshot.objects.count(),
    }
    ctx['snapshots'] = SystemMetricSnapshot.objects.order_by('-captured_at')[:12]

    return render(request, 'admin_panel/system_hub.html', ctx)


@_admin
def system_health_api(request):
    from observability.health import SystemHealthChecker
    return JsonResponse(SystemHealthChecker().get_metrics())


@_admin
@require_POST
def clear_cache(request):
    cache.clear()
    messages.success(request, 'All caches cleared successfully.')
    return redirect('/admin-panel/system/?tab=health')


@_admin
@require_POST
def resolve_alert(request, pk):
    from observability.models import SecurityAlert
    alert = get_object_or_404(SecurityAlert, pk=pk)
    alert.is_resolved = True
    alert.resolved_at = timezone.now()
    alert.resolved_by = request.user
    alert.save()
    messages.success(request, 'Alert resolved.')
    return redirect('/admin-panel/system/?tab=alerts')


# ─────────────────────────────────────────────────────────────
# SETTINGS HUB  (/admin-panel/settings/)
# ─────────────────────────────────────────────────────────────
@_admin
def settings_hub(request):
    from .models import SiteSettings, AIProviderSettings, EmailConfig, GatewayConfig
    from django.conf import settings as ds

    ctx = {'active_tab': request.GET.get('tab', 'general')}

    if request.method == 'POST':
        action = request.POST.get('_action','')

        # GENERAL
        if action == 'general':
            keys = ['site_name','site_description','site_url','contact_email',
                    'support_email','max_upload_size_mb','enable_registration',
                    'default_content_tier']
            for k in keys:
                SiteSettings.objects.update_or_create(key=k, defaults={'value': request.POST.get(k,'')})
            cache.delete('site_settings_all')
            messages.success(request, 'General settings saved.')
            return redirect('/admin-panel/settings/?tab=general')

        # EMAIL
        elif action == 'email':
            cfg = EmailConfig.get()
            cfg.backend    = request.POST.get('backend', 'smtp')
            cfg.host       = request.POST.get('host','')
            cfg.port       = int(request.POST.get('port', 587) or 587)
            cfg.encryption = request.POST.get('encryption','tls')
            cfg.username   = request.POST.get('username','')
            pwd = request.POST.get('password','')
            if pwd: cfg.password = pwd   # only overwrite if provided
            cfg.api_key    = request.POST.get('api_key','')
            cfg.from_email = request.POST.get('from_email','')
            cfg.from_name  = request.POST.get('from_name','')
            cfg.is_active  = request.POST.get('is_active')=='on'
            cfg.test_recipient = request.POST.get('test_recipient','')
            cfg.save()
            if cfg.is_active:
                cfg.apply_to_django()
            messages.success(request, 'Email config saved.')
            return redirect('/admin-panel/settings/?tab=email')

        # PAYMENTS
        elif action == 'payment':
            for gw in ['paystack','stripe','flutterwave','wave','bank']:
                pub  = request.POST.get(f'{gw}_public','')
                sec  = request.POST.get(f'{gw}_secret','')
                whk  = request.POST.get(f'{gw}_webhook','')
                cur  = request.POST.get(f'{gw}_currency','NGN')
                test = request.POST.get(f'{gw}_test')=='on'
                act  = request.POST.get(f'{gw}_active')=='on'
                extra_data = {}
                if gw == 'bank':
                    extra_data = {
                        'bank_name':    request.POST.get('bank_bank_name',''),
                        'account_name': request.POST.get('bank_account_name',''),
                        'account_number': request.POST.get('bank_account_number',''),
                        'routing_number': request.POST.get('bank_routing_number',''),
                        'instructions': request.POST.get('bank_instructions',''),
                    }
                obj, _ = GatewayConfig.objects.get_or_create(gateway=gw)
                if pub: obj.public_key  = pub
                if sec: obj.secret_key  = sec
                if whk: obj.webhook_secret = whk
                obj.currency    = cur
                obj.is_test_mode= test
                obj.is_active   = act
                if extra_data:  obj.extra = extra_data
                obj.save()
            messages.success(request, 'Payment gateways saved.')
            return redirect('/admin-panel/settings/?tab=payments')

        # AI
        elif action == 'ai':
            for prov in ['openai','anthropic','stability']:
                key = request.POST.get(f'{prov}_key','').strip()
                model = request.POST.get(f'{prov}_model','').strip()
                active = request.POST.get(f'{prov}_active')=='on'
                obj, _ = AIProviderSettings.objects.get_or_create(provider=prov)
                if key: obj.api_key = key
                if model: obj.model_name = model
                obj.is_active = active
                obj.save()
            messages.success(request, 'AI settings saved.')
            return redirect('/admin-panel/settings/?tab=ai')

    # Build context
    qs = SiteSettings.objects.all()
    ctx['site'] = {s.key: s.value for s in qs}
    ctx['email_cfg']   = EmailConfig.get()
    ctx['email_backends'] = EmailConfig.BACKENDS
    ctx['email_encryptions'] = EmailConfig.ENCRYPTIONS
    ctx['gateways']    = {g.gateway: g for g in GatewayConfig.objects.all()}
    ctx['ai_providers']= {p.provider: p for p in AIProviderSettings.objects.all()}
    ctx['currencies']   = ['NGN','USD','GHS','KES','ZAR','GBP','EUR','XOF','XAF']
    return render(request, 'admin_panel/settings_hub.html', ctx)


@_admin
@require_POST
def email_test(request):
    from .models import EmailConfig
    from django.core.mail import send_mail
    from django.conf import settings as ds
    cfg = EmailConfig.get()
    recipient = request.POST.get('recipient', cfg.test_recipient or request.user.email)
    if not recipient:
        messages.error(request, 'No recipient email address.')
        return redirect('/admin-panel/settings/?tab=email')
    try:
        cfg.apply_to_django()
        send_mail(
            subject='NEXUS — Email Test',
            message='This is a test email from your NEXUS platform. Email is configured correctly!',
            from_email=f'{cfg.from_name} <{cfg.from_email}>',
            recipient_list=[recipient],
            fail_silently=False,
        )
        messages.success(request, f'Test email sent to {recipient}.')
    except Exception as e:
        messages.error(request, f'Email failed: {e}')
    return redirect('/admin-panel/settings/?tab=email')
