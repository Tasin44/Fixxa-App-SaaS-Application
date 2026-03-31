'''
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Quote
from utils.n8n_webhooks import n8n_client
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Quote)
def quote_status_changed(sender, instance, created, **kwargs):
    """
    Trigger n8n workflow when quote is created or status changes
    This handles:
    - Creating HubSpot deals for new quotes
    - Sending quotes via email/WhatsApp
    - Updating deal status in HubSpot
    """
    try:
        # Prepare quote data for n8n
        quote_data = {
            'action': 'created' if created else 'updated',
            'timestamp': timezone.now().isoformat(),
            'quote': {
                'id': instance.quote_id,
                'status': instance.status,
                'service_type': instance.service_type,
                'service_description': instance.service_description,
                'subtotal': float(instance.subtotal),
                'tax_amount': float(instance.tax_amount),
                'total': float(instance.total),
                'sent_via': instance.sent_via,
                'sent_at': instance.sent_at.isoformat() if instance.sent_at else None,
                'expiry_date': instance.expiry_date.isoformat() if instance.expiry_date else None,
                'service_location': instance.service_location,
                'created_at': instance.created_at.isoformat(),
            },
            'client': {
                'id': instance.client.id,
                'name': instance.client.name,
                'email': instance.client.email,
                'phone_number': instance.client.phone_number,
                'address': instance.client.address,
            }
        }
        
        # Send different webhooks based on action and status
        if created:
            # New quote created - create HubSpot deal
            n8n_client.send_webhook('quote-created', quote_data)
            logger.info(f"Quote {instance.quote_id} created webhook sent to n8n")
            
        elif instance.status == 'sent':
            # Quote sent - trigger email/WhatsApp sending
            n8n_client.send_webhook('quote-send', quote_data)
            logger.info(f"Quote {instance.quote_id} send webhook sent to n8n")
            
        elif instance.status in ['won', 'lost']:
            # Quote status changed - update HubSpot deal
            n8n_client.send_webhook('quote-status-update', quote_data)
            logger.info(f"Quote {instance.quote_id} status update webhook sent to n8n")
            
    except Exception as e:
        logger.error(f"Error sending quote webhook to n8n: {str(e)}")

'''



# 4. Create signals for quotes
# Create new file: quoteapp/signals.py  
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Quote
from utils.n8n_webhooks import n8n_client
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Quote)
def quote_status_changed(sender, instance, created, **kwargs):
    """
    Trigger n8n workflow when quote is created or status changes
    This handles:
    - Creating HubSpot deals for new quotes
    - Sending quotes via email/WhatsApp
    - Updating deal status in HubSpot
    """
    try:
        # Prepare quote data for n8n
        quote_data = {
            'action': 'created' if created else 'updated',
            'timestamp': timezone.now().isoformat(),
            'quote': {
                'id': instance.quote_id,
                'status': instance.status,
                'service_type': instance.service_type,
                'service_description': instance.service_description,
                'subtotal': float(instance.subtotal),
                'tax_amount': float(instance.tax_amount),
                'total': float(instance.total),
                'sent_via': instance.sent_via,
                'sent_at': instance.sent_at.isoformat() if instance.sent_at else None,
                'expiry_date': instance.expiry_date.isoformat() if instance.expiry_date else None,
                'service_location': instance.service_location,
                'created_at': instance.created_at.isoformat(),
            },
            'client': {
                'id': instance.client.id,
                'name': instance.client.name,
                'email': instance.client.email,
                'phone_number': instance.client.phone_number,
                'address': instance.client.address,
            }
        }
        
        # Send different webhooks based on action and status
        if created:
            # New quote created - create HubSpot deal
            n8n_client.send_webhook('quote-created', quote_data)
            logger.info(f"Quote {instance.quote_id} created webhook sent to n8n")
            
        elif instance.status == 'sent':
            # Quote sent - trigger email/WhatsApp sending
            n8n_client.send_webhook('quote-send', quote_data)
            logger.info(f"Quote {instance.quote_id} send webhook sent to n8n")
            
        elif instance.status in ['won', 'lost']:
            # Quote status changed - update HubSpot deal
            n8n_client.send_webhook('quote-status-update', quote_data)
            logger.info(f"Quote {instance.quote_id} status update webhook sent to n8n")
            
    except Exception as e:
        logger.error(f"Error sending quote webhook to n8n: {str(e)}")




