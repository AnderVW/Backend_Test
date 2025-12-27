import os
from loguru import logger
from django.core.management.base import BaseCommand
from clothing.models import Clothing
from django.conf import settings
from _libs.lib_azure import AzureBlobClient  # wherever you put your class

class Command(BaseCommand):
    help = "Upload dummy clothing images to Azure and save in DB"

    def handle(self, *args, **options):
        azure_client = AzureBlobClient()
        for cloth in Clothing.objects.all():
            url = azure_client.generate_read_sas_url(
                settings.AZURE_CONTAINER_NAME,
                cloth.azure_blob_name
            )
            logger.info(f"Successfully uploaded blob: {url}")
        # Initialize Azure client
        # azure_client = AzureBlobClient()

        # # # Folder with dummy images
        # images_folder = os.path.join(settings.BASE_DIR, "..", "assets/clothing_test")
                
        # # client = AzureBlobClient()

        # # # Delete all blobs under dummy_clothing/
        # # container_client = client.get_container_client(client.container_name)
        # # blobs = container_client.list_blobs(name_starts_with="dummy_clothing/")

        # # for blob in blobs:
        # #     client.delete_blob(blob.name)
        # #     print(f"Deleted blob: {blob.name}")

        # # Dummy clothing data
        # dummy_clothes = [
        #     {"file": "Dummy1.png", "brand_name": "Mango","main_category": "Tops", "sub_category": "Shirts", "price": 99},
        #     {"file": "Dummy2.png", "brand_name": "Zera","main_category": "Tops", "sub_category": "TShirts", "price": 29},
        #     {"file": "Dummy3.png", "brand_name": "H&M", "main_category": "Tops","sub_category": "Shirts", "price": 89},
        #     {"file": "Dummy4.png", "brand_name": "AIIZ","main_category": "Bottom", "sub_category": "Trousers", "price": 49},
        #     {"file": "Dummy5.png", "brand_name": "Zera","main_category": "LongJacket", "sub_category": "Coat", "price": 59},
        #     {"file": "Dummy6.png", "brand_name": "Zara","main_category": "Dress", "sub_category": "Dresses", "price": 69},
        # ]

        # # Upload images and save to DB
        # for item in dummy_clothes:
        #     file_path = os.path.join(images_folder, item["file"])
        #     if not os.path.exists(file_path):
        #         self.stdout.write(self.style.ERROR(f"File not found: {file_path}"))
        #         continue

        #     # Upload to Azure
        #     blob_name = f"dummy_clothing/{item['file']}"
        #     with open(file_path, "rb") as f:
        #         success = azure_client.upload_blob_from_bytes(blob_name, f.read(), content_type="image/png")

        #     if success:
                
        #         Clothing.objects.create(
        #             brand_name=item["brand_name"],
        #             price=item["price"],
        #             main_category = item["main_category"],
                    
        #             sub_category=item["sub_category"],
        #             azure_blob_name=blob_name
        #         )
        #         self.stdout.write(self.style.SUCCESS(f"Uploaded and saved {item['file']}"))
        #     else:
        #         self.stdout.write(self.style.ERROR(f"Failed to upload {item['file']}"))
