from django.urls import path
from . import views

urlpatterns = [
    path('',                              views.music_home,           name='music_home'),
    path('browse/',                       views.music_browse,         name='music_browse'),
    path('artist/<slug:slug>/',           views.artist_detail,        name='artist_detail'),
    path('album/<slug:slug>/',            views.album_detail,         name='album_detail'),
    path('track/<slug:slug>/',            views.track_detail,         name='track_detail'),
    path('download/<int:pk>/',            views.download_track,       name='download_track'),
    path('like/<int:pk>/',                views.toggle_like,          name='music_toggle_like'),
    path('comment/<int:pk>/',             views.add_music_comment,    name='add_music_comment'),
    # Playlists
    path('playlists/',                    views.playlist_list,        name='playlist_list'),
    path('playlists/create/',             views.playlist_create,      name='playlist_create'),
    path('playlists/<int:pk>/',           views.playlist_detail,      name='playlist_detail'),
    path('playlists/<int:pk>/add/<int:track_pk>/',  views.playlist_add_track,    name='playlist_add_track'),
    path('playlists/<int:pk>/remove/<int:track_pk>/', views.playlist_remove_track, name='playlist_remove_track'),
    path('playlists/<int:pk>/delete/',    views.playlist_delete,      name='playlist_delete'),
    # Discover (Shazam-like)
    path('discover/',                     views.music_discover,       name='music_discover'),
    path('discover/identify/',            views.music_identify,       name='music_identify'),
    # Genre filter shortcut
    path('genre/<slug:slug>/',            views.genre_tracks,         name='genre_tracks'),
    # Lyrics
    path('lyrics/<int:pk>/',              views.track_lyrics,         name='track_lyrics'),
    # Queue API (returns JSON list of tracks for a context)
    path('queue/<str:context>/<int:pk>/', views.get_queue,            name='music_queue'),
]
