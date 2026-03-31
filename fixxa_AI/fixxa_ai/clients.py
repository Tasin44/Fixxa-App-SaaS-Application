"""Singleton clients for external services"""

from openai import OpenAI
from langchain_community.utilities import SQLDatabase
from .config import Config
import logging

logger = logging.getLogger(__name__)


class AIClients:
    """Singleton manager for external service clients"""
    
    _openai_client = None
    # _database = None
    
    @classmethod
    def get_openai_client(cls) -> OpenAI:
        """Get OpenAI client (singleton)"""
        if cls._openai_client is None:
            api_key = Config.OPENAI_API_KEY

            if not api_key:
                raise ValueError("OPENAI_API_KEY not configured in .env file")
            
            cls._openai_client = OpenAI(api_key=Config.OPENAI_API_KEY)
            logger.info("OpenAI client initialized")
        
        return cls._openai_client
    
    # @classmethod
    # def get_database(cls) -> SQLDatabase:
    #     """Get PostgreSQL database connection (singleton)"""
    #     if cls._database is None:
    #         if not Config.DATABASE_URL:
    #             raise ValueError("DATABASE_URL not configured in .env file")
            
    #         try:
    #             cls._database = SQLDatabase.from_uri(Config.DATABASE_URL)
    #             logger.info("PostgreSQL database connection established")
    #         except Exception as e:
    #             logger.error(f"Failed to connect to PostgreSQL: {e}")
    #             raise
        
    #     return cls._database
