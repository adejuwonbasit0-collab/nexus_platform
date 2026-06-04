from django.urls import path
from . import views

urlpatterns = [
    path('',                      views.music_home,        name='music_home'),
    path('browse/',               views.music_browse,      name='music_browse'),
    path('artist/<slug:slug>/',   views.artist_detail,     name='artist_detail'),
    path('album/<slug:slug>/',    views.album_detail,      name='album_detail'),
    path('track/<slug:slug>/',    views.track_detail,      name='track_detail'),
    path('download/<int:pk>/',    views.download_track,    name='download_track'),
    path('like/<int:pk>/',        views.toggle_like,       name='music_toggle_like'),
    path('comment/<int:pk>/',     views.add_music_comment, name='add_music_comment'),
]
