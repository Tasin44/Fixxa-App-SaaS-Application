# from django.db.models.signals import post_save
# from django.dispatch import receiver
# from .models import Client
# import requests
# from django.conf import settings

# @receiver(post_save, sender=Client)
# def sync_client_to_n8n(sender, instance, created, **kwargs):
#     # Comment: This signal triggers after saving a Client. If created or updated, send data to n8n webhook for HubSpot sync.
#     if created or instance._state.adding is False:  # On create or update
#         data = {
#             'client_id': instance.id,
#             'name': instance.name,
#             'email': instance.email,
#             'phone': instance.phone_number,
#             'address': instance.address,
#             'user_id': instance.user_id,
#             'created_at': instance.created_at.isoformat(),
#             'updated_at': instance.updated_at.isoformat(),
#             # Add more fields as needed
#         }
#         n8n_webhook_url = settings.N8N_WEBHOOK_URL  # Import from settings
#         try:
#             requests.post(n8n_webhook_url, json=data)
#         except Exception as e:
#             print(f"Error syncing client to n8n: {e}")  # Log error; in production, use logging


# 3. Create signals to automatically trigger n8n workflows
# Create new file: clientapp/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Client
from utils.n8n_webhooks import n8n_client
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Client)
def client_created_or_updated(sender, instance, created, **kwargs):
    """
    Trigger n8n workflow when client is created or updated
    This will sync client data to HubSpot via n8n
    """
    try:
        # Prepare client data for n8n
        client_data = {
            'action': 'created' if created else 'updated',
            'timestamp': timezone.now().isoformat(),
            'client': {
                'id': instance.id,
                'name': instance.name,
                'email': instance.email,
                'phone_number': instance.phone_number,
                'address': instance.address,
                'user_id': instance.user_id,
                'created_at': instance.created_at.isoformat(),
                'updated_at': instance.updated_at.isoformat(),
            }
        }
        
        # Send to n8n webhook (which will sync to HubSpot)
        webhook_name = 'client-created' if created else 'client-updated'
        n8n_client.send_webhook(webhook_name, client_data)
        
        logger.info(f"Client {instance.name} {webhook_name.replace('-', ' ')} webhook sent to n8n")
        
    except Exception as e:
        logger.error(f"Error sending client webhook to n8n: {str(e)}")









