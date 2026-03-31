"""Configuration management for Fixxa AI"""

import os
from dotenv import load_dotenv
import logging
from django.conf import settings

# # Load environment variables
# load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class Config:
    """Centralized configuration"""
    
    # OpenAI API Configuration
    # OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    OPENAI_API_KEY = settings.OPENAI_API_KEY
    
    # PostgreSQL Database Configuration
    # DATABASE_URL = os.getenv('DATABASE_URL')
    
    # OpenAI Models
    WHISPER_MODEL = "whisper-1"
    GPT_MODEL = "gpt-4o-2024-08-06"
    SQL_MODEL = "gpt-4"
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        missing = []
        
        if not cls.OPENAI_API_KEY:
            missing.append('OPENAI_API_KEY')
        # if not cls.DATABASE_URL:
        #     missing.append('DATABASE_URL')
        
        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}. "
                f"Please check your .env file."
            )
        
        return True
