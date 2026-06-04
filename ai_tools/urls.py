from django.urls import path
from . import views

urlpatterns = [
    path('studio/', views.ai_studio, name='ai_studio'),
    path('generate/', views.generate_image, name='generate_image'),
    path('chat/', views.ai_assistant, name='ai_assistant'),
    path('moderate/<int:pk>/', views.moderate_content, name='moderate_content'),
]
