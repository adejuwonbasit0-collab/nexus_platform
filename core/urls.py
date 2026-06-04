from django.urls import path
from . import views
from . import settings_views

urlpatterns = [
    # Dashboard & analytics
    path('',                                views.admin_dashboard,        name='admin_dashboard'),
    path('analytics/',                      views.admin_analytics,        name='admin_analytics'),
    # Content - unified
    path('content/',                        views.admin_content,          name='admin_content'),
    path('upload/',                         views.admin_upload_content,   name='admin_upload'),
    path('content/<int:pk>/approve/',       views.admin_approve_content,  name='admin_approve'),
    path('content/<int:pk>/reject/',        views.admin_reject_content,   name='admin_reject'),
    path('content/<int:pk>/delete/',        views.admin_delete_content,   name='admin_delete_content'),
    # Module-specific management
    path('movies/',                         views.admin_movies,           name='admin_movies'),
    path('music/',                          views.admin_music,            name='admin_music'),
    path('blog/',                           views.admin_blog,             name='admin_blog'),
    path('images/',                         views.admin_images_mgmt,      name='admin_images'),
    # Series
    path('series/',                         views.admin_series,           name='admin_series'),
    path('series/create/',                  views.admin_create_series,    name='admin_create_series'),
    path('series/<int:series_pk>/episode/', views.admin_add_episode,      name='admin_add_episode'),
    # Categories
    path('categories/',                     views.admin_categories,       name='admin_categories'),
    # Users
    path('users/',                          views.admin_users,            name='admin_users'),
    path('users/<int:pk>/',                 views.admin_user_detail,      name='admin_user_detail'),
    # Finance
    path('monetization/',                   views.admin_monetization,     name='admin_monetization'),
    # CMS, Automation, System, Settings — unified hubs
    path('cms/',                            settings_views.cms_hub,       name='cms_hub'),
    path('automation/',                     settings_views.automation_hub, name='automation_hub'),
    path('automation/job/<int:pk>/toggle/', settings_views.job_toggle,    name='job_toggle'),
    path('automation/job/<int:pk>/delete/', settings_views.job_delete,    name='job_delete'),
    path('automation/wf/<int:pk>/toggle/',  settings_views.wf_toggle,     name='wf_toggle'),
    path('automation/wf/<int:pk>/delete/',  settings_views.wf_delete,     name='wf_delete'),
    path('automation/wf/<int:pk>/test/',    settings_views.wf_test,       name='wf_test'),
    path('system/',                         settings_views.system_hub,    name='system_hub'),
    path('system/health-api/',              settings_views.system_health_api, name='system_health_api'),
    path('system/clear-cache/',             settings_views.clear_cache,   name='clear_cache'),
    path('system/alert/<int:pk>/resolve/',  settings_views.resolve_alert, name='resolve_alert'),
    path('settings/',                       settings_views.settings_hub,  name='settings_hub'),
    path('settings/email-test/',            settings_views.email_test,    name='email_test'),
    # Notifications
    path('notifications/',                  views.notifications_list,     name='notifications_list'),
    path('notifications/count/',            views.notifications_count,    name='notifications_count'),
]
