from django.urls import path
from . import views
urlpatterns = [
    path('',                    views.image_home,       name='image_home'),
    path('browse/',             views.image_browse,     name='image_browse'),
    path('view/<slug:slug>/',   views.image_detail,     name='image_detail'),
    path('download/<int:pk>/',  views.download_image,   name='download_image'),
    path('comment/<int:pk>/',   views.add_image_comment,name='add_image_comment'),
]
