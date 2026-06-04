from django.urls import path
from . import views
urlpatterns = [
    path('',                          views.movie_home,        name='movie_home'),
    path('browse/',                   views.movie_browse,      name='movie_browse'),
    path('film/<slug:slug>/',         views.movie_detail,      name='movie_detail'),
    path('series/<slug:slug>/',       views.series_detail,     name='series_detail'),
    path('episode/<int:pk>/',         views.episode_watch,     name='episode_watch'),
    path('stream/<str:model>/<int:pk>/', views.stream_video,   name='stream_video'),
    path('download/<int:pk>/',        views.download_movie,    name='download_movie'),
    path('progress/<int:pk>/',        views.save_progress,     name='save_progress'),
    path('comment/<int:pk>/',         views.add_movie_comment, name='add_movie_comment'),
]
