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
    
    #external clothing endpoint
    path('clothing/',include('clothing.urls')),

   #Clothing items endpoints
    path('clothing-items/init/', views.init_clothing_upload, name='api_init_clothing_upload'),
    path('clothing-items/status/<uuid:asset_id>/', views.check_clothing_status, name='api_check_clothing_status'),
    path('clothing-items/', views.list_clothing, name='api_list_clothing'),
    path('clothing-items/update-type/<uuid:asset_id>/', views.update_clothing_type, name='api_update_clothing_type'),
    path('clothing-items/update-category/<uuid:asset_id>/', views.update_clothing_category, name='api_update_clothing_category'),
    path('clothing-items/update-subcategory/<uuid:asset_id>/', views.update_clothing_subcategory, name='api_update_clothing_subcategory'),
    path('clothing-items/update-color/<uuid:asset_id>/', views.update_clothing_color, name='api_update_clothing_color'),
    path('clothing-items/update-comments/<uuid:asset_id>/', views.update_clothing_comments, name='api_update_clothing_comments'),
    path('clothing-items/delete/<uuid:asset_id>/', views.delete_clothing, name='api_delete_clothing'),
    
    # Base images endpoints
    path('base-images/init/', views.init_base_upload, name='api_init_base_upload'),
    path('base-images/status/<uuid:asset_id>/', views.check_base_status, name='api_check_base_status'),
    path('base-images/', views.list_base, name='api_list_base'),
    path('base-images/delete/<uuid:asset_id>/', views.delete_base, name='api_delete_base'),
    
    # Generated images endpoints
    path('generated-images/', views.list_generated, name='api_list_generated'),
    path('generated-images/delete/<uuid:asset_id>/', views.delete_generated, name='api_delete_generated'),
    
    # Virtual fit endpoints
    path('virtual-fit/generate/', views.generate_virtual_fit, name='api_generate_virtual_fit'),
    path('virtual-fit/tasks/<uuid:task_id>/', views.generation_task_status, name='api_generation_status'),
]

