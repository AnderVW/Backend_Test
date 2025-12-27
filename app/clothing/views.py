from django.shortcuts import render

# Create your views here.
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from _libs.lib_azure import AzureBlobClient
from .models import Clothing, FavoriteClothing
from django.conf import settings


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_clothing(request):
    try:
        clothes = Clothing.objects.all().order_by('-created_at')
        azure_client = AzureBlobClient()

        response = []
        for c in clothes:
            is_favorited = FavoriteClothing.objects.filter(
                user=request.user,
                clothing=c
            ).exists()

            sas_url = azure_client.generate_read_sas_url(
                settings.AZURE_CONTAINER_NAME,
                c.azure_blob_name
            )

            response.append({
                "id": c.id,
                "brand_name": c.brand_name,
                "price": float(c.price),
                "image_url": sas_url,
                "description": c.description,
                "main_category": c.main_category,
                "sub_category": c.sub_category,
                "color":c.colors,
                "currency": c.currency,
                "link": c.link,
                "is_favorited": is_favorited,
                "created_at": c.created_at,
            })

        return Response({"clothing" :response}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"error": "Failed to retrieve clothing"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
@permission_classes([IsAuthenticated])
@api_view(['GET'])
def list_favorites(request):
    """
    List all clothing items favorited by the authenticated user.
    """
    try:
        favorites = FavoriteClothing.objects.filter(user=request.user).select_related("clothing").order_by('created_at')
        azure_client = AzureBlobClient()

        response = []
        for fav in favorites:
            clothing = fav.clothing  # access the related Clothing object

            sas_url = azure_client.generate_read_sas_url(
                settings.AZURE_CONTAINER_NAME,
                clothing.azure_blob_name  # this should be on Clothing, not FavoriteClothing
            )

            response.append({
                "id": clothing.id,
                "brand_name": clothing.brand_name,
                "price": float(clothing.price),
                "image_url": sas_url,
                "description": clothing.description,
                "main_category": clothing.main_category,
                "sub_category": clothing.sub_category,
                                "color":clothing.colors,

                "currency": clothing.currency,
                "link": clothing.link,
                "is_favorited": True,
                "created_at": fav.created_at,  # when the favorite was created
            })

        return Response({"favourite_clothing": response}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"error": f"Failed to retrieve favorites: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@permission_classes([IsAuthenticated])
@api_view(['POST'])
def add_favorite(request):
    """
    Add a clothing item to favorites.
    Request body: { "clothing_id": <id> }
    """
    clothing_id = request.data.get('clothing_id')
    if not clothing_id:
        return Response({"error": "clothing_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        clothing = Clothing.objects.get(id=clothing_id)
    except Clothing.DoesNotExist:
        return Response({"error": "Clothing not found"}, status=status.HTTP_404_NOT_FOUND)

    favorite, created = FavoriteClothing.objects.get_or_create(user=request.user, clothing=clothing)
    if not created:
        return Response({"message": "Already in favorites", "is_favorite": True}, status=status.HTTP_200_OK)

    return Response({"message": "Added to favorites", "is_favorite": True}, status=status.HTTP_201_CREATED)


@permission_classes([IsAuthenticated])
@api_view(['DELETE'])
def remove_favorite(request, clothing_id):
    """
    Remove a clothing item from favorites.
    URL param: /favorites/remove/<clothing_id>/
    """
    try:
        clothing = Clothing.objects.get(id=clothing_id)
    except Clothing.DoesNotExist:
        return Response({"error": "Clothing not found"}, status=status.HTTP_404_NOT_FOUND)

    deleted, _ = FavoriteClothing.objects.filter(user=request.user, clothing=clothing).delete()
    if deleted == 0:
        return Response({"message": "Not in favorites", "is_favorite": False}, status=status.HTTP_200_OK)

    return Response({"message": "Removed from favorites", "is_favorite": False}, status=status.HTTP_200_OK)
