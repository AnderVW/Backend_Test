from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from loguru import logger

from .models import UserProfile


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_profile(request):
    try:
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        return Response({
            'gender': profile.gender,
            'profile_url': profile.profile_url,
            'bio': profile.bio,
            'is_verified': profile.is_verified,
            'is_banned': profile.is_banned,
            'country': profile.country,
            'accepted_tos': profile.accepted_tos,
            'language': profile.language,
            'created_at': profile.created_at,
            'updated_at': profile.updated_at,
        })
    except Exception as e:
        logger.error(f"Error getting profile for user {request.user.id}: {e}", exc_info=True)
        return Response(
            {'error': 'Failed to retrieve profile'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    try:
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        
        # Update only provided fields
        allowed_fields = ['gender', 'profile_url', 'bio', 'country', 'accepted_tos', 'language']
        for field in allowed_fields:
            if field in request.data:
                value = request.data[field]
                # Basic validation
                if field == 'accepted_tos' and not isinstance(value, bool):
                    return Response(
                        {'error': f'Invalid value for {field}. Must be boolean.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                if field in ['gender', 'profile_url', 'country', 'language'] and value is not None and not isinstance(value, str):
                    return Response(
                        {'error': f'Invalid value for {field}. Must be string.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                setattr(profile, field, value)
        
        profile.save()
        
        return Response({
            'gender': profile.gender,
            'profile_url': profile.profile_url,
            'bio': profile.bio,
            'is_verified': profile.is_verified,
            'is_banned': profile.is_banned,
            'country': profile.country,
            'accepted_tos': profile.accepted_tos,
            'language': profile.language,
            'created_at': profile.created_at,
            'updated_at': profile.updated_at,
        })
    except Exception as e:
        logger.error(f"Error updating profile for user {request.user.id}: {e}", exc_info=True)
        return Response(
            {'error': 'Failed to update profile'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
