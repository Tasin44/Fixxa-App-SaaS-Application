# utils/n8n_webhooks.py
import requests
import json
import logging
from django.conf import settings
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class N8NWebhookClient:
    """Client for sending data to n8n webhooks"""
    
    def __init__(self):
        self.base_url = getattr(settings, 'N8N_WEBHOOK_URL', 'http://localhost:5678/webhook')
        self.api_key = getattr(settings, 'N8N_API_KEY', '')
    
    def send_webhook(self, webhook_name: str, data: Dict[str, Any]) -> Optional[Dict]:
        """
        Send data to n8n webhook
        
        Args:
            webhook_name: Name of the webhook endpoint (e.g., 'client-created', 'quote-sent')
            data: Data to send to n8n
            
        Returns:
            Response from n8n or None if failed
        """
        try:
            # Construct webhook URL
            url = f"{self.base_url}/{webhook_name}"
            
            # Prepare headers
            headers = {
                'Content-Type': 'application/json',
            }
            
            # Add API key if configured
            if self.api_key:
                headers['Authorization'] = f'Bearer {self.api_key}'
            
            # Send POST request to n8n
            response = requests.post(
                url=url,
                json=data,
                headers=headers,
                timeout=30  # 30 second timeout
            )
            
            response.raise_for_status()  # Raise exception for bad status codes
            
            logger.info(f"Successfully sent {webhook_name} webhook to n8n")
            return response.json() if response.content else {}
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send {webhook_name} webhook to n8n: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error sending {webhook_name} webhook: {str(e)}")
            return None

# Initialize client instance
n8n_client = N8NWebhookClient()














