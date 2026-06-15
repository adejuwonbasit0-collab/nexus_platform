from django.urls import path
from . import global_views

urlpatterns = [
    path('',                   global_views.platform_home,     name='home'),
    path('search/',            global_views.global_search,     name='search'),
    path('trending/',          global_views.trending_view,     name='trending'),
    path('dashboard/',         global_views.user_dashboard,    name='user_dashboard'),
    path('subscriptions/',     global_views.subscriptions_view, name='subscriptions'),
]