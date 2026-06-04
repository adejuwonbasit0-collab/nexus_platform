from django.urls import path
from . import views
urlpatterns = [
    path('',                   views.blog_home,        name='blog_home'),
    path('browse/',            views.blog_browse,      name='blog_browse'),
    path('post/<slug:slug>/',  views.post_detail,      name='post_detail'),
    path('like/<int:pk>/',     views.toggle_like,      name='blog_toggle_like'),
    path('comment/<int:pk>/',  views.add_comment,      name='blog_add_comment'),
    path('ai/',                views.ai_blog_generator,name='ai_blog_generator'),
    path('edit/<int:pk>/',     views.blog_edit,        name='blog_edit'),
    path('my-posts/',          views.my_posts,         name='my_posts'),
]
