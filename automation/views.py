"""Automation Center admin views."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.core.paginator import Paginator

from .models import ScheduledJob, WorkflowDefinition, WorkflowAction, WorkflowRun, EmailSequence


def _admin_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_admin():
            return redirect('/auth/login/')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


@_admin_required
def automation_dashboard(request):
    scheduled_jobs = ScheduledJob.objects.all()
    workflows      = WorkflowDefinition.objects.prefetch_related('actions').all()
    recent_runs    = WorkflowRun.objects.select_related('workflow').order_by('-started_at')[:20]
    stats = {
        'total_jobs':       scheduled_jobs.count(),
        'active_jobs':      scheduled_jobs.filter(status='active').count(),
        'total_workflows':  workflows.count(),
        'active_workflows': workflows.filter(is_active=True).count(),
        'runs_today':       WorkflowRun.objects.filter(
            started_at__date=__import__('django.utils.timezone', fromlist=['timezone']).timezone.now().date()
        ).count() if False else WorkflowRun.objects.count(),
        'failed_runs':      WorkflowRun.objects.filter(status='failed').count(),
    }
    return render(request, 'admin_panel/automation/dashboard.html', {
        'scheduled_jobs': scheduled_jobs, 'workflows': workflows,
        'recent_runs': recent_runs, 'stats': stats,
    })


@_admin_required
def job_create(request):
    if request.method == 'POST':
        import json
        ScheduledJob.objects.create(
            name=request.POST.get('name', ''),
            description=request.POST.get('description', ''),
            task_name=request.POST.get('task_name', ''),
            interval=request.POST.get('interval', 'daily'),
            cron_expr=request.POST.get('cron_expr', ''),
            status='active',
            created_by=request.user,
        )
        messages.success(request, 'Scheduled job created.')
        return redirect('automation_dashboard')
    return render(request, 'admin_panel/automation/job_form.html', {
        'intervals': ScheduledJob.INTERVALS, 'action': 'Create'
    })


@_admin_required
@require_POST
def job_toggle(request, pk):
    job = get_object_or_404(ScheduledJob, pk=pk)
    job.status = 'paused' if job.status == 'active' else 'active'
    job.save()
    return JsonResponse({'status': job.status})


@_admin_required
@require_POST
def job_delete(request, pk):
    get_object_or_404(ScheduledJob, pk=pk).delete()
    messages.success(request, 'Job deleted.')
    return redirect('automation_dashboard')


@_admin_required
def workflow_create(request):
    if request.method == 'POST':
        wf = WorkflowDefinition.objects.create(
            name=request.POST.get('name', ''),
            description=request.POST.get('description', ''),
            trigger_event=request.POST.get('trigger_event', ''),
            is_active=request.POST.get('is_active') == 'on',
        )
        messages.success(request, f'Workflow "{wf.name}" created.')
        return redirect('workflow_edit', pk=wf.pk)
    return render(request, 'admin_panel/automation/workflow_form.html', {
        'trigger_events': WorkflowDefinition.TRIGGER_EVENTS, 'action': 'Create'
    })


@_admin_required
def workflow_edit(request, pk):
    wf = get_object_or_404(WorkflowDefinition, pk=pk)
    actions = wf.actions.all()
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_workflow':
            wf.name          = request.POST.get('name', wf.name)
            wf.description   = request.POST.get('description', '')
            wf.trigger_event = request.POST.get('trigger_event', wf.trigger_event)
            wf.is_active     = request.POST.get('is_active') == 'on'
            wf.save()
            messages.success(request, 'Workflow updated.')
        elif action == 'add_action':
            import json
            config_raw = request.POST.get('config', '{}')
            try:
                config = json.loads(config_raw)
            except Exception:
                config = {}
            WorkflowAction.objects.create(
                workflow=wf,
                action_type=request.POST.get('action_type', 'send_email'),
                order=actions.count(),
                config=config,
            )
            messages.success(request, 'Action added.')
        elif action == 'delete_action':
            WorkflowAction.objects.filter(pk=request.POST.get('action_pk'), workflow=wf).delete()
            messages.success(request, 'Action removed.')
        elif action == 'test_fire':
            from .engine import WorkflowEngine
            WorkflowEngine.fire(wf.trigger_event, {'test': True, 'user_id': request.user.pk,
                                                    'user_email': request.user.email})
            messages.success(request, f'Test fire completed. Check workflow runs.')
        return redirect('workflow_edit', pk=pk)
    runs = wf.runs.order_by('-started_at')[:10]
    return render(request, 'admin_panel/automation/workflow_edit.html', {
        'wf': wf, 'actions': actions, 'runs': runs,
        'action_types': WorkflowAction.ACTION_TYPES,
        'trigger_events': WorkflowDefinition.TRIGGER_EVENTS,
    })


@_admin_required
@require_POST
def workflow_delete(request, pk):
    get_object_or_404(WorkflowDefinition, pk=pk).delete()
    messages.success(request, 'Workflow deleted.')
    return redirect('automation_dashboard')
