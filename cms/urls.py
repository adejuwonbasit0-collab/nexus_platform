from django.urls import path
from . import views

urlpatterns = [
    # Branding & Theme
    path('branding/',                                   views.cms_branding,                   name='cms_branding'),
    path('theme/',                                      views.cms_theme,                       name='cms_theme'),
    path('theme/dynamic.css',                           views.cms_theme_css,                   name='cms_theme_css'),
    # Homepage
    path('homepage/',                                   views.cms_homepage,                    name='cms_homepage'),
    path('homepage/section/create/',                    views.cms_homepage_section_create,     name='cms_homepage_section_create'),
    path('homepage/section/<int:pk>/edit/',             views.cms_homepage_section_edit,       name='cms_homepage_section_edit'),
    path('homepage/section/<int:pk>/delete/',           views.cms_homepage_section_delete,     name='cms_homepage_section_delete'),
    path('homepage/reorder/',                           views.cms_homepage_reorder,            name='cms_homepage_reorder'),
    # Menus
    path('menus/',                                      views.cms_menus,                       name='cms_menus'),
    path('menus/<str:location>/',                       views.cms_menu_edit,                   name='cms_menu_edit'),
    # Static Pages
    path('pages/',                                      views.cms_pages,                       name='cms_pages'),
    path('pages/create/',                               views.cms_page_create,                 name='cms_page_create'),
    path('pages/<int:pk>/edit/',                        views.cms_page_edit,                   name='cms_page_edit'),
    path('pages/<int:pk>/delete/',                      views.cms_page_delete,                 name='cms_page_delete'),
    # SEO
    path('seo/',                                        views.cms_seo,                         name='cms_seo'),
    # Announcements
    path('announcements/',                              views.cms_announcements,               name='cms_announcements'),
    path('announcements/create/',                       views.cms_announcement_create,         name='cms_announcement_create'),
    path('announcements/<int:pk>/toggle/',              views.cms_announcement_toggle,         name='cms_announcement_toggle'),
    path('announcements/<int:pk>/delete/',              views.cms_announcement_delete,         name='cms_announcement_delete'),
    # Email Templates
    path('email-templates/',                            views.cms_email_templates,             name='cms_email_templates'),
    path('email-templates/<str:template_type>/',        views.cms_email_template_edit,         name='cms_email_template_edit'),
    # Scripts
    path('scripts/',                                    views.cms_scripts,                     name='cms_scripts'),
    path('scripts/create/',                             views.cms_script_create,               name='cms_script_create'),
    path('scripts/<int:pk>/edit/',                      views.cms_script_edit,                 name='cms_script_edit'),
    path('scripts/<int:pk>/toggle/',                    views.cms_script_toggle,               name='cms_script_toggle'),
    path('scripts/<int:pk>/delete/',                    views.cms_script_delete,               name='cms_script_delete'),
    # Maintenance
    path('maintenance/',                                views.cms_maintenance,                 name='cms_maintenance'),
    # Feature Flags
    path('feature-flags/',                              views.cms_feature_flags,               name='cms_feature_flags'),
    path('feature-flags/<int:pk>/toggle/',              views.cms_feature_flag_toggle,         name='cms_feature_flag_toggle'),
    path('feature-flags/<int:pk>/save/',                views.cms_feature_flag_save,           name='cms_feature_flag_save'),
]
