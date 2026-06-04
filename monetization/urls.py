from django.urls import path
from . import views

urlpatterns = [
    path('initiate/<int:content_pk>/',    views.initiate_payment,      name='initiate_payment'),
    path('verify/',                        views.verify_payment,         name='verify_payment'),
    path('webhook/paystack/',              views.paystack_webhook,       name='paystack_webhook'),
    path('webhook/stripe/',                views.stripe_webhook,         name='stripe_webhook'),
    path('subscribe/<slug:plan_slug>/',    views.subscribe,              name='subscribe'),
    path('wallet/',                        views.wallet_dashboard,       name='wallet_dashboard'),
    path('coupon/validate/',               views.validate_coupon,        name='validate_coupon'),
]
