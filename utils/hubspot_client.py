

import requests
from django.conf import settings
from typing import Dict, Optional
import logging
from urllib.parse import urljoin
logger = logging.getLogger(__name__)

class HubSpotClient:
    """HubSpot API client for managing contacts and deals"""
    
    def __init__(self):
        self.api_key = settings.HUBSPOT_API_KEY
        self.base_url = settings.HUBSPOT_BASE_URL
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }
    
    def create_contact(self, client_data: Dict) -> Optional[str]:
        """
        Create a contact in HubSpot from Django Client data
        Returns: HubSpot contact ID if successful, None if failed
        """
        url = f"{self.base_url}/crm/v3/objects/contacts"
        url = urljoin(self.base_url, '/crm/v3/objects/contacts')
        # Transform Django client data to HubSpot format
        hubspot_data = {#Takes a dictionary of client data from client  model
            "properties": {#Maps fields: name to firstname/lastname, email to email, etc.
                "firstname": client_data.get('name', '').split(' ')[0],
                "lastname": ' '.join(client_data.get('name', '').split(' ')[1:]) or '',
                "email": client_data.get('email', ''),
                "phone": client_data.get('phone_number', ''),
                "address": client_data.get('address', ''),
                "custom_client_id": str(client_data.get('id', ''))  # Stores the Django client_id as a custom property (custom_client_id) for tracking.
            }
        }
        
        try:
            response = requests.post(url, json=hubspot_data, headers=self.headers)#Sends a POST request to HubSpot’s Contacts API (/crm/v3/objects/contacts) to create a Contact.
            response.raise_for_status()  # Raise an exception for bad status codes (4xx, 5xx)
            if response.status_code == 201:
                return response.json().get('id')
            else:
                logger.error(f"HubSpot contact creation failed: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error creating HubSpot contact: {str(e)}")
            return None
    
    def create_deal(self, quote_data: Dict, hubspot_contact_id: str) -> Optional[str]:
        """
        Create a deal in HubSpot from Django Quote data(Quote MODEL)
        Returns: HubSpot deal ID if successful, None if failed
        """
        url = f"{self.base_url}/crm/v3/objects/deals"#Sends a POST request to HubSpot’s Deals API (/crm/v3/objects/deals) to create a Deal.
        
        hubspot_data = {
            "properties": {
                "dealname": f"Quote #{quote_data.get('quote_id')} - {quote_data.get('service_type', 'Service')}",
                "amount": str(quote_data.get('total', 0)),
                "dealstage": self._map_quote_status_to_hubspot(quote_data.get('status', 'sent')),
                "pipeline": "default",  # Use your HubSpot pipeline ID
                "custom_quote_id": str(quote_data.get('quote_id', ''))
            },
            "associations": [
                {
                    "to": {"id": hubspot_contact_id},
                    "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 3}]  # Deal to Contact
                }
            ]
        }
        
        try:
            response = requests.post(url, json=hubspot_data, headers=self.headers)
            if response.status_code == 201:
                return response.json().get('id')
            else:
                logger.error(f"HubSpot deal creation failed: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error creating HubSpot deal: {str(e)}")
            return None
    
    def _map_quote_status_to_hubspot(self, quote_status: str) -> str:
        """Maps your Quote model’s status (sent, won, lost) to HubSpot deal stages (e.g., qualifiedtobuy, closedwon, closedlost)."""
        mapping = {
            'sent': 'qualifiedtobuy',  # Replace with your actual HubSpot stage IDs
            'won': 'closedwon',
            'lost': 'closedlost'
        }
        return mapping.get(quote_status, 'qualifiedtobuy')


'''
Will It Automatically Create Contacts and Deals?
Yes, but it requires integration with your Django app:

The HubSpotClient class itself doesn’t “automatically” create anything—it provides methods (create_contact, create_deal) that you must call explicitly in your code (e.g., in signals or views).
To make it automatic, you need to:

Call create_contact when a Client is saved (e.g., via a post_save signal in clientapp/signals.py).
Call create_deal when a Quote is created or updated (e.g., via a post_save signal in quoteapp/signals.py).
Ensure the HubSpot API token and base URL are configured in your Django settings.


If integrated correctly (e.g., via signals as shown in your previous code), it will automatically:

Create a HubSpot Contact when a Client is created/updated in Django.
Create a HubSpot Deal when a Quote is created/updated, linked to the corresponding Contact.

'''








