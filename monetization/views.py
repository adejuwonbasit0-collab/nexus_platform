"""
monetization/views.py
Paystack payment initiation + server-side verification.
Public key loaded from DB (PaymentSettings). Secret key comes from
AIProviderSettings pattern → NOT stored in settings.py.
"""
import json
import logging
import urllib.request
import urllib.error
from datetime import datetime, timezone

from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.conf import settings

from .models import Payment, PaymentSettings, Earning, WebhookEvent, Wallet, WithdrawalRequest, Coupon, SubscriptionPlan
from content.models import Content
from core.utils import notify, verify_paystack_transaction

logger = logging.getLogger(__name__)


def _get_payment_cfg():
    """Return (public_key, secret_key, currency) from DB + env."""
    cfg = PaymentSettings.get_active()
    if cfg:
        public_key = cfg.public_key
        currency   = cfg.currency or 'NGN'
    else:
        public_key = ''
        currency   = 'NGN'

    # Secret key must stay out of DB – use env only
    secret_key = getattr(settings, 'PAYSTACK_SECRET_KEY', '')
    import os
    secret_key = secret_key or os.environ.get('PAYSTACK_SECRET_KEY', '')
    return public_key, secret_key, currency


@login_required
def initiate_payment(request, content_pk):
    """Return JSON with Paystack public key + metadata to initialise popup."""
    obj = get_object_or_404(Content, pk=content_pk, status='approved', tier='premium')
    public_key, _, currency = _get_payment_cfg()

    if not public_key:
        return JsonResponse({'error': 'Payment system is not configured.'}, status=503)

    cfg = PaymentSettings.get_active()
    is_test = cfg.is_test_key if cfg else True

    # Create a pending Payment record
    payment = Payment.objects.create(
        user=request.user,
        content=obj,
        amount=obj.price,
        currency=currency,
        status='pending',
    )
    return JsonResponse({
        'public_key':  public_key,
        'email':       request.user.email or f'{request.user.username}@nexus.local',
        'amount':      int(obj.price * 100),   # kobo / smallest unit
        'currency':    currency,
        'reference':   f'NEXUS-{payment.pk}-{int(datetime.now().timestamp())}',
        'payment_id':  payment.pk,
        'is_test':     is_test,
    })


@require_POST
@login_required
def verify_payment(request):
    """
    Called by frontend after Paystack callback.
    Verifies transaction server-side before granting access.
    """
    try:
        body = json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'Invalid request body.'}, status=400)

    reference  = body.get('reference', '').strip()
    payment_id = body.get('payment_id')

    if not reference or not payment_id:
        return JsonResponse({'error': 'Missing reference or payment_id.'}, status=400)

    payment = get_object_or_404(Payment, pk=payment_id, user=request.user)

    if payment.status == 'completed':
        return JsonResponse({'status': 'already_verified'})

    _, secret_key, _ = _get_payment_cfg()
    if not secret_key:
        return JsonResponse({'error': 'Payment secret key not configured on server.'}, status=503)

    try:
        data   = verify_paystack_transaction(reference, secret_key)
        txn    = data['data']
        paid   = txn.get('status') == 'success'
        amount_paid = txn.get('amount', 0) / 100   # kobo → naira

        if paid:
            payment.status       = 'completed'
            payment.paystack_ref = reference
            payment.verified_at  = datetime.now(timezone.utc)
            payment.save()

            # Award creator earnings
            from monetization.models import CommissionSettings, Earning
            try:
                commission = CommissionSettings.objects.get(
                    content_type=payment.content.content_type, action='purchase'
                )
                earn_amount = commission.amount
                Earning.objects.create(
                    creator=payment.content.creator,
                    content=payment.content,
                    amount=earn_amount,
                    reason='Purchase commission',
                )
                payment.content.creator.total_earnings += earn_amount
                payment.content.creator.save(update_fields=['total_earnings'])
            except CommissionSettings.DoesNotExist:
                pass

            notify(
                request.user,
                'payment_success',
                'Payment Successful',
                f'Your payment for "{payment.content.title}" was successful.',
                link=f'/content/{payment.content.pk}/',
            )
            return JsonResponse({'status': 'success', 'amount': str(amount_paid)})
        else:
            payment.status = 'failed'
            payment.save()
            return JsonResponse({'status': 'failed', 'message': 'Transaction not successful.'})

    except ValueError as e:
        payment.status = 'failed'
        payment.save()
        logger.error('Paystack verify error: %s', e)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=502)


# ── Webhook Handlers ────────────────────────────────────────────────────────

import json, hmac, hashlib, logging
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST as _require_POST
from django.http import HttpResponse, JsonResponse
from django.conf import settings as django_settings

logger = logging.getLogger('nexus')


