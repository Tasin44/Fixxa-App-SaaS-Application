"""Pydantic models for data validation"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
import re


class ServiceItem(BaseModel):
    """Service item in work order - maps to QuoteItem/InvoiceItem"""
    quote_description: str  # Maps to quote_description field
    # service_type: str = "General Service"  # Maps to service_type field
    # service_duration: float = 1.0  # Maps to service_duration field
    # service_rate: float = 0.0  # Maps to service_rate field
    quantity: int = 1  # Maps to quantity field
    unit_price: float = 0.0  # Maps to unit_price field
    # material_name: Optional[str] = None  # Maps to material_name field


class MaterialItem(BaseModel):
    """Material item in work order - embedded in ServiceItem"""
    material_name: str  # Maps to material_name field
    quantity: int = 1  # Maps to quantity field
    unit_price: float = 0.0  # Maps to unit_price field


class ClientDetails(BaseModel):
    """Client details extracted from voice"""
    client_name: str
    phone_number: Optional[str] = None
    address: Optional[str] = None
    email: Optional[str] = None
    # service_type: Optional[str] = None
    # issue_description: Optional[str] = None
    # estimated_cost: Optional[float] = None
    # appointment_date: Optional[str] = None
    notes: Optional[str] = None
    
    # Quote/Invoice specific fields
    issue_date: Optional[str] = None  # Maps to issue_date
    due_date: Optional[str] = None  # Maps to due_date
    # duration_unit: str = "hours"  # Maps to duration_unit (hours/days)
    # discount_amount: float = 0.0  # Maps to discount_amount
    # discount_type: str = "percentage"  # Maps to discount_type
    vat_rate: float = 20.0  # Maps to vat_rate
    # service_location: Optional[str] = None  # Maps to service_location
    
    # Items list - maps to QuoteItem/InvoiceItem
    items: Optional[List[ServiceItem]] = Field(default_factory=list)
    
    @field_validator('phone_number')
    @classmethod
    def clean_phone(cls, v):
        """Extract only digits from phone number"""
        if v:
            return re.sub(r'\D', '', v)
        return v
    
    # @field_validator('estimated_cost')
    # @classmethod
    # def clean_cost(cls, v):
    #     """Extract numeric value from cost"""
    #     if isinstance(v, str):
    #         numbers = re.findall(r'\d+\.?\d*', v)
    #         return float(numbers[0]) if numbers else None
    #     return v


class ChatQueryResult(BaseModel):
    """Result from natural language query"""
    success: bool
    sql_query: Optional[str] = None
    result: Optional[List[dict]] = None
    answer: Optional[str] = None
    error: Optional[str] = None
