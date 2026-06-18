from django.urls import path
from core import views

urlpatterns = [
    path('',                          views.creator_dashboard,      name='creator_dashboard'),
    path('upload/',                   views.creator_upload,         name='creator_upload'),
    path('write-blog/',               views.creator_write_blog,     name='creator_write_blog'),
    path('withdraw/',                 views.creator_withdraw,       name='creator_withdraw'),
    path('delete/<int:pk>/',          views.creator_delete_content, name='creator_delete'),
    path('edit/<int:pk>/',            views.creator_edit_content,   name='creator_edit'),

    # Series & Episodes
    path('series/',                          views.creator_series_list,      name='creator_series_list'),
    path('series/new/',                      views.creator_create_series,    name='creator_create_series'),
    path('series/<int:series_pk>/episodes/', views.creator_series_episodes,  name='creator_series_episodes'),

    # Albums & Tracks
    path('albums/',                       views.creator_albums_list,    name='creator_albums_list'),
    path('albums/new/',                   views.creator_create_album,   name='creator_create_album'),
    path('albums/<int:album_pk>/tracks/', views.creator_album_tracks,   name='creator_album_tracks'),
]
