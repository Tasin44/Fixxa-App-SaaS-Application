"""
Fixxa AI - Voice Processing, Document Extraction & SQL Chatbot
================================================================
For Django Backend Integration

Version: 3.0.0
"""

__version__ = "3.0.0"

# Voice processing functions
from .voice import (
    transcribe_audio_file,
    extract_client_data,
    process_audio_from_file
)

# Document extraction functions
from .document_extraction import (
    extract_text_from_image,
    extract_text_from_pdf,
    extract_data_from_document,
    process_document_file
)

# SQL chatbot functions
from .chatbot import (
    natural_language_query,
)

# Utility functions
from .utils import (
    check_database_health,
    validate_user_id
)

__all__ = [
    # Voice processing
    'transcribe_audio_file',
    'extract_client_data',
    'process_audio_from_file',
    
    # Document extraction
    'extract_text_from_image',
    'extract_text_from_pdf',
    'extract_data_from_document',
    'process_document_file',
    
    # SQL chatbot
    'natural_language_query',
    
    # Utilities
    'check_database_health',
    'validate_user_id',
]
