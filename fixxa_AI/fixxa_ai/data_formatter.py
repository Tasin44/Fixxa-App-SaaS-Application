"""Data formatter: Convert AI extracted data to Django backend format"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
from .models import ClientDetails

logger = logging.getLogger(__name__)


def format_client_data_for_backend(extracted_data: ClientDetails) -> Dict[str, Any]:
    return {
        'name': extracted_data.client_name,
        'phone_number': extracted_data.phone_number or '',
        'address': extracted_data.address or '',
        'email': extracted_data.email or '',
        'source': 'manual',
    }


def format_quote_items_for_backend(extracted_data: ClientDetails) -> List[Dict[str, Any]]:
    items = []
    for item in extracted_data.items:
        formatted_item = {
            'quote_description': item.quote_description,
            'quantity': item.quantity,
            'unit_price': item.unit_price,
        }
        items.append(formatted_item)
    return items


def format_quote_data_for_backend(extracted_data: ClientDetails, client_id: int, user_id: str) -> Dict[str, Any]:
    issue_date = extracted_data.issue_date or datetime.now().strftime('%Y-%m-%d')
    
    if extracted_data.due_date:
        due_date = extracted_data.due_date
    else:
        issue_dt = datetime.strptime(issue_date, '%Y-%m-%d')
        due_date = (issue_dt + timedelta(days=30)).strftime('%Y-%m-%d')
    
    items = format_quote_items_for_backend(extracted_data)
    
    quote_data = {
        'client': client_id,
        'issue_date': issue_date,
        'due_date': due_date,
        'vat_rate': float(extracted_data.vat_rate) if extracted_data.vat_rate else 20.0,
        'items': items,
    }
    
    if extracted_data.notes:
        quote_data['notes'] = extracted_data.notes
    
    logger.info(f"Formatted quote data for client {client_id}: {len(items)} items")
    return quote_data


def format_invoice_data_for_backend(extracted_data: ClientDetails, client_id: int, user_id: str) -> Dict[str, Any]:
    issue_date = extracted_data.issue_date or datetime.now().strftime('%Y-%m-%d')
    
    if extracted_data.due_date:
        due_date = extracted_data.due_date
    else:
        issue_dt = datetime.strptime(issue_date, '%Y-%m-%d')
        due_date = (issue_dt + timedelta(days=30)).strftime('%Y-%m-%d')
    
    items = format_quote_items_for_backend(extracted_data)
    
    invoice_data = {
        'client': client_id,
        'issue_date': issue_date,
        'due_date': due_date,
        'vat_rate': float(extracted_data.vat_rate) if extracted_data.vat_rate else 20.0,
        'items': items,
    }
    
    if extracted_data.notes:
        invoice_data['notes'] = extracted_data.notes
    
    logger.info(f"Formatted invoice data for client {client_id}: {len(items)} items")
    return invoice_data


def validate_extracted_data(extracted_data: ClientDetails, document_type: str = "quote") -> Dict[str, Any]:
    errors = []
    
    if not extracted_data.client_name or extracted_data.client_name.strip() == '':
        errors.append("Client name is required")
    
    if not extracted_data.items or len(extracted_data.items) == 0:
        errors.append(f"At least one item is required for {document_type}")
    
    for idx, item in enumerate(extracted_data.items):
        if not item.quote_description or item.quote_description.strip() == '':
            errors.append(f"Item {idx + 1}: Description is required")
        
        if item.quantity <= 0:
            errors.append(f"Item {idx + 1}: Quantity must be greater than 0")
        
        if item.unit_price == 0:
            errors.append(f"Item {idx + 1}: Unit price is required")
    
    return {
        'valid': len(errors) == 0,
        'errors': errors
    }