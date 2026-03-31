"""Voice processing: transcription and data extraction"""

import logging
from pathlib import Path
from .clients import AIClients
from .models import ClientDetails
from .config import Config

logger = logging.getLogger(__name__)


def transcribe_audio_file(file_path: str) -> str:
    try:
        client = AIClients.get_openai_client()
        print(f"OpenAI API Key: {client.api_key}")  # Add this line
        with open(file_path, 'rb') as audio_file:
            response = client.audio.transcriptions.create(
                model=Config.WHISPER_MODEL,
                file=audio_file,
                response_format="text"
            )
        transcription = response if isinstance(response, str) else response.text
        logger.info(f"Audio transcribed: {len(transcription)} characters")
        return transcription
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise


def extract_client_data(transcription: str, document_type: str = "client_details") -> ClientDetails:
    try:
        client = AIClients.get_openai_client()
        print(f"OpenAI API Key: {client.api_key}")  # Add this line
        
        system_prompt = """You are an AI assistant that extracts structured information from voice transcriptions.
Extract all relevant client and service information accurately.
For phone numbers, extract digits only.
For costs, extract numeric values only."""
        
        user_prompt = f"""Extract information from this {document_type} transcription:

{transcription}

Extract and structure:
1. Client Information:
   - client_name
   - phone_number (digits only)
   - address
   - email

2. Quote/Invoice Information:
   - issue_date (format: YYYY-MM-DD)
   - due_date (format: YYYY-MM-DD)
   - vat_rate (default: 20.0)

3. Items (array):
   Each item should have:
   - quote_description (what work needs to be done)
   - quantity (default: 1)
   - unit_price (price per unit, default: 0)

4. Additional:
   - notes (any extra information)"""
        
        response = client.beta.chat.completions.parse(
            model=Config.GPT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format=ClientDetails
        )
        
        extracted_data = response.choices[0].message.parsed
        logger.info(f"Data extracted for client: {extracted_data.client_name}")
        return extracted_data
    
    except Exception as e:
        logger.error(f"Data extraction failed: {e}")
        raise


def process_audio_from_file(file_path: str, document_type: str = "client_details") -> dict:
    try:
        if not Path(file_path).exists():
            raise FileNotFoundError(f"Audio file not found: {file_path}")
        
        logger.info(f"Processing audio file: {file_path}")
        transcription = transcribe_audio_file(file_path)
        extracted_data = extract_client_data(transcription, document_type)
        
        return {
            'success': True,
            'transcription': transcription,
            'extracted_data': extracted_data
        }
    
    except Exception as e:
        logger.error(f"Audio processing failed: {e}")
        return {
            'success': False,
            'error': str(e)
        }