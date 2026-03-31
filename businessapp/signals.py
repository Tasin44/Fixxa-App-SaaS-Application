from django.db.models.signals import post_save
from django.dispatch import receiver
from authapp.models import User
from .models import BusinessProfile

@receiver(post_save, sender=User)
def create_business_profile(sender, instance, created, **kwargs):
    if created and not hasattr(instance, 'business_profile'):
        BusinessProfile.objects.create(
            user=instance,
            business_name=f"{instance.username}'s Business",
            whatsapp_number="",
        )