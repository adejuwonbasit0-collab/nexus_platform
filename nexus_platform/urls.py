"""Nexus Platform — Master URL Configuration"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from cms.views import static_page_view, cms_robots_txt, cms_theme_css

urlpatterns = [
    path('django-admin/', admin.site.urls),
    # Public platform
    path('', include('core.global_urls')),
    # Auth
    path('auth/', include('accounts.urls')),
    # Content modules
    path('movies/',  include('movies.urls')),
    path('music/',   include('music.urls')),
    path('images/',  include('images.urls')),
    path('blog/',    include('blog.urls')),
    path('content/', include('content.urls')),
    # AI tools
    path('ai/',      include('ai_tools.urls')),
    # Payments
    path('pay/',     include('monetization.urls')),
    # Admin panel (all admin including cms/system/settings via hub)
    path('admin-panel/', include('core.urls')),
    # Creator area
    path('creator/', include('core.creator_urls')),
    # SEO endpoints
    path('robots.txt',    cms_robots_txt,  name='robots_txt'),
    path('cms/dynamic.css', cms_theme_css, name='dynamic_css'),
    # Public static pages
    path('page/<slug:slug>/', static_page_view, name='static_page'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,  document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
