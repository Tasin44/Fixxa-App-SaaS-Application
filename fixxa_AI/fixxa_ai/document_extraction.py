"""Document extraction: OCR and data extraction from images/PDFs"""

import logging
import base64
from pathlib import Path
from typing import Union
from .clients import AIClients
from .models import ClientDetails
from .config import Config

logger = logging.getLogger(__name__)


def encode_image_to_base64(file_path: str) -> str:
    """
    Encode image file to base64 for GPT-4 Vision.
    
    Args:
        file_path: Path to image file
    
    Returns:
        str: Base64 encoded image
    """
    try:
        with open(file_path, 'rb') as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        logger.error(f"Failed to encode image: {e}")
        raise


def extract_text_from_image(file_path: str) -> str:
    """
    Extract text from image using GPT-4 Vision.
    
    Args:
        file_path: Path to image file (jpg, png, etc.)
    
    Returns:
        str: Extracted text content
    """
    try:
        client = AIClients.get_openai_client()
        
        # Encode image
        base64_image = encode_image_to_base64(file_path)
        
        # Determine image type
        file_ext = Path(file_path).suffix.lower()
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }
        mime_type = mime_types.get(file_ext, 'image/jpeg')
        
        # Use GPT-4 Vision to extract text
        response = client.chat.completions.create(
            model="gpt-4o",  # GPT-4 Vision model
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """Extract ALL text from this image. 
                            Include:
                            - Client/customer names, addresses, phone numbers, emails
                            - Item descriptions, quantities, prices
                            - Dates (invoice date, due date)
                            - Totals, subtotals, taxes, discounts
                            - Any other relevant information
                            
                            Return the extracted text in a clear, organized format."""
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=1500
        )
        
        extracted_text = response.choices[0].message.content
        logger.info(f"Extracted text from image: {len(extracted_text)} characters")
        
        return extracted_text
    
    except Exception as e:
        logger.error(f"Image text extraction failed: {e}")
        raise


def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract text from PDF file.
    
    Args:
        file_path: Path to PDF file
    
    Returns:
        str: Extracted text content
    """
    try:
        # Try using PyPDF2 first
        try:
            import PyPDF2
            
            with open(file_path, 'rb') as pdf_file:
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                
                if text.strip():
                    logger.info(f"Extracted text from PDF using PyPDF2: {len(text)} characters")
                    return text
        except ImportError:
            logger.warning("PyPDF2 not installed, falling back to GPT-4 Vision")
        except Exception as e:
            logger.warning(f"PyPDF2 extraction failed: {e}, trying GPT-4 Vision")
        
        # Fallback: Convert first page to image and use GPT-4 Vision
        # For complex PDFs or when PyPDF2 fails
        logger.info("Using GPT-4 Vision for PDF extraction")
        
        # For simple implementation, we'll use GPT-4 Vision with PDF as image
        # In production, you might want to use pdf2image library
        client = AIClients.get_openai_client()
        
        with open(file_path, 'rb') as pdf_file:
            pdf_content = base64.b64encode(pdf_file.read()).decode('utf-8')
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """Extract ALL text and data from this PDF document.
                            Include:
                            - Client/customer information (names, addresses, contacts)
                            - Item descriptions, services, materials, quantities, prices
                            - Dates (invoice date, due date, service date)
                            - Financial details (subtotal, tax, discount, total)
                            - Any other relevant business information
                            
                            Return in clear, organized format."""
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:application/pdf;base64,{pdf_content}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=2000
        )
        
        extracted_text = response.choices[0].message.content
        logger.info(f"Extracted text from PDF: {len(extracted_text)} characters")
        
        return extracted_text
    
    except Exception as e:
        logger.error(f"PDF text extraction failed: {e}")
        raise


"""Document extraction: OCR and data extraction from images/PDFs"""

import logging
import base64
from pathlib import Path
from .clients import AIClients
from .models import ClientDetails
from .config import Config

logger = logging.getLogger(__name__)

# ...existing code... (keep encode_image_to_base64, extract_text_from_image, extract_text_from_pdf unchanged)

def extract_data_from_document(file_path: str, document_type: str = "quote") -> ClientDetails:
    try:
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext == '.pdf':
            extracted_text = extract_text_from_pdf(file_path)
        elif file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
            extracted_text = extract_text_from_image(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")
        
        client = AIClients.get_openai_client()
        
        system_prompt = """You are an AI that extracts structured business information from documents.
Extract client details and quote/invoice items accurately.
For phone numbers, extract digits only.
For prices, extract numeric values only."""
        
        user_prompt = f"""Extract information from this {document_type} document text:

{extracted_text}

Extract and structure:
1. Client Information:
   - client_name
   - phone_number (digits only)
   - address
   - email

2. Document Information:
   - issue_date (format: YYYY-MM-DD)
   - due_date (format: YYYY-MM-DD)
   - vat_rate (default: 20.0)

3. Items (array):
   Each item should have:
   - quote_description (what is being sold/serviced)
   - quantity (number of units, default: 1)
   - unit_price (price per unit)

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
        logger.info(f"Data extracted from document: {extracted_data.client_name}")
        return extracted_data
    
    except Exception as e:
        logger.error(f"Document data extraction failed: {e}")
        raise

# ...existing code... (keep process_document_file unchanged)

def process_document_file(file_path: str, document_type: str = "quote") -> dict:
    """
    Complete workflow: extract text and structure data from document.
    
    This is the main function for document processing.
    
    Args:
        file_path: Path to document file (image or PDF)
        document_type: Type of document ("quote" or "invoice")
    
    Returns:
        dict: {
            'success': bool,
            'extracted_text': str,
            'extracted_data': ClientDetails,
            'error': str (if failed)
        }
    
    Example:
        >>> # In Django view
        >>> document_file = request.FILES['document']
        >>> file_path = default_storage.save(f'temp/{document_file.name}', document_file)
        >>> result = process_document_file(file_path, document_type='invoice')
        >>> if result['success']:
        >>>     invoice_data = result['extracted_data']
    """
    try:
        # Validate file exists
        if not Path(file_path).exists():
            raise FileNotFoundError(f"Document file not found: {file_path}")
        
        # Extract structured data (includes text extraction)
        logger.info(f"Processing document file: {file_path}")
        
        # Get extracted text first
        file_ext = Path(file_path).suffix.lower()
        if file_ext == '.pdf':
            extracted_text = extract_text_from_pdf(file_path)
        else:
            extracted_text = extract_text_from_image(file_path)
        
        # Then extract structured data
        extracted_data = extract_data_from_document(file_path, document_type)
        
        return {
            'success': True,
            'extracted_text': extracted_text,
            'extracted_data': extracted_data
        }
    
    except Exception as e:
        logger.error(f"Document processing failed: {e}")
        return {
            'success': False,
            'error': str(e)
        }
