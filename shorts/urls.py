from django.urls import path
from . import views

urlpatterns = [
    path('',                  views.shorts_feed,  name='shorts_feed'),
    path('<int:pk>/view/',    views.track_view,   name='short_track_view'),
    path('<int:pk>/like/',    views.toggle_like,  name='short_toggle_like'),
    path('<int:pk>/comments/',      views.list_comments, name='short_list_comments'),
    path('<int:pk>/comments/add/',  views.add_comment,   name='short_add_comment'),
]
