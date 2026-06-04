from django.urls import path
from . import views

urlpatterns = [
    path('browse/',                        views.browse,          name='browse'),
    path('<int:pk>/',                      views.content_detail,  name='content_detail'),
    path('series/<int:pk>/',              views.series_detail,   name='series_detail'),
    path('watch/<int:pk>/',               views.episode_watch,   name='episode_watch'),
    path('stream/video/<int:pk>/',        views.stream_video,    name='stream_video'),
    path('<int:pk>/download/',            views.download_content, name='download_content'),
    path('<int:pk>/like/',                views.toggle_like,     name='toggle_like'),
    path('<int:pk>/comment/',             views.add_comment,     name='add_comment'),
]
