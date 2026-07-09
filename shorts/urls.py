from django.urls import path
from . import views

urlpatterns = [
    path('',                  views.shorts_feed,  name='shorts_feed'),
    path('<int:pk>/view/',    views.track_view,   name='short_track_view'),
    path('<int:pk>/like/',    views.toggle_like,  name='short_toggle_like'),
]
