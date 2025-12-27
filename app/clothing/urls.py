"""
URL configuration for clothing app
"""
from django.urls import path
from . import views


urlpatterns = [
    path('', views.list_clothing, name='list_clothing'),

    path('favorites/add/', views.add_favorite, name='add_favorite'),
    path('favorites/remove/<int:clothing_id>/', views.remove_favorite, name='remove_favorite'),
    path('favorites/', views.list_favorites, name='list_favorites'),
]

