"""
URL configuration for userprofile app
"""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.get_profile, name='profile_get'),
    path('update/', views.update_profile, name='profile_update'),
]

