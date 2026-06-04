"""
Workflow Engine — fires workflows based on trigger events.
Called via automation.engine.fire(trigger, context).
"""
import logging
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger('nexus')


class WorkflowEngine:
    @classmethod
    def fire(cls, trigger: str, context: dict):
        """Fire all active workflows matching the given trigger event."""
        try:
            from .models import WorkflowDefinition, WorkflowRun
            workflows = WorkflowDefinition.objects.filter(
                trigger_event=trigger, is_active=True
            ).prefetch_related('actions')

            for workflow in workflows:
                run = WorkflowRun.objects.create(
                    workflow=workflow, trigger_context=context, status='running'
                )
                try:
                    cls._execute_workflow(workflow, run, context)
                    run.status = 'completed'
                    workflow.run_count += 1
                    workflow.save(update_fields=['run_count'])
                except Exception as e:
                    run.status = 'failed'
                    run.error  = str(e)
                    logger.error('Workflow "%s" failed: %s', workflow.name, e)
                finally:
                    from django.utils import timezone
                    run.finished_at = timezone.now()
                    run.save()
        except Exception as e:
            logger.error('WorkflowEngine.fire error: %s', e)

    @classmethod
    def _execute_workflow(cls, workflow, run, context: dict):
        steps_log = []
        for action in workflow.actions.filter(is_active=True):
            result = cls._execute_action(action, context)
            steps_log.append({'action_type': action.action_type, 'result': result, 'order': action.order})
        run.steps_log = steps_log
        run.save(update_fields=['steps_log'])

    @classmethod
    def _execute_action(cls, action, context: dict) -> str:
        cfg = action.config

        if action.action_type == 'send_email':
            recipient_email = context.get('user_email') or context.get('email')
            subject = cfg.get('subject', 'Notification from NEXUS')
            body    = cfg.get('body', '')
            # Simple template substitution
            for key, val in context.items():
                body    = body.replace(f'{{{{{key}}}}}', str(val))
                subject = subject.replace(f'{{{{{key}}}}}', str(val))
            if recipient_email:
                try:
                    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [recipient_email],
                              fail_silently=True)
                    return 'email_sent'
                except Exception as e:
                    return f'email_failed: {e}'
            return 'no_recipient'

        elif action.action_type == 'send_notification':
            user_id = context.get('user_id')
            if user_id:
                try:
                    from core.utils import notify
                    from accounts.models import User
                    user = User.objects.get(pk=user_id)
                    notify(user, cfg.get('notif_type', 'info'),
                           cfg.get('title', 'Notification'),
                           cfg.get('message', ''))
                    return 'notification_sent'
                except Exception as e:
                    return f'notification_failed: {e}'
            return 'no_user'

        elif action.action_type == 'send_webhook':
            import urllib.request, json
            url  = cfg.get('url', '')
            if url:
                try:
                    data = json.dumps(context).encode()
                    req  = urllib.request.Request(url, data=data,
                                                  headers={'Content-Type': 'application/json'})
                    urllib.request.urlopen(req, timeout=10)
                    return 'webhook_sent'
                except Exception as e:
                    return f'webhook_failed: {e}'
            return 'no_url'

        elif action.action_type == 'wait':
            # In synchronous mode, we skip waits — Celery would handle delays
            return f'wait_{cfg.get("hours", 0)}h_skipped_sync'

        return 'unknown_action'
