from django.db import models

# Create your models here.
from django.conf import settings


class Clothing(models.Model):
    brand_name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="EUR")

    azure_blob_name = models.URLField(max_length=1000)
    description  = models.TextField(blank=True, default="")


    main_category = models.CharField(max_length=100)
    sub_category = models.CharField(max_length=100)
    

    colors = models.JSONField(default=list, blank=True)

    link = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.brand_name} - {self.sub_category}"


class FavoriteClothing(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    clothing = models.ForeignKey(
        Clothing,
        on_delete=models.CASCADE,
        related_name="favorites"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "clothing")

    def __str__(self):
        return f"{self.user} ♥ {self.clothing}"
