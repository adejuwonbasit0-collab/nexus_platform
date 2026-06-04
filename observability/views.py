"""Observability admin views — audit logs, system health, error logs, security alerts."""
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta

from .models import AuditLog, SecurityAlert, SystemMetricSnapshot, ErrorLog
from .health import SystemHealthChecker


def _admin_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_admin():
            return redirect('/auth/login/')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


@_admin_required
def system_health(request):
    checker = SystemHealthChecker()
    metrics = checker.get_metrics()

    # Recent snapshots for charts
    snapshots = SystemMetricSnapshot.objects.order_by('-captured_at')[:24]

    # Recent errors
    recent_errors = ErrorLog.objects.filter(is_resolved=False).order_by('-occurred_at')[:10]

    # Unresolved alerts
    active_alerts = SecurityAlert.objects.filter(is_resolved=False).order_by('-created_at')[:10]

    # Stats
    now = timezone.now()
    stats = {
        'total_users':    0,
        'active_today':   AuditLog.objects.filter(timestamp__gte=now - timedelta(hours=24)).values('user').distinct().count(),
        'errors_24h':     ErrorLog.objects.filter(occurred_at__gte=now - timedelta(hours=24)).count(),
        'alerts_open':    SecurityAlert.objects.filter(is_resolved=False).count(),
        'audit_today':    AuditLog.objects.filter(timestamp__gte=now.replace(hour=0, minute=0, second=0)).count(),
    }
    try:
        from accounts.models import User
        stats['total_users'] = User.objects.count()
    except Exception:
        pass

    return render(request, 'admin_panel/system_health.html', {
        'metrics': metrics, 'snapshots': snapshots,
        'recent_errors': recent_errors, 'active_alerts': active_alerts, 'stats': stats,
    })


@_admin_required
def system_health_api(request):
    checker = SystemHealthChecker()
    return JsonResponse(checker.get_metrics())


@_admin_required
def audit_logs(request):
    qs = AuditLog.objects.select_related('user').order_by('-timestamp')
    # Filters
    action = request.GET.get('action', '')
    user_q = request.GET.get('user', '')
    date   = request.GET.get('date', '')
    if action:
        qs = qs.filter(action=action)
    if user_q:
        qs = qs.filter(user__username__icontains=user_q)
    if date:
        qs = qs.filter(timestamp__date=date)

    paginator = Paginator(qs, 50)
    page      = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'admin_panel/audit_logs.html', {
        'page': page, 'actions': AuditLog.ACTIONS,
        'filter_action': action, 'filter_user': user_q, 'filter_date': date,
    })


@_admin_required
def security_alerts(request):
    qs = SecurityAlert.objects.select_related('user').order_by('-created_at')
    unresolved = qs.filter(is_resolved=False)
    resolved   = qs.filter(is_resolved=True)[:20]
    return render(request, 'admin_panel/security_alerts.html', {
        'unresolved': unresolved, 'resolved': resolved,
    })


@_admin_required
@require_POST
def resolve_alert(request, pk):
    alert = get_object_or_404(SecurityAlert, pk=pk)
    alert.is_resolved = True
    alert.resolved_at = timezone.now()
    alert.resolved_by = request.user
    alert.save()
    messages.success(request, 'Alert marked as resolved.')
    return redirect('security_alerts')


@_admin_required
def error_logs(request):
    qs = ErrorLog.objects.select_related('user').order_by('-occurred_at')
    level = request.GET.get('level', '')
    if level:
        qs = qs.filter(level=level)
    paginator = Paginator(qs, 50)
    page      = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'admin_panel/error_logs.html', {
        'page': page, 'levels': ErrorLog.LEVELS, 'filter_level': level,
    })


@_admin_required
@require_POST
def take_health_snapshot(request):
    checker = SystemHealthChecker()
    metrics = checker.get_metrics()
    # Convert to snapshot
    m = metrics
    SystemMetricSnapshot.objects.create(
        db_latency_ms=m['database'].get('latency_ms', 0),
    )
    messages.success(request, 'Health snapshot captured.')
    return redirect('system_health')
