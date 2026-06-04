from django.urls import path
from . import views

urlpatterns = [
    path('',                            views.automation_dashboard, name='automation_dashboard'),
    path('jobs/create/',                views.job_create,           name='job_create'),
    path('jobs/<int:pk>/toggle/',       views.job_toggle,           name='job_toggle'),
    path('jobs/<int:pk>/delete/',       views.job_delete,           name='job_delete'),
    path('workflows/create/',           views.workflow_create,      name='workflow_create'),
    path('workflows/<int:pk>/edit/',    views.workflow_edit,        name='workflow_edit'),
    path('workflows/<int:pk>/delete/',  views.workflow_delete,      name='workflow_delete'),
]
