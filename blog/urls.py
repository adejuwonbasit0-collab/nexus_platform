from django.urls import path
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from . import views

def creator_write_redirect(request):
    """Redirect /blog/write/ to creator studio blog tab.
    Users cannot write posts — only creators and admins can."""
    if not request.user.is_authenticated:
        return redirect(f'/auth/login/?next=/creator/')
    role = getattr(request.user, 'role', '')
    if role in ('creator', 'admin', 'staff') or request.user.is_staff or request.user.is_superuser:
        return redirect('/creator/#blog')
    # Regular users cannot write — redirect to blog home
    return redirect('/blog/')

urlpatterns = [
    path('',                   views.blog_home,        name='blog_home'),
    path('browse/',            views.blog_browse,      name='blog_browse'),
    path('post/<slug:slug>/',  views.post_detail,      name='post_detail'),
    path('like/<int:pk>/',     views.toggle_like,      name='blog_toggle_like'),
    path('comment/<int:pk>/',  views.add_comment,      name='blog_add_comment'),
    path('ai/',                views.ai_blog_generator,name='ai_blog_generator'),
    path('edit/<int:pk>/',     views.blog_edit,        name='blog_edit'),
    path('my-posts/',          views.my_posts,         name='my_posts'),
    # /blog/write/ → redirect to creator studio (not a public write page)
    path('write/',             creator_write_redirect, name='blog_write'),
]