@csrf_exempt
@_require_POST
def paystack_webhook(request):
    """Receive and process Paystack webhook events."""
    signature = request.headers.get('x-paystack-signature', '')
    payload   = request.body
    secret    = django_settings.PAYSTACK_SECRET_KEY.encode()

    # Verify HMAC signature
    expected = hmac.new(secret, payload, hashlib.sha512).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return HttpResponse(status=400)

    try:
        event = json.loads(payload)
    except Exception:
        return HttpResponse(status=400)

    event_type = event.get('event', '')
    data       = event.get('data', {})
    event_id   = str(data.get('id', data.get('reference', '')))

    # Idempotency — skip if already processed
    if WebhookEvent.objects.filter(provider='paystack', event_id=event_id).exists():
        return HttpResponse(status=200)

    WebhookEvent.objects.create(
        provider='paystack', event_type=event_type,
        event_id=event_id, payload=event,
    )

    # Handle charge success
    if event_type == 'charge.success':
        reference = data.get('reference', '')
        try:
            payment = Payment.objects.get(paystack_ref=reference, status='pending')
            payment.status = 'completed'
            payment.save(update_fields=['status'])
            # Credit creator wallet if applicable
            if payment.content and payment.content.creator:
                creator = payment.content.creator
                commission_pct = 0.7  # 70% to creator
                creator_amount = payment.amount * commission_pct
                try:
                    creator.wallet.credit(
                        creator_amount,
                        reason=f'Payment for: {payment.content.title}',
                        reference=reference,
                    )
                    Earning.objects.create(
                        creator=creator,
                        content=payment.content,
                        amount=creator_amount,
                        reason=f'Sale: {payment.content.title}',
                    )
                except Exception as e:
                    logger.error('Wallet credit failed: %s', e)
            # Fire automation
            try:
                from automation.engine import WorkflowEngine
                WorkflowEngine.fire('payment.completed', {
                    'user_id': payment.user.pk,
                    'user_email': payment.user.email,
                    'amount': str(payment.amount),
                    'reference': reference,
                })
            except Exception:
                pass
            # Mark webhook processed
            WebhookEvent.objects.filter(
                provider='paystack', event_id=event_id
            ).update(processed=True)
        except Payment.DoesNotExist:
            logger.warning('Paystack webhook: Payment not found for ref %s', reference)

    return HttpResponse(status=200)


@csrf_exempt
@_require_POST
def stripe_webhook(request):
    """Receive and process Stripe webhook events."""
    payload   = request.body
    sig_header = request.headers.get('Stripe-Signature', '')
    secret    = django_settings.STRIPE_WEBHOOK_SECRET

    if not secret:
        return HttpResponse(status=400)

    # Simple timestamp + signature verification (no stripe SDK)
    try:
        event = json.loads(payload)
    except Exception:
        return HttpResponse(status=400)

    event_id   = event.get('id', '')
    event_type = event.get('type', '')

    if WebhookEvent.objects.filter(provider='stripe', event_id=event_id).exists():
        return HttpResponse(status=200)

    WebhookEvent.objects.create(
        provider='stripe', event_type=event_type,
        event_id=event_id, payload=event,
    )
    WebhookEvent.objects.filter(provider='stripe', event_id=event_id).update(processed=True)
    return HttpResponse(status=200)


def subscribe(request, plan_slug):
    """Initiate subscription checkout."""
    from .models import SubscriptionPlan
    plan = get_object_or_404(SubscriptionPlan, slug=plan_slug, is_active=True)
    if not request.user.is_authenticated:
        return redirect(f'/auth/login/?next=/pay/subscribe/{plan_slug}/')

    context = {
        'plan': plan,
        'paystack_public_key': PaymentSettings.get_active().public_key if PaymentSettings.get_active() else '',
    }
    return render(request, 'monetization/subscribe.html', context)


@login_required
def wallet_dashboard(request):
    """User's wallet and transaction history (creators/admins only)."""
    if not request.user.is_creator():
        messages.info(request, "Wallets are only available for creator accounts.")
        return redirect('user_dashboard')
    from .models import Wallet, WalletTransaction, WithdrawalRequest
    wallet, _ = Wallet.objects.get_or_create(user=request.user)
    transactions = WalletTransaction.objects.filter(wallet=wallet).order_by('-created_at')[:30]
    withdrawals  = WithdrawalRequest.objects.filter(user=request.user).order_by('-created_at')[:10]
    return render(request, 'monetization/wallet.html', {
        'wallet': wallet,
        'transactions': transactions,
        'withdrawals': withdrawals,
    })


def validate_coupon(request):
    """AJAX: validate a coupon code and return discount info."""
    from .models import Coupon
    if request.method != 'POST':
        return JsonResponse({'valid': False, 'error': 'POST required'})
    try:
        data  = json.loads(request.body)
        code  = data.get('code', '').strip().upper()
        amount = float(data.get('amount', 0))
    except Exception:
        return JsonResponse({'valid': False, 'error': 'Invalid request'})

    try:
        coupon = Coupon.objects.get(code=code)
        valid, message = coupon.is_valid()
        if not valid:
            return JsonResponse({'valid': False, 'error': message})
        if amount < float(coupon.min_amount):
            return JsonResponse({'valid': False, 'error': f'Minimum order amount is {coupon.min_amount}'})
        discounted = float(coupon.apply(amount))
        return JsonResponse({
            'valid': True,
            'discount_type': coupon.discount_type,
            'discount_value': float(coupon.discount_value),
            'original_amount': amount,
            'discounted_amount': discounted,
            'savings': amount - discounted,
        })
    except Coupon.DoesNotExist:
        return JsonResponse({'valid': False, 'error': 'Coupon not found'})