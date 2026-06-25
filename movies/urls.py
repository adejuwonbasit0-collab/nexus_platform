from django.urls import path
from . import views

urlpatterns = [
    path('',                               views.movie_home,          name='movie_home'),
    path('browse/',                        views.movie_browse,        name='movie_browse'),
    path('film/<slug:slug>/',              views.movie_detail,        name='movie_detail'),
    path('series/<slug:slug>/',            views.series_detail,       name='series_detail'),
    path('episode/<int:pk>/',             views.episode_watch,        name='episode_watch'),
    path('episode/download/<int:pk>/',    views.download_episode,     name='download_episode'),
    path('stream/movie/<int:pk>/',        views.stream_movie,         name='stream_movie'),
    path('stream/<str:model>/<int:pk>/',  views.stream_video,         name='stream_video'),
    path('download/<int:pk>/',            views.download_movie,       name='download_movie'),
    path('progress/<int:pk>/',            views.save_progress,        name='save_progress'),
    path('episode-comment/<int:pk>/',     views.add_episode_comment,  name='add_episode_comment'),
    path('comment/<int:pk>/',             views.add_movie_comment,    name='add_movie_comment'),
    path('like/<int:pk>/',                views.toggle_movie_like,    name='movie_toggle_like'),
    # Subtitles / AI scene summary
    path('subtitles/<int:pk>/',           views.movie_subtitles,      name='movie_subtitles'),
    path('episode/subtitles/<int:pk>/',   views.episode_subtitles,    name='episode_subtitles'),
]
