"""
API URL configuration
"""
from django.urls import path, include
from . import views

urlpatterns = [
    # Auth endpoints
    path('auth/login/', views.login, name='api_login'),
    path('auth/signup/', views.signup, name='api_signup'),
    path('auth/google/', views.google_auth, name='api_google_auth'),
    path('auth/user/', views.user_info, name='api_user_info'),
    path('auth/logout/', views.logout, name='api_logout'),
    
    # Profile endpoints
    path('profile/', include('userprofile.urls')),
    
    # Asset upload endpoints
    path('assets/init/', views.init_upload, name='api_init_upload'),
    path('assets/status/<uuid:asset_id>/', views.check_upload_status, name='api_check_upload_status'),
    path('assets/', views.list_assets, name='api_list_assets'),
    path('assets/delete/<uuid:asset_id>/', views.delete_asset, name='api_delete_asset'),
    
    # Virtual fit endpoints
    path('virtual-fit/generate/', views.generate_virtual_fit, name='api_generate_virtual_fit'),
    path('virtual-fit/tasks/<uuid:task_id>/', views.generation_task_status, name='api_generation_status'),
]

