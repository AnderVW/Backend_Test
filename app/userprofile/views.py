from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from loguru import logger
from django.conf import settings
from .models import UserProfile
from _libs.lib_azure import AzureBlobClient
import mimetypes


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_profile(request):
    try:
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        return Response({
            'id':request.user.id,
            'display_name':profile.display_name,
            'email': request.user.email,
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
        azure_client = AzureBlobClient()
        # Update only provided fields
        allowed_fields = ['gender', 'profile_url', 'bio', 'country', 'accepted_tos', 'language',"display_name"]
        for field in allowed_fields:
            if field in request.data:
                if field != 'profile_url':
                    value = request.data[field]
                else:
                    profile_file = request.FILES[field]   # IMPORTANT
                
                    # Detect content type from filename
                    content_type, _ = mimetypes.guess_type(profile_file.name)
                    content_type = content_type or profile_file.content_type or "image/jpeg"

                    blob_name = f"{request.user.id}_{request.user.email}/{profile_file.name}"

                    success = azure_client.upload_blob_from_bytes(
                        blob_name,
                        profile_file.read(),   # bytes
                        content_type=content_type
                    )

                    value = blob_name if success else None
                # Basic validation
                if field == 'accepted_tos' and not isinstance(value, bool):
                    return Response(
                        {'error': f'Invalid value for {field}. Must be boolean.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                if field in ['gender', 'profile_url', 'country', 'language',"display_name"] and value is not None and not isinstance(value, str):
                    return Response(
                        {'error': f'Invalid value for {field}. Must be string.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                setattr(profile, field, value)

       
        
        profile.save()

        url = azure_client.generate_read_sas_url(
                    settings.AZURE_CONTAINER_NAME,
                    profile.profile_url
                    )
        
        return Response({
            'id':request.user.id,
            'display_name':profile.display_name,
            'email': request.user.email,
            'gender': profile.gender,
            'profile_url': url,
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
