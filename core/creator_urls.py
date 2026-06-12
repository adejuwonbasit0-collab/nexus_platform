from django.urls import path
from core import views

urlpatterns = [
    path('',                          views.creator_dashboard,      name='creator_dashboard'),
    path('upload/',                   views.creator_upload,         name='creator_upload'),
    path('write-blog/',               views.creator_write_blog,     name='creator_write_blog'),
    path('withdraw/',                 views.creator_withdraw,       name='creator_withdraw'),
    path('delete/<int:pk>/',          views.creator_delete_content, name='creator_delete'),
    path('edit/<int:pk>/',            views.creator_edit_content,   name='creator_edit'),
]
