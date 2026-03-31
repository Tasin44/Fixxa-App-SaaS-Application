"""Voice Data Mapper - Maps AI-extracted data to Django model fields"""

from datetime import datetime, timedelta
from typing import Dict, List, Any


def map_voice_to_quote_data(voice_data: Dict[str, Any]) -> Dict[str, Any]:
    today = datetime.now().date()
    return {
        "source": "voice",
        "issue_date": voice_data.get("issue_date") or today.isoformat(),
        "due_date": voice_data.get("due_date") or (today + timedelta(days=30)).isoformat(),
        "vat_rate": voice_data.get("vat_rate", 20.0),
        "quote_status": "draft",
        "items": map_voice_items(voice_data.get("items", []))
    }


def map_voice_to_invoice_data(voice_data: Dict[str, Any]) -> Dict[str, Any]:
    today = datetime.now().date()
    return {
        "source": "voice",
        "issue_date": voice_data.get("issue_date") or today.isoformat(),
        "due_date": voice_data.get("due_date") or (today + timedelta(days=30)).isoformat(),
        "vat_rate": voice_data.get("vat_rate", 20.0),
        "payment_status": "unpaid",
        "items": map_voice_items(voice_data.get("items", []))
    }


def map_voice_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    mapped_items = []
    for item in items:
        mapped_item = {
            "quote_description": item.get("quote_description") or item.get("description", ""),
            "quantity": int(item.get("quantity", 1)),
            "unit_price": float(item.get("unit_price", 0.0)),
        }
        mapped_items.append(mapped_item)
    return mapped_items


def validate_voice_data(voice_data: Dict[str, Any], document_type: str = "quote") -> Dict[str, Any]:
    if not voice_data.get("items") or len(voice_data.get("items", [])) == 0:
        raise ValueError("At least one service item is required")
    
    for i, item in enumerate(voice_data.get("items", [])):
        if not item.get("quote_description") and not item.get("description"):
            raise ValueError(f"Item {i+1}: quote_description is required")
    
    if document_type == "quote":
        return map_voice_to_quote_data(voice_data)
    elif document_type == "invoice":
        return map_voice_to_invoice_data(voice_data)
    else:
        raise ValueError(f"Invalid document_type: {document_type}")