"""Utility functions"""

import re
import logging
from .clients import AIClients

logger = logging.getLogger(__name__)


def validate_user_id(user_id: str) -> bool:
    """
    Validate user ID is a valid UUID format.
    
    Args:
        user_id: User UUID string
    
    Returns:
        bool: True if valid
    
    Raises:
        ValueError: If invalid UUID format
    """
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    
    if not re.match(uuid_pattern, user_id.lower()):
        raise ValueError(f"Invalid user_id format: {user_id}. Must be a valid UUID.")
    
    return True


def check_database_health() -> dict:
    """
    Check PostgreSQL database connection and get basic info.
    
    Returns:
        dict: {
            'status': str ('healthy' or 'unhealthy'),
            'database': str (database name),
            'tables': list (available tables),
            'message': str (error message if unhealthy)
        }
    """
    try:
        db = AIClients.get_database()
        
        # Get table names
        tables = db.get_usable_table_names()
        
        # Extract database name from connection
        dialect = db.dialect if hasattr(db, 'dialect') else 'postgresql'
        
        return {
            'status': 'healthy',
            'database': str(dialect),
            'tables': tables,
            'table_count': len(tables)
        }
    
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            'status': 'unhealthy',
            'message': str(e)
        }


def clean_phone_number(phone: str) -> str:
    """
    Extract only digits from phone number.
    
    Args:
        phone: Phone number string (e.g., "(123) 456-7890")
    
    Returns:
        str: Cleaned phone number (e.g., "1234567890")
    """
    if not phone:
        return ""
    
    return re.sub(r'\D', '', phone)


def format_currency(amount: float) -> str:
    """
    Format amount as currency.
    
    Args:
        amount: Numeric amount
    
    Returns:
        str: Formatted as "$X,XXX.XX"
    """
    if amount is None:
        return "$0.00"
    
    return f"${amount:,.2f}"
