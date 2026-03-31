# """
# AI-powered views for Fixxa Backend
# ===================================
# Voice and Document processing for automatic Quote/Invoice generation
# """

# import sys
# import os
# from pathlib import Path
# from rest_framework.views import APIView
# from rest_framework.response import Response
# from rest_framework import status
# from rest_framework.permissions import IsAuthenticated
# from rest_framework.parsers import MultiPartParser, FormParser
# from django.core.files.storage import default_storage
# from django.db import transaction
# from django.utils import timezone
# import logging
# import json

# # Import Django models
# from clientapp.models import Client
# from quoteapp.models import Quote, QuoteItem, Invoice, InvoiceItem, QuoteCounter, InvoiceCounter
# from quoteapp.views import ensure_client_folder
# from decimal import Decimal

# logger = logging.getLogger(__name__)

# # Lazy import function for AI modules (to avoid slow startup)
# def get_ai_modules():
#     """Import AI modules only when needed"""
#     FIXXA_AI_PATH = Path(__file__).parent.parent / 'fixxa_AI'
#     if str(FIXXA_AI_PATH) not in sys.path:
#         sys.path.insert(0, str(FIXXA_AI_PATH))
    
#     try:
#         from fixxa_ai import (
#             process_audio_from_file,
#             process_document_file,
#             natural_language_query
#         )
#         from fixxa_ai.data_formatter import (
#             format_client_data_for_backend,
#             format_quote_data_for_backend,
#             format_invoice_data_for_backend,
#             validate_extracted_data
#         )
#         return {
#             'process_audio_from_file': process_audio_from_file,
#             'process_document_file': process_document_file,
#             'natural_language_query': natural_language_query,
#             'format_client_data_for_backend': format_client_data_for_backend,
#             'format_quote_data_for_backend': format_quote_data_for_backend,
#             'format_invoice_data_for_backend': format_invoice_data_for_backend,
#             'validate_extracted_data': validate_extracted_data,
#             'available': True
#         }
#     except ImportError as e:
#         logger.warning(f"AI modules not available: {e}")
#         return {'available': False, 'error': str(e)}


# class StandardResponseMixin:
#     """Mixin for consistent API responses"""

#     def success_response(self, data, message="Success", status_code=200):
#         return Response({
#             "success": True,
#             "statusCode": status_code,
#             "message": message,
#             "data": data,
#             "timestamp": timezone.now().isoformat()
#         }, status=status_code)

#     def error_response(self, message, status_code=400, data=None):
#         return Response({
#             "success": False,
#             "statusCode": status_code,
#             "message": message,
#             "data": data,
#             "timestamp": timezone.now().isoformat()
#         }, status=status_code)


# class VoiceQuoteCreateView(StandardResponseMixin, APIView):
#     """
#     AI-powered quote creation from voice note.
    
#     POST /api/ai/voice/quote/
#     Content-Type: multipart/form-data
#     Authorization: Bearer <token>
    
#     Body:
#     - audio: Audio file (mp3, wav, m4a, ogg, webm)
    
#     Process:
#     1. Transcribe audio using Whisper
#     2. Extract client & quote data using GPT-4
#     3. Create new client
#     4. Create quote with items
#     5. Return created quote
#     """
    
#     permission_classes = [IsAuthenticated]
#     parser_classes = [MultiPartParser, FormParser]
    
#     def post(self, request):
#         # Load AI modules
#         ai = get_ai_modules()
#         if not ai['available']:
#             return self.error_response(
#                 f"AI module not available: {ai.get('error', 'Unknown error')}",
#                 status_code=status.HTTP_503_SERVICE_UNAVAILABLE
#             )
        
#         # Validate audio file
#         if 'audio' not in request.FILES:
#             return self.error_response("Audio file is required", status_code=status.HTTP_400_BAD_REQUEST)
        
#         audio_file = request.FILES['audio']
        
#         # Validate file type
#         allowed_extensions = ['.mp3', '.wav', '.m4a', '.ogg', '.webm']
#         file_ext = Path(audio_file.name).suffix.lower()
#         if file_ext not in allowed_extensions:
#             return self.error_response(
#                 f"Invalid file type. Allowed: {', '.join(allowed_extensions)}",
#                 status_code=status.HTTP_400_BAD_REQUEST
#             )
        
#         temp_file_path = None
        
#         try:
#             # Save audio file temporarily
#             temp_file_path = default_storage.save(f'temp/audio/{audio_file.name}', audio_file)
#             full_path = default_storage.path(temp_file_path)
            
#             logger.info(f"Processing voice quote for user {request.user.id}")
            
#             # Process audio with AI
#             result = ai['process_audio_from_file'](full_path, document_type="quote")
            
#             if not result['success']:
#                 return self.error_response(
#                     f"AI processing failed: {result.get('error')}",
#                     status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
#                 )
            
#             extracted_data = result['extracted_data']
#             transcription = result['transcription']
            
#             # Validate extracted data
#             validation = ai['validate_extracted_data'](extracted_data, document_type="quote")
#             if not validation['valid']:
#                 return self.error_response(
#                     "Extracted data is incomplete",
#                     status_code=status.HTTP_400_BAD_REQUEST,
#                     data={'errors': validation['errors'], 'transcription': transcription}
#                 )
            
#             # Create client and quote in transaction
#             with transaction.atomic():
#                 # 1. Create new client
#                 client_data = ai['format_client_data_for_backend'](extracted_data)
#                 client_data['user'] = request.user
#                 client_data['source'] = 'manual'  # Coming from voice
                
#                 client = Client.objects.create(**client_data)
#                 logger.info(f"Created client: {client.name} (ID: {client.id})")
                
#                 # 1b. Create folder for client
#                 ensure_client_folder(request.user, client)
                
#                 # 2. Format quote data
#                 quote_data = ai['format_quote_data_for_backend'](extracted_data, client.id, str(request.user.id))
                
#                 # 3. Generate quote number
#                 year = timezone.now().year
#                 counter_obj, created = QuoteCounter.objects.select_for_update().get_or_create(
#                     user=request.user,
#                     year=year
#                 )
#                 counter_obj.counter += 1
#                 counter_obj.save()
                
#                 short_uid = str(request.user.id)[:4]
#                 quote_number = f"QT-{short_uid}-{year}-{counter_obj.counter:02d}"
                
#                 # 4. Create quote
#                 items_data = quote_data.pop('items')
                
#                 quote = Quote.objects.create(
#                     user=request.user,
#                     client=client,
#                     quote_number=quote_number,
#                     source='voice',  # Mark as voice-generated
#                     issue_date=quote_data['issue_date'],
#                     due_date=quote_data['due_date'],
#                     #duration_unit=quote_data['duration_unit'],
#                     #discount_amount=Decimal(str(quote_data['discount_amount'])),
#                     #discount_type=quote_data['discount_type'],
#                     vat_rate=Decimal(str(quote_data['vat_rate'])),
#                     #service_location=quote_data.get('service_location', ''),
#                     subtotal=Decimal('0.00'),
#                     total=Decimal('0.00'),
#                     quote_status='draft'
#                 )
                
#                 # 5. Create quote items
#                 for item_dict in items_data:
#                     QuoteItem.objects.create(
#                         quote=quote,
#                         quote_description=item_dict['quote_description'],
#                         # service_type=item_dict['service_type'],
#                         # service_duration=item_dict['service_duration'],
#                         # service_rate=Decimal(str(item_dict['service_rate'])),
#                         quantity=item_dict['quantity'],
#                         unit_price=Decimal(str(item_dict['unit_price'])),
#                         #material_name=item_dict.get('material_name', ''),
#                         #amount=Decimal(str(item_dict['quantity'])) * Decimal(str(item_dict['unit_price']))
#                     )
                
#                 # 6. Calculate totals
#                 quote.refresh_from_db()
#                 items = quote.items.all()
#                 #subtotal = sum(item.amount for item in items)
#                 subtotal = sum(i.quantity * i.unit_price for i in items)
                
#                 # Calculate discount
#                 if quote.discount_type == 'percentage':
#                     discount_value = subtotal * (quote.discount_amount / Decimal('100'))
#                 else:
#                     discount_value = quote.discount_amount
                
#                 # Calculate VAT
#                 amount_after_discount = subtotal - discount_value
#                 vat_amount = amount_after_discount * (quote.vat_rate / Decimal('100'))
#                 total = amount_after_discount + vat_amount
                
#                 quote.subtotal = subtotal
#                 quote.total = total
#                 quote.save(update_fields=['subtotal', 'total'])
                
#                 logger.info(f"Created quote: {quote.quote_number} with {len(items_data)} items")
            
#             # Return response
#             return self.success_response(
#                 data={
#                     'quote_id': quote.quote_id,
#                     'quote_number': quote.quote_number,
#                     'client': {
#                         'id': client.id,
#                         'name': client.name,
#                         'email': client.email,
#                         'phone_number': client.phone_number
#                     },
#                     'transcription': transcription,
#                     'total': str(quote.total),
#                     'items_count': len(items_data)
#                 },
#                 message="Quote created successfully from voice",
#                 status_code=status.HTTP_201_CREATED
#             )
        
#         except Exception as e:
#             logger.error(f"Voice quote creation failed: {e}")
#             return self.error_response(
#                 f"Failed to create quote: {str(e)}",
#                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )
        
#         finally:
#             # Clean up temp file
#             if temp_file_path and default_storage.exists(temp_file_path):
#                 default_storage.delete(temp_file_path)


# class VoiceInvoiceCreateView(StandardResponseMixin, APIView):
#     """
#     AI-powered invoice creation from voice note.
    
#     POST /api/ai/voice/invoice/
#     Content-Type: multipart/form-data
#     Authorization: Bearer <token>
    
#     Body:
#     - audio: Audio file (mp3, wav, m4a, ogg, webm)
    
#     Process: Same as VoiceQuoteCreateView but creates Invoice
#     """
    
#     permission_classes = [IsAuthenticated]
#     parser_classes = [MultiPartParser, FormParser]
    
#     def post(self, request):
#         # Load AI modules
#         ai = get_ai_modules()
#         if not ai['available']:
#             return self.error_response(
#                 f"AI module not available: {ai.get('error', 'Unknown error')}",
#                 status_code=status.HTTP_503_SERVICE_UNAVAILABLE
#             )
        
#         if 'audio' not in request.FILES:
#             return self.error_response("Audio file is required", status_code=status.HTTP_400_BAD_REQUEST)
        
#         audio_file = request.FILES['audio']
        
#         # Validate file type
#         allowed_extensions = ['.mp3', '.wav', '.m4a', '.ogg', '.webm']
#         file_ext = Path(audio_file.name).suffix.lower()
#         if file_ext not in allowed_extensions:
#             return self.error_response(
#                 f"Invalid file type. Allowed: {', '.join(allowed_extensions)}",
#                 status_code=status.HTTP_400_BAD_REQUEST
#             )
        
#         temp_file_path = None
        
#         try:
#             # Save audio file temporarily
#             temp_file_path = default_storage.save(f'temp/audio/{audio_file.name}', audio_file)
#             full_path = default_storage.path(temp_file_path)
            
#             logger.info(f"Processing voice invoice for user {request.user.id}")
            
#             # Process audio with AI
#             result = ai['process_audio_from_file'](full_path, document_type="invoice")
            
#             if not result['success']:
#                 return self.error_response(
#                     f"AI processing failed: {result.get('error')}",
#                     status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
#                 )
            
#             extracted_data = result['extracted_data']
#             transcription = result['transcription']
            
#             # Validate extracted data
#             validation = ai['validate_extracted_data'](extracted_data, document_type="invoice")
#             if not validation['valid']:
#                 return self.error_response(
#                     "Extracted data is incomplete",
#                     status_code=status.HTTP_400_BAD_REQUEST,
#                     data={'errors': validation['errors'], 'transcription': transcription}
#                 )
            
#             # Create client and invoice in transaction
#             with transaction.atomic():
#                 # 1. Create new client
#                 client_data = ai['format_client_data_for_backend'](extracted_data)
#                 client_data['user'] = request.user
#                 client_data['source'] = 'manual'
                
#                 client = Client.objects.create(**client_data)
#                 logger.info(f"Created client: {client.name} (ID: {client.id})")
                
#                 # 1b. Create folder for client
#                 ensure_client_folder(request.user, client)
                
#                 # 2. Format invoice data
#                 invoice_data = ai['format_invoice_data_for_backend'](extracted_data, client.id, str(request.user.id))
                
#                 # 3. Generate invoice number
#                 year = timezone.now().year
#                 counter_obj, created = InvoiceCounter.objects.select_for_update().get_or_create(
#                     user=request.user,
#                     year=year
#                 )
#                 counter_obj.counter += 1
#                 counter_obj.save()
                
#                 short_uid = str(request.user.id)[:4]
#                 invoice_number = f"INV-{short_uid}-{year}-{counter_obj.counter:02d}"
                
#                 # 4. Create invoice
#                 items_data = invoice_data.pop('items')
                
#                 invoice = Invoice.objects.create(
#                     user=request.user,
#                     client=client,
#                     invoice_number=invoice_number,
#                     source='voice',  # Mark as voice-generated
#                     issue_date=invoice_data['issue_date'],
#                     due_date=invoice_data['due_date'],
#                     #duration_unit=invoice_data['duration_unit'],
#                     #discount_amount=Decimal(str(invoice_data['discount_amount'])),
#                     #discount_type=invoice_data['discount_type'],
#                     vat_rate=Decimal(str(invoice_data['vat_rate'])),
#                     #service_location=invoice_data.get('service_location', ''),
#                     subtotal=Decimal('0.00'),
#                     total=Decimal('0.00'),
#                     payment_status='unpaid'
#                 )
                
#                 # 5. Create invoice items
#                 for item_dict in items_data:
#                     InvoiceItem.objects.create(
#                         invoice=invoice,
#                         quote_description=item_dict['quote_description'],
#                         # service_type=item_dict['service_type'],
#                         # service_duration=item_dict['service_duration'],
#                         # service_rate=Decimal(str(item_dict['service_rate'])),
#                         quantity=item_dict['quantity'],
#                         unit_price=Decimal(str(item_dict['unit_price'])),
#                         #material_name=item_dict.get('material_name', ''),
#                         #amount=Decimal(str(item_dict['quantity'])) * Decimal(str(item_dict['unit_price']))
#                     )
                
#                 # 6. Calculate totals
#                 invoice.refresh_from_db()
#                 items = invoice.items.all()
#                 #subtotal = sum(item.amount for item in items)
#                 subtotal = sum(i.quantity * i.unit_price for i in items)
                
#                 # Calculate discount
#                 if invoice.discount_type == 'percentage':
#                     discount_value = subtotal * (invoice.discount_amount / Decimal('100'))
#                 else:
#                     discount_value = invoice.discount_amount
                
#                 # Calculate VAT
#                 amount_after_discount = subtotal - discount_value
#                 vat_amount = amount_after_discount * (invoice.vat_rate / Decimal('100'))
#                 total = amount_after_discount + vat_amount
                
#                 invoice.subtotal = subtotal
#                 invoice.total = total
#                 invoice.save(update_fields=['subtotal', 'total'])
                
#                 logger.info(f"Created invoice: {invoice.invoice_number} with {len(items_data)} items")
            
#             # Return response
#             return self.success_response(
#                 data={
#                     'invoice_id': invoice.invoice_id,
#                     'invoice_number': invoice.invoice_number,
#                     'client': {
#                         'id': client.id,
#                         'name': client.name,
#                         'email': client.email,
#                         'phone_number': client.phone_number
#                     },
#                     'transcription': transcription,
#                     'total': str(invoice.total),
#                     'items_count': len(items_data)
#                 },
#                 message="Invoice created successfully from voice",
#                 status_code=status.HTTP_201_CREATED
#             )
        
#         except Exception as e:
#             logger.error(f"Voice invoice creation failed: {e}")
#             return self.error_response(
#                 f"Failed to create invoice: {str(e)}",
#                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )
        
#         finally:
#             # Clean up temp file
#             if temp_file_path and default_storage.exists(temp_file_path):
#                 default_storage.delete(temp_file_path)


# class DocumentQuoteCreateView(StandardResponseMixin, APIView):
#     """
#     AI-powered quote creation from document (image/PDF).
    
#     POST /api/ai/document/quote/
#     Content-Type: multipart/form-data
#     Authorization: Bearer <token>
    
#     Body:
#     - document: Image or PDF file
    
#     Process:
#     1. Extract text from document using GPT-4 Vision/OCR
#     2. Extract client & quote data using GPT-4
#     3. Create new client
#     4. Create quote with items
#     5. Return created quote
#     """
    
#     permission_classes = [IsAuthenticated]
#     parser_classes = [MultiPartParser, FormParser]
    
#     def post(self, request):
#         # Load AI modules
#         ai = get_ai_modules()
#         if not ai['available']:
#             return self.error_response(
#                 f"AI module not available: {ai.get('error', 'Unknown error')}",
#                 status_code=status.HTTP_503_SERVICE_UNAVAILABLE
#             )
        
#         if 'document' not in request.FILES:
#             return self.error_response("Document file is required", status_code=status.HTTP_400_BAD_REQUEST)
        
#         document_file = request.FILES['document']
        
#         # Validate file type
#         allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.gif', '.webp']
#         file_ext = Path(document_file.name).suffix.lower()
#         if file_ext not in allowed_extensions:
#             return self.error_response(
#                 f"Invalid file type. Allowed: {', '.join(allowed_extensions)}",
#                 status_code=status.HTTP_400_BAD_REQUEST
#             )
        
#         temp_file_path = None
        
#         try:
#             # Save document file temporarily
#             temp_file_path = default_storage.save(f'temp/documents/{document_file.name}', document_file)
#             full_path = default_storage.path(temp_file_path)
            
#             logger.info(f"Processing document quote for user {request.user.id}")
            
#             # Process document with AI
#             result = ai['process_document_file'](full_path, document_type="quote")
            
#             if not result['success']:
#                 return self.error_response(
#                     f"AI processing failed: {result.get('error')}",
#                     status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
#                 )
            
#             extracted_data = result['extracted_data']
#             extracted_text = result['extracted_text']
            
#             # Validate extracted data
#             validation = ai['validate_extracted_data'](extracted_data, document_type="quote")
#             if not validation['valid']:
#                 return self.error_response(
#                     "Extracted data is incomplete",
#                     status_code=status.HTTP_400_BAD_REQUEST,
#                     data={'errors': validation['errors'], 'extracted_text': extracted_text[:500]}
#                 )
            
#             # Create client and quote (same logic as voice)
#             with transaction.atomic():
#                 # Create client
#                 client_data = ai['format_client_data_for_backend'](extracted_data)
#                 client_data['user'] = request.user
#                 client_data['source'] = 'manual'
                
#                 client = Client.objects.create(**client_data)
                
#                 # Create folder for client
#                 ensure_client_folder(request.user, client)
                
#                 # Format and create quote
#                 quote_data = ai['format_quote_data_for_backend'](extracted_data, client.id, str(request.user.id))
                
#                 year = timezone.now().year
#                 counter_obj, created = QuoteCounter.objects.select_for_update().get_or_create(
#                     user=request.user, year=year
#                 )
#                 counter_obj.counter += 1
#                 counter_obj.save()
                
#                 short_uid = str(request.user.id)[:4]
#                 quote_number = f"QT-{short_uid}-{year}-{counter_obj.counter:02d}"
                
#                 items_data = quote_data.pop('items')
                
#                 quote = Quote.objects.create(
#                     user=request.user,
#                     client=client,
#                     quote_number=quote_number,
#                     source='manual',  # Document upload
#                     issue_date=quote_data['issue_date'],
#                     due_date=quote_data['due_date'],
#                     # duration_unit=quote_data['duration_unit'],
#                     # discount_amount=Decimal(str(quote_data['discount_amount'])),
#                     # discount_type=quote_data['discount_type'],
#                     vat_rate=Decimal(str(quote_data['vat_rate'])),
#                     #service_location=quote_data.get('service_location', ''),
#                     subtotal=Decimal('0.00'),
#                     total=Decimal('0.00'),
#                     quote_status='draft'
#                 )
                
#                 # Create items
#                 for item_dict in items_data:
#                     QuoteItem.objects.create(
#                         quote=quote,
#                         quote_description=item_dict['quote_description'],
#                         # service_type=item_dict['service_type'],
#                         # service_duration=item_dict['service_duration'],
#                         # service_rate=Decimal(str(item_dict['service_rate'])),
#                         quantity=item_dict['quantity'],
#                         unit_price=Decimal(str(item_dict['unit_price'])),
#                         #material_name=item_dict.get('material_name', ''),
#                         #amount=Decimal(str(item_dict['quantity'])) * Decimal(str(item_dict['unit_price']))
#                     )
                
#                 # Calculate totals
#                 quote.refresh_from_db()
#                 items = quote.items.all()
#                 #subtotal = sum(item.amount for item in items)
#                 subtotal = sum(i.quantity * i.unit_price for i in items)
                
#                 if quote.discount_type == 'percentage':
#                     discount_value = subtotal * (quote.discount_amount / Decimal('100'))
#                 else:
#                     discount_value = quote.discount_amount
                
#                 amount_after_discount = subtotal - discount_value
#                 vat_amount = amount_after_discount * (quote.vat_rate / Decimal('100'))
#                 total = amount_after_discount + vat_amount
                
#                 quote.subtotal = subtotal
#                 quote.total = total
#                 quote.save(update_fields=['subtotal', 'total'])
                
#                 logger.info(f"Created quote from document: {quote.quote_number}")
            
#             return self.success_response(
#                 data={
#                     'quote_id': quote.quote_id,
#                     'quote_number': quote.quote_number,
#                     'client': {
#                         'id': client.id,
#                         'name': client.name,
#                         'email': client.email,
#                         'phone_number': client.phone_number
#                     },
#                     'total': str(quote.total),
#                     'items_count': len(items_data)
#                 },
#                 message="Quote created successfully from document",
#                 status_code=status.HTTP_201_CREATED
#             )
        
#         except Exception as e:
#             logger.error(f"Document quote creation failed: {e}")
#             return self.error_response(
#                 f"Failed to create quote: {str(e)}",
#                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )
        
#         finally:
#             if temp_file_path and default_storage.exists(temp_file_path):
#                 default_storage.delete(temp_file_path)


# class DocumentInvoiceCreateView(StandardResponseMixin, APIView):
#     """
#     AI-powered invoice creation from document (image/PDF).
    
#     POST /api/ai/document/invoice/
    
#     Same as DocumentQuoteCreateView but creates Invoice
#     """
    
#     permission_classes = [IsAuthenticated]
#     parser_classes = [MultiPartParser, FormParser]
    
#     def post(self, request):
#         # Load AI modules
#         ai = get_ai_modules()
#         if not ai['available']:
#             return self.error_response(
#                 f"AI module not available: {ai.get('error', 'Unknown error')}",
#                 status_code=status.HTTP_503_SERVICE_UNAVAILABLE
#             )
        
#         if 'document' not in request.FILES:
#             return self.error_response("Document file is required", status_code=status.HTTP_400_BAD_REQUEST)
        
#         document_file = request.FILES['document']
        
#         # Validate file type
#         allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.gif', '.webp']
#         file_ext = Path(document_file.name).suffix.lower()
#         if file_ext not in allowed_extensions:
#             return self.error_response(
#                 f"Invalid file type. Allowed: {', '.join(allowed_extensions)}",
#                 status_code=status.HTTP_400_BAD_REQUEST
#             )
        
#         temp_file_path = None
        
#         try:
#             # Save document file temporarily
#             temp_file_path = default_storage.save(f'temp/documents/{document_file.name}', document_file)
#             full_path = default_storage.path(temp_file_path)
            
#             logger.info(f"Processing document invoice for user {request.user.id}")
            
#             # Process document with AI
#             result = ai['process_document_file'](full_path, document_type="invoice")
            
#             if not result['success']:
#                 return self.error_response(
#                     f"AI processing failed: {result.get('error')}",
#                     status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
#                 )
            
#             extracted_data = result['extracted_data']
#             extracted_text = result['extracted_text']
            
#             # Validate extracted data
#             validation = ai['validate_extracted_data'](extracted_data, document_type="invoice")
#             if not validation['valid']:
#                 return self.error_response(
#                     "Extracted data is incomplete",
#                     status_code=status.HTTP_400_BAD_REQUEST,
#                     data={'errors': validation['errors'], 'extracted_text': extracted_text[:500]}
#                 )
            
#             # Create client and invoice
#             with transaction.atomic():
#                 # Create client
#                 client_data = ai['format_client_data_for_backend'](extracted_data)
#                 client_data['user'] = request.user
#                 client_data['source'] = 'manual'
                
#                 client = Client.objects.create(**client_data)
                
#                 # Create folder for client
#                 ensure_client_folder(request.user, client)
                
#                 # Format and create invoice
#                 invoice_data = ai['format_invoice_data_for_backend'](extracted_data, client.id, str(request.user.id))
                
#                 year = timezone.now().year
#                 counter_obj, created = InvoiceCounter.objects.select_for_update().get_or_create(
#                     user=request.user, year=year
#                 )
#                 counter_obj.counter += 1
#                 counter_obj.save()
                
#                 short_uid = str(request.user.id)[:4]
#                 invoice_number = f"INV-{short_uid}-{year}-{counter_obj.counter:02d}"
                
#                 items_data = invoice_data.pop('items')
                
#                 invoice = Invoice.objects.create(
#                     user=request.user,
#                     client=client,
#                     invoice_number=invoice_number,
#                     source='manual',  # Document upload
#                     issue_date=invoice_data['issue_date'],
#                     due_date=invoice_data['due_date'],
#                     #duration_unit=invoice_data['duration_unit'],
#                     #discount_amount=Decimal(str(invoice_data['discount_amount'])),
#                     #discount_type=invoice_data['discount_type'],
#                     vat_rate=Decimal(str(invoice_data['vat_rate'])),
#                     #service_location=invoice_data.get('service_location', ''),
#                     subtotal=Decimal('0.00'),
#                     total=Decimal('0.00'),
#                     payment_status='unpaid'
#                 )
                
#                 # Create items
#                 for item_dict in items_data:
#                     InvoiceItem.objects.create(
#                         invoice=invoice,
#                         quote_description=item_dict['quote_description'],
#                         # service_type=item_dict['service_type'],
#                         # service_duration=item_dict['service_duration'],
#                         # service_rate=Decimal(str(item_dict['service_rate'])),
#                         quantity=item_dict['quantity'],
#                         unit_price=Decimal(str(item_dict['unit_price'])),
#                         #material_name=item_dict.get('material_name', ''),
#                         #amount=Decimal(str(item_dict['quantity'])) * Decimal(str(item_dict['unit_price']))
#                     )
                
#                 # Calculate totals
#                 invoice.refresh_from_db()
#                 items = invoice.items.all()
#                 #subtotal = sum(item.amount for item in items)
#                 subtotal = sum(i.quantity * i.unit_price for i in items)
                
#                 if invoice.discount_type == 'percentage':
#                     discount_value = subtotal * (invoice.discount_amount / Decimal('100'))
#                 else:
#                     discount_value = invoice.discount_amount
                
#                 amount_after_discount = subtotal - discount_value
#                 vat_amount = amount_after_discount * (invoice.vat_rate / Decimal('100'))
#                 total = amount_after_discount + vat_amount
                
#                 invoice.subtotal = subtotal
#                 invoice.total = total
#                 invoice.save(update_fields=['subtotal', 'total'])
                
#                 logger.info(f"Created invoice from document: {invoice.invoice_number}")
            
#             return self.success_response(
#                 data={
#                     'invoice_id': invoice.invoice_id,
#                     'invoice_number': invoice.invoice_number,
#                     'client': {
#                         'id': client.id,
#                         'name': client.name,
#                         'email': client.email,
#                         'phone_number': client.phone_number
#                     },
#                     'total': str(invoice.total),
#                     'items_count': len(items_data)
#                 },
#                 message="Invoice created successfully from document",
#                 status_code=status.HTTP_201_CREATED
#             )
        
#         except Exception as e:
#             logger.error(f"Document invoice creation failed: {e}")
#             return self.error_response(
#                 f"Failed to create invoice: {str(e)}",
#                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )
        
#         finally:
#             if temp_file_path and default_storage.exists(temp_file_path):
#                 default_storage.delete(temp_file_path)


# class AIChatQueryView(StandardResponseMixin, APIView):
#     """
#     AI-powered natural language query for reports and data analysis.
    
#     POST /api/ai/chat/
#     Content-Type: application/json
#     Authorization: Bearer <token>
    
#     Body:
#     {
#         "question": "How many invoices did I send this month?"
#     }
    
#     Returns:
#     - SQL query (for debugging)
#     - Query results
#     - Natural language answer
#     """
    
#     permission_classes = [IsAuthenticated]
    
#     def post(self, request):
#         # Load AI modules
#         ai = get_ai_modules()
#         if not ai['available']:
#             return self.error_response(
#                 f"AI module not available: {ai.get('error', 'Unknown error')}",
#                 status_code=status.HTTP_503_SERVICE_UNAVAILABLE
#             )
        
#         question = request.data.get('question')
        
#         if not question:
#             return self.error_response(
#                 "Question is required",
#                 status_code=status.HTTP_400_BAD_REQUEST
#             )
        
#         try:
#             logger.info(f"AI chat query for user {request.user.id}: {question}")
            
#             # Query with AI
#             result = ai['natural_language_query'](
#                 user_id=str(request.user.id),
#                 question=question
#             )
            
#             if not result['success']:
#                 return self.error_response(
#                     f"Query failed: {result.get('error')}",
#                     status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
#                 )
            
#             return self.success_response(
#                 data={
#                     'question': question,
#                     'answer': result['answer'],
#                     'sql_query': result.get('sql_query'),
#                     'result_data': result.get('result')
#                 },
#                 message="Query processed successfully"
#             )
        
#         except Exception as e:
#             logger.error(f"AI chat query failed: {e}")
#             return self.error_response(
#                 f"Failed to process query: {str(e)}",
#                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )
"""
AI-powered views for Fixxa Backend
===================================
Voice and Document processing for automatic Quote/Invoice generation
"""

import sys
import os
from pathlib import Path
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone
import logging
import json

# Import Django models
from clientapp.models import Client
from quoteapp.models import Quote, QuoteItem, Invoice, InvoiceItem, QuoteCounter, InvoiceCounter,QuoteToken
from quoteapp.views import ensure_client_folder
from quoteapp.serializers import QuoteListRetrieveSerializer, NewInvoiceResponseSerializer
from decimal import Decimal
from utils.payment import create_stripe_payment_link
from datetime import timedelta
from django.conf import settings

logger = logging.getLogger(__name__)

# Lazy import function for AI modules (to avoid slow startup)
def get_ai_modules():
    """Import AI modules only when needed"""
    FIXXA_AI_PATH = Path(__file__).parent.parent / 'fixxa_AI'
    if str(FIXXA_AI_PATH) not in sys.path:
        sys.path.insert(0, str(FIXXA_AI_PATH))
    
    try:
        from fixxa_ai import (
            process_audio_from_file,
            process_document_file,
            natural_language_query
        )
        from fixxa_ai.data_formatter import (
            format_client_data_for_backend,
            format_quote_data_for_backend,
            format_invoice_data_for_backend,
            validate_extracted_data
        )
        return {
            'process_audio_from_file': process_audio_from_file,
            'process_document_file': process_document_file,
            'natural_language_query': natural_language_query,
            'format_client_data_for_backend': format_client_data_for_backend,
            'format_quote_data_for_backend': format_quote_data_for_backend,
            'format_invoice_data_for_backend': format_invoice_data_for_backend,
            'validate_extracted_data': validate_extracted_data,
            'available': True
        }
    except ImportError as e:
        logger.warning(f"AI modules not available: {e}")
        return {'available': False, 'error': str(e)}


class StandardResponseMixin:
    """Mixin for consistent API responses"""

    def success_response(self, data, message="Success", status_code=200):
        return Response({
            "success": True,
            "statusCode": status_code,
            "message": message,
            "data": data,
            "timestamp": timezone.now().isoformat()
        }, status=status_code)

    def error_response(self, message, status_code=400, data=None):
        return Response({
            "success": False,
            "statusCode": status_code,
            "message": message,
            "data": data,
            "timestamp": timezone.now().isoformat()
        }, status=status_code)


class VoiceQuoteCreateView(StandardResponseMixin, APIView):
    """
    AI-powered quote creation from voice note.
    
    POST /api/ai/voice/quote/
    Content-Type: multipart/form-data
    Authorization: Bearer <token>
    
    Body:
    - audio: Audio file (mp3, wav, m4a, ogg, webm)
    
    Process:
    1. Transcribe audio using Whisper
    2. Extract client & quote data using GPT-4
    3. Create new client
    4. Create quote with items
    5. Return created quote
    """
    
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request):
        # Load AI modules
        ai = get_ai_modules()
        if not ai['available']:
            return self.error_response(
                f"AI module not available: {ai.get('error', 'Unknown error')}",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        # ✅ Validate client_id from request
        client_id = request.data.get('client_id')
        if not client_id:
            return self.error_response("client_id is required", status_code=status.HTTP_400_BAD_REQUEST)
        
        try:
            client = Client.objects.get(id=client_id, user=request.user)
        except Client.DoesNotExist:
            return self.error_response("Client not found", status_code=status.HTTP_404_NOT_FOUND)
        
        # Validate audio file
        if 'audio' not in request.FILES:
            return self.error_response("Audio file is required", status_code=status.HTTP_400_BAD_REQUEST)
        
        audio_file = request.FILES['audio']
        
        # Validate file type
        allowed_extensions = ['.mp3', '.wav', '.m4a', '.ogg', '.webm']
        file_ext = Path(audio_file.name).suffix.lower()
        if file_ext not in allowed_extensions:
            return self.error_response(
                f"Invalid file type. Allowed: {', '.join(allowed_extensions)}",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        temp_file_path = None
        
        try:
            # Save audio file temporarily
            temp_file_path = default_storage.save(f'temp/audio/{audio_file.name}', audio_file)
            full_path = default_storage.path(temp_file_path)
            
            logger.info(f"Processing voice quote for user {request.user.id}")
            
            # Process audio with AI
            result = ai['process_audio_from_file'](full_path, document_type="quote")
            
            if not result['success']:
                return self.error_response(
                    f"AI processing failed: {result.get('error')}",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            extracted_data = result['extracted_data']
            transcription = result['transcription']
            
            # Validate extracted data
            validation = ai['validate_extracted_data'](extracted_data, document_type="quote")
            if not validation['valid']:
                return self.error_response(
                    "Extracted data is incomplete",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    data={'errors': validation['errors'], 'transcription': transcription}
                )
            
            # Create client and quote in transaction
            with transaction.atomic():
                # 1. Create new client
                '''
                client_data = ai['format_client_data_for_backend'](extracted_data)
                client_data['user'] = request.user
                client_data['source'] = 'manual'  # Coming from voice
                
                client = Client.objects.create(**client_data)
                logger.info(f"Created client: {client.name} (ID: {client.id})")
                
                # 1b. Create folder for client
                ensure_client_folder(request.user, client)
                '''
                folder = ensure_client_folder(request.user, client)
                
                # 2. Format quote data
                quote_data = ai['format_quote_data_for_backend'](extracted_data, client.id, str(request.user.id))
                
                # 3. Generate quote number
                year = timezone.now().year
                counter_obj, created = QuoteCounter.objects.select_for_update().get_or_create(
                    user=request.user,
                    year=year
                )
                counter_obj.counter += 1
                counter_obj.save()
                
                short_uid = str(request.user.id)[:4]
                quote_number = f"QT-{short_uid}-{year}-{counter_obj.counter:02d}"
                
                # 4. Create quote
                items_data = quote_data.pop('items')
                
                quote = Quote.objects.create(
                    user=request.user,
                    client=client,
                    folder=folder,  # ✅ assign folder
                    quote_number=quote_number,
                    source='voice',  # Mark as voice-generated
                    issue_date=quote_data['issue_date'],
                    due_date=quote_data['due_date'],
                    #duration_unit=quote_data['duration_unit'],
                    #discount_amount=Decimal(str(quote_data['discount_amount'])),
                    #discount_type=quote_data['discount_type'],
                    vat_rate=Decimal(str(quote_data['vat_rate'])),
                    #service_location=quote_data.get('service_location', ''),
                    subtotal=Decimal('0.00'),
                    total=Decimal('0.00'),
                    quote_status='draft'
                )
                
                # 5. Create quote items
                for item_dict in items_data:
                    QuoteItem.objects.create(
                        quote=quote,
                        quote_description=item_dict['quote_description'],
                        # service_type=item_dict['service_type'],
                        # service_duration=item_dict['service_duration'],
                        # service_rate=Decimal(str(item_dict['service_rate'])),
                        quantity=item_dict['quantity'],
                        unit_price=Decimal(str(item_dict['unit_price'])),
                        #material_name=item_dict.get('material_name', ''),
                        #amount=Decimal(str(item_dict['quantity'])) * Decimal(str(item_dict['unit_price']))
                    )
                
                # 6. Calculate totals
                quote.refresh_from_db()
                items = quote.items.all()
                #subtotal = sum(item.amount for item in items)
                subtotal = sum(i.quantity * i.unit_price for i in items)
                
                # Calculate discount
                if quote.discount_type == 'percentage':
                    discount_value = subtotal * (quote.discount_amount / Decimal('100'))
                else:
                    discount_value = quote.discount_amount
                
                # Calculate VAT
                amount_after_discount = subtotal - discount_value
                vat_amount = amount_after_discount * (quote.vat_rate / Decimal('100'))
                total = amount_after_discount + vat_amount
                
                quote.subtotal = subtotal
                quote.total = total
                quote.save(update_fields=['subtotal', 'total'])
    
               # ✅ Generate accept/reject links with token (same as manual)
                quote_token = QuoteToken.objects.create(
                    quote=quote,
                    expires_at=timezone.now() + timedelta(days=30)
                )
                quote.accept_link = f"{settings.BASE_URL}/quoteapp/quotes/{quote.quote_id}/accept/?token={quote_token.token}"
                quote.reject_link = f"{settings.BASE_URL}/quoteapp/quotes/{quote.quote_id}/reject/?token={quote_token.token}"
                quote.save(update_fields=['accept_link', 'reject_link'])

                logger.info(f"Created quote: {quote.quote_number} with {len(items_data)} items")
            
            # Serialize response using proper format
            from rest_framework.request import Request
            from django.test.client import RequestFactory
            factory = RequestFactory()
            django_request = factory.get('/')
            django_request.user = request.user
            drf_request = Request(django_request)
            
            serializer = QuoteListRetrieveSerializer(quote, context={'request': drf_request})
            response_data = serializer.data
            response_data['transcription'] = transcription
            
            # Return response
            return self.success_response(
                data=response_data,
                message="Quote created successfully from voice",
                status_code=status.HTTP_201_CREATED
            )
        
        except Exception as e:
            logger.error(f"Voice quote creation failed: {e}")
            return self.error_response(
                f"Failed to create quote: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        finally:
            # Clean up temp file
            if temp_file_path and default_storage.exists(temp_file_path):
                default_storage.delete(temp_file_path)


class VoiceInvoiceCreateView(StandardResponseMixin, APIView):
    """
    AI-powered invoice creation from voice note.
    
    POST /api/ai/voice/invoice/
    Content-Type: multipart/form-data
    Authorization: Bearer <token>
    
    Body:
    - audio: Audio file (mp3, wav, m4a, ogg, webm)
    
    Process: Same as VoiceQuoteCreateView but creates Invoice
    """
    
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request):
        # Load AI modules
        ai = get_ai_modules()
        if not ai['available']:
            return self.error_response(
                f"AI module not available: {ai.get('error', 'Unknown error')}",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        # ✅ Validate client_id from request
        client_id = request.data.get('client_id')
        if not client_id:
            return self.error_response("client_id is required", status_code=status.HTTP_400_BAD_REQUEST)
        
        try:
            client = Client.objects.get(id=client_id, user=request.user)
        except Client.DoesNotExist:
            return self.error_response("Client not found", status_code=status.HTTP_404_NOT_FOUND)
        
        if 'audio' not in request.FILES:
            return self.error_response("Audio file is required", status_code=status.HTTP_400_BAD_REQUEST)
        
        audio_file = request.FILES['audio']
        
        # Validate file type
        allowed_extensions = ['.mp3', '.wav', '.m4a', '.ogg', '.webm']
        file_ext = Path(audio_file.name).suffix.lower()
        if file_ext not in allowed_extensions:
            return self.error_response(
                f"Invalid file type. Allowed: {', '.join(allowed_extensions)}",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        temp_file_path = None
        
        try:
            # Save audio file temporarily
            temp_file_path = default_storage.save(f'temp/audio/{audio_file.name}', audio_file)
            full_path = default_storage.path(temp_file_path)
            
            logger.info(f"Processing voice invoice for user {request.user.id}")
            
            # Process audio with AI
            result = ai['process_audio_from_file'](full_path, document_type="invoice")
            
            if not result['success']:
                return self.error_response(
                    f"AI processing failed: {result.get('error')}",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            extracted_data = result['extracted_data']
            transcription = result['transcription']
            
            # Validate extracted data
            validation = ai['validate_extracted_data'](extracted_data, document_type="invoice")
            if not validation['valid']:
                return self.error_response(
                    "Extracted data is incomplete",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    data={'errors': validation['errors'], 'transcription': transcription}
                )
            
            # Create client and invoice in transaction
            with transaction.atomic():
                # 1. Create new client
                '''
                client_data = ai['format_client_data_for_backend'](extracted_data)
                client_data['user'] = request.user
                client_data['source'] = 'manual'
                
                client = Client.objects.create(**client_data)
                logger.info(f"Created client: {client.name} (ID: {client.id})")
                '''

                 # ✅ REMOVED: client creation - use existing client
                folder = ensure_client_folder(request.user, client)
                # 1b. Create folder for client
                #ensure_client_folder(request.user, client)
                
                # 2. Format invoice data
                invoice_data = ai['format_invoice_data_for_backend'](extracted_data, client.id, str(request.user.id))
                
                # 3. Generate invoice number
                year = timezone.now().year
                counter_obj, created = InvoiceCounter.objects.select_for_update().get_or_create(
                    user=request.user,
                    year=year
                )
                counter_obj.counter += 1
                counter_obj.save()
                
                short_uid = str(request.user.id)[:4]
                invoice_number = f"INV-{short_uid}-{year}-{counter_obj.counter:02d}"
                
                # 4. Create invoice
                items_data = invoice_data.pop('items')
                
                invoice = Invoice.objects.create(
                    user=request.user,
                    client=client,
                    folder=folder,  # ✅ assign folder
                    invoice_number=invoice_number,
                    source='voice',  # Mark as voice-generated
                    issue_date=invoice_data['issue_date'],
                    due_date=invoice_data['due_date'],
                    #duration_unit=invoice_data['duration_unit'],
                    #discount_amount=Decimal(str(invoice_data['discount_amount'])),
                    #discount_type=invoice_data['discount_type'],
                    vat_rate=Decimal(str(invoice_data['vat_rate'])),
                    #service_location=invoice_data.get('service_location', ''),
                    subtotal=Decimal('0.00'),
                    total=Decimal('0.00'),
                    payment_status='unpaid'
                )
                
                # 5. Create invoice items
                for item_dict in items_data:
                    InvoiceItem.objects.create(
                        invoice=invoice,
                        quote_description=item_dict['quote_description'],
                        # service_type=item_dict['service_type'],
                        # service_duration=item_dict['service_duration'],
                        # service_rate=Decimal(str(item_dict['service_rate'])),
                        quantity=item_dict['quantity'],
                        unit_price=Decimal(str(item_dict['unit_price'])),
                        #material_name=item_dict.get('material_name', ''),
                        #amount=Decimal(str(item_dict['quantity'])) * Decimal(str(item_dict['unit_price']))
                    )
                
                # 6. Calculate totals
                invoice.refresh_from_db()
                items = invoice.items.all()
                #subtotal = sum(item.amount for item in items)
                subtotal = sum(i.quantity * i.unit_price for i in items)
                
                # Calculate discount
                if invoice.discount_type == 'percentage':
                    discount_value = subtotal * (invoice.discount_amount / Decimal('100'))
                else:
                    discount_value = invoice.discount_amount
                
                # Calculate VAT
                amount_after_discount = subtotal - discount_value
                vat_amount = amount_after_discount * (invoice.vat_rate / Decimal('100'))
                total = amount_after_discount + vat_amount
                
                invoice.subtotal = subtotal
                invoice.total = total
                invoice.save(update_fields=['subtotal', 'total'])
                

                # ✅ Generate payment link (same as manual)
                payment_link = create_stripe_payment_link(invoice)
                if payment_link:
                    invoice.payment_link = payment_link
                    invoice.save(update_fields=['payment_link'])


                logger.info(f"Created invoice: {invoice.invoice_number} with {len(items_data)} items")
            
            # Serialize response using proper format
            from rest_framework.request import Request
            from django.test.client import RequestFactory
            factory = RequestFactory()
            django_request = factory.get('/')
            django_request.user = request.user
            drf_request = Request(django_request)
            
            serializer = NewInvoiceResponseSerializer(invoice, context={'request': drf_request})
            response_data = serializer.data
            response_data['transcription'] = transcription
            
            # Return response
            return self.success_response(
                data=response_data,
                message="Invoice created successfully from voice",
                status_code=status.HTTP_201_CREATED
            )
        
        except Exception as e:
            logger.error(f"Voice invoice creation failed: {e}")
            return self.error_response(
                f"Failed to create invoice: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        finally:
            # Clean up temp file
            if temp_file_path and default_storage.exists(temp_file_path):
                default_storage.delete(temp_file_path)


class DocumentQuoteCreateView(StandardResponseMixin, APIView):
    """
    AI-powered quote creation from document (image/PDF).
    
    POST /api/ai/document/quote/
    Content-Type: multipart/form-data
    Authorization: Bearer <token>
    
    Body:
    - document: Image or PDF file
    
    Process:
    1. Extract text from document using GPT-4 Vision/OCR
    2. Extract client & quote data using GPT-4
    3. Create new client
    4. Create quote with items
    5. Return created quote
    """
    
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request):
        # Load AI modules
        ai = get_ai_modules()
        if not ai['available']:
            return self.error_response(
                f"AI module not available: {ai.get('error', 'Unknown error')}",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        if 'document' not in request.FILES:
            return self.error_response("Document file is required", status_code=status.HTTP_400_BAD_REQUEST)
        
        document_file = request.FILES['document']
        
        # Validate file type
        allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.gif', '.webp']
        file_ext = Path(document_file.name).suffix.lower()
        if file_ext not in allowed_extensions:
            return self.error_response(
                f"Invalid file type. Allowed: {', '.join(allowed_extensions)}",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        temp_file_path = None
        
        try:
            # Save document file temporarily
            temp_file_path = default_storage.save(f'temp/documents/{document_file.name}', document_file)
            full_path = default_storage.path(temp_file_path)
            
            logger.info(f"Processing document quote for user {request.user.id}")
            
            # Process document with AI
            result = ai['process_document_file'](full_path, document_type="quote")
            
            if not result['success']:
                return self.error_response(
                    f"AI processing failed: {result.get('error')}",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            extracted_data = result['extracted_data']
            extracted_text = result['extracted_text']
            
            # Validate extracted data
            validation = ai['validate_extracted_data'](extracted_data, document_type="quote")
            if not validation['valid']:
                return self.error_response(
                    "Extracted data is incomplete",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    data={'errors': validation['errors'], 'extracted_text': extracted_text[:500]}
                )
            
            # Create client and quote (same logic as voice)
            with transaction.atomic():
                # Create client
                client_data = ai['format_client_data_for_backend'](extracted_data)
                client_data['user'] = request.user
                client_data['source'] = 'manual'
                
                client = Client.objects.create(**client_data)
                
                # Create folder for client
                ensure_client_folder(request.user, client)
                
                # Format and create quote
                quote_data = ai['format_quote_data_for_backend'](extracted_data, client.id, str(request.user.id))
                
                year = timezone.now().year
                counter_obj, created = QuoteCounter.objects.select_for_update().get_or_create(
                    user=request.user, year=year
                )
                counter_obj.counter += 1
                counter_obj.save()
                
                short_uid = str(request.user.id)[:4]
                quote_number = f"QT-{short_uid}-{year}-{counter_obj.counter:02d}"
                
                items_data = quote_data.pop('items')
                
                quote = Quote.objects.create(
                    user=request.user,
                    client=client,
                    quote_number=quote_number,
                    source='manual',  # Document upload
                    issue_date=quote_data['issue_date'],
                    due_date=quote_data['due_date'],
                    # duration_unit=quote_data['duration_unit'],
                    # discount_amount=Decimal(str(quote_data['discount_amount'])),
                    # discount_type=quote_data['discount_type'],
                    vat_rate=Decimal(str(quote_data['vat_rate'])),
                    #service_location=quote_data.get('service_location', ''),
                    subtotal=Decimal('0.00'),
                    total=Decimal('0.00'),
                    quote_status='draft'
                )
                
                # Create items
                for item_dict in items_data:
                    QuoteItem.objects.create(
                        quote=quote,
                        quote_description=item_dict['quote_description'],
                        # service_type=item_dict['service_type'],
                        # service_duration=item_dict['service_duration'],
                        # service_rate=Decimal(str(item_dict['service_rate'])),
                        quantity=item_dict['quantity'],
                        unit_price=Decimal(str(item_dict['unit_price'])),
                        #material_name=item_dict.get('material_name', ''),
                        #amount=Decimal(str(item_dict['quantity'])) * Decimal(str(item_dict['unit_price']))
                    )
                
                # Calculate totals
                quote.refresh_from_db()
                items = quote.items.all()
                #subtotal = sum(item.amount for item in items)
                subtotal = sum(i.quantity * i.unit_price for i in items)
                
                if quote.discount_type == 'percentage':
                    discount_value = subtotal * (quote.discount_amount / Decimal('100'))
                else:
                    discount_value = quote.discount_amount
                
                amount_after_discount = subtotal - discount_value
                vat_amount = amount_after_discount * (quote.vat_rate / Decimal('100'))
                total = amount_after_discount + vat_amount
                
                quote.subtotal = subtotal
                quote.total = total
                quote.save(update_fields=['subtotal', 'total'])

                # ✅ Generate accept/reject links with token
                quote_token = QuoteToken.objects.create(
                    quote=quote,
                    expires_at=timezone.now() + timedelta(days=30)
                )
                quote.accept_link = f"{settings.BASE_URL}/quoteapp/quotes/{quote.quote_id}/accept/?token={quote_token.token}"
                quote.reject_link = f"{settings.BASE_URL}/quoteapp/quotes/{quote.quote_id}/reject/?token={quote_token.token}"
                quote.save(update_fields=['accept_link', 'reject_link'])

                logger.info(f"Created quote from document: {quote.quote_number}")
            
            # Serialize response using proper format
            from rest_framework.request import Request
            from django.test.client import RequestFactory
            factory = RequestFactory()
            django_request = factory.get('/')
            django_request.user = request.user
            drf_request = Request(django_request)
            
            serializer = QuoteListRetrieveSerializer(quote, context={'request': drf_request})
            
            return self.success_response(
                data=serializer.data,
                message="Quote created successfully from document",
                status_code=status.HTTP_201_CREATED
            )
        
        except Exception as e:
            logger.error(f"Document quote creation failed: {e}")
            return self.error_response(
                f"Failed to create quote: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        finally:
            if temp_file_path and default_storage.exists(temp_file_path):
                default_storage.delete(temp_file_path)


class DocumentInvoiceCreateView(StandardResponseMixin, APIView):
    """
    AI-powered invoice creation from document (image/PDF).
    
    POST /api/ai/document/invoice/
    
    Same as DocumentQuoteCreateView but creates Invoice
    """
    
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request):
        # Load AI modules
        ai = get_ai_modules()
        if not ai['available']:
            return self.error_response(
                f"AI module not available: {ai.get('error', 'Unknown error')}",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        if 'document' not in request.FILES:
            return self.error_response("Document file is required", status_code=status.HTTP_400_BAD_REQUEST)
        
        document_file = request.FILES['document']
        
        # Validate file type
        allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.gif', '.webp']
        file_ext = Path(document_file.name).suffix.lower()
        if file_ext not in allowed_extensions:
            return self.error_response(
                f"Invalid file type. Allowed: {', '.join(allowed_extensions)}",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        temp_file_path = None
        
        try:
            # Save document file temporarily
            temp_file_path = default_storage.save(f'temp/documents/{document_file.name}', document_file)
            full_path = default_storage.path(temp_file_path)
            
            logger.info(f"Processing document invoice for user {request.user.id}")
            
            # Process document with AI
            result = ai['process_document_file'](full_path, document_type="invoice")
            
            if not result['success']:
                return self.error_response(
                    f"AI processing failed: {result.get('error')}",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            extracted_data = result['extracted_data']
            extracted_text = result['extracted_text']
            
            # Validate extracted data
            validation = ai['validate_extracted_data'](extracted_data, document_type="invoice")
            if not validation['valid']:
                return self.error_response(
                    "Extracted data is incomplete",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    data={'errors': validation['errors'], 'extracted_text': extracted_text[:500]}
                )
            
            # Create client and invoice
            with transaction.atomic():
                # Create client
                client_data = ai['format_client_data_for_backend'](extracted_data)
                client_data['user'] = request.user
                client_data['source'] = 'manual'
                
                client = Client.objects.create(**client_data)
                
                # Create folder for client
                ensure_client_folder(request.user, client)
                
                # Format and create invoice
                invoice_data = ai['format_invoice_data_for_backend'](extracted_data, client.id, str(request.user.id))
                
                year = timezone.now().year
                counter_obj, created = InvoiceCounter.objects.select_for_update().get_or_create(
                    user=request.user, year=year
                )
                counter_obj.counter += 1
                counter_obj.save()
                
                short_uid = str(request.user.id)[:4]
                invoice_number = f"INV-{short_uid}-{year}-{counter_obj.counter:02d}"
                
                items_data = invoice_data.pop('items')
                
                invoice = Invoice.objects.create(
                    user=request.user,
                    client=client,
                    invoice_number=invoice_number,
                    source='manual',  # Document upload
                    issue_date=invoice_data['issue_date'],
                    due_date=invoice_data['due_date'],
                    #duration_unit=invoice_data['duration_unit'],
                    #discount_amount=Decimal(str(invoice_data['discount_amount'])),
                    #discount_type=invoice_data['discount_type'],
                    vat_rate=Decimal(str(invoice_data['vat_rate'])),
                    #service_location=invoice_data.get('service_location', ''),
                    subtotal=Decimal('0.00'),
                    total=Decimal('0.00'),
                    payment_status='unpaid'
                )
                
                # Create items
                for item_dict in items_data:
                    InvoiceItem.objects.create(
                        invoice=invoice,
                        quote_description=item_dict['quote_description'],
                        # service_type=item_dict['service_type'],
                        # service_duration=item_dict['service_duration'],
                        # service_rate=Decimal(str(item_dict['service_rate'])),
                        quantity=item_dict['quantity'],
                        unit_price=Decimal(str(item_dict['unit_price'])),
                        #material_name=item_dict.get('material_name', ''),
                        #amount=Decimal(str(item_dict['quantity'])) * Decimal(str(item_dict['unit_price']))
                    )
                
                # Calculate totals
                invoice.refresh_from_db()
                items = invoice.items.all()
                #subtotal = sum(item.amount for item in items)
                subtotal = sum(i.quantity * i.unit_price for i in items)
                
                if invoice.discount_type == 'percentage':
                    discount_value = subtotal * (invoice.discount_amount / Decimal('100'))
                else:
                    discount_value = invoice.discount_amount
                
                amount_after_discount = subtotal - discount_value
                vat_amount = amount_after_discount * (invoice.vat_rate / Decimal('100'))
                total = amount_after_discount + vat_amount
                
                invoice.subtotal = subtotal
                invoice.total = total
                invoice.save(update_fields=['subtotal', 'total'])
                

                # ✅ Generate payment link
                payment_link = create_stripe_payment_link(invoice)
                if payment_link:
                    invoice.payment_link = payment_link
                    invoice.save(update_fields=['payment_link'])



                logger.info(f"Created invoice from document: {invoice.invoice_number}")
            
            # Serialize response using proper format
            from rest_framework.request import Request
            from django.test.client import RequestFactory
            factory = RequestFactory()
            django_request = factory.get('/')
            django_request.user = request.user
            drf_request = Request(django_request)
            
            serializer = NewInvoiceResponseSerializer(invoice, context={'request': drf_request})
            
            return self.success_response(
                data=serializer.data,
                message="Invoice created successfully from document",
                status_code=status.HTTP_201_CREATED
            )
        
        except Exception as e:
            logger.error(f"Document invoice creation failed: {e}")
            return self.error_response(
                f"Failed to create invoice: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        finally:
            if temp_file_path and default_storage.exists(temp_file_path):
                default_storage.delete(temp_file_path)


class AIChatQueryView(StandardResponseMixin, APIView):
    """
    AI-powered natural language query for reports and data analysis.
    
    POST /api/ai/chat/
    Content-Type: application/json
    Authorization: Bearer <token>
    
    Body:
    {
        "question": "How many invoices did I send this month?"
    }
    
    Returns:
    - SQL query (for debugging)
    - Query results
    - Natural language answer
    """
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        # Load AI modules
        ai = get_ai_modules()
        if not ai['available']:
            return self.error_response(
                f"AI module not available: {ai.get('error', 'Unknown error')}",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        question = request.data.get('question')
        
        if not question:
            return self.error_response(
                "Question is required",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            logger.info(f"AI chat query for user {request.user.id}: {question}")
            
            # Query with AI
            result = ai['natural_language_query'](
                user_id=str(request.user.id),
                question=question
            )
            
            if not result['success']:
                return self.error_response(
                    f"Query failed: {result.get('error')}",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            return self.success_response(
                data={
                    'question': question,
                    'answer': result['answer'],
                    'sql_query': result.get('sql_query'),
                    'result_data': result.get('result')
                },
                message="Query processed successfully"
            )
        
        except Exception as e:
            logger.error(f"AI chat query failed: {e}")
            return self.error_response(
                f"Failed to process query: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        


class VoiceQuoteUploadPDFView(StandardResponseMixin, APIView):
    """
    POST /quoteapp/ai/voice/quote/{id}/upload-pdf/
    Form-data: pdf_file (file), send_email (bool, optional)
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, pk=None):
        try:
            quote = Quote.objects.get(quote_id=pk, user=request.user)
        except Quote.DoesNotExist:
            return self.error_response("Quote not found", status_code=404)

        pdf_file = request.FILES.get('pdf_file')
        if not pdf_file:
            return self.error_response("pdf_file is required", status_code=400)

        from django.core.files.base import ContentFile
        from django.core.mail import EmailMessage
        from django.conf import settings

        quote.pdf_file.save(
            f"quote_{quote.quote_number}.pdf",
            ContentFile(pdf_file.read()),
            save=True
        )
        quote.pdf_generated_at = timezone.now()
        quote.can_edit = False
        quote.save(update_fields=['pdf_generated_at', 'can_edit'])

        send_email = request.data.get('send_email', 'false').lower() == 'true'
        if send_email and quote.client.email:
            email_body = f"""
                Dear {quote.client.name},

                Please find attached Quote #{quote.quote_number}.

                Issue Date: {quote.issue_date}
                Due Date: {quote.due_date}
                Total Amount: £{quote.total}

                Best regards,
                {request.user.email}
            """
            email = EmailMessage(
                subject=f"Quote #{quote.quote_number}",
                body=email_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[quote.client.email],
            )
            quote.pdf_file.open('rb')
            email.attach(f"quote_{quote.quote_number}.pdf", quote.pdf_file.read(), 'application/pdf')
            quote.pdf_file.close()
            email.send()

        return self.success_response(
            {'pdf_url': f"{settings.BASE_URL}{quote.pdf_file.url}"},
            "PDF uploaded and email sent" if send_email else "PDF uploaded successfully"
        )


class VoiceInvoiceUploadPDFView(StandardResponseMixin, APIView):
    """
    POST /quoteapp/ai/voice/invoice/{id}/upload-pdf/
    Form-data: pdf_file (file), send_email (bool, optional)
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, pk=None):
        try:
            invoice = Invoice.objects.get(invoice_id=pk, user=request.user)
        except Invoice.DoesNotExist:
            return self.error_response("Invoice not found", status_code=404)

        pdf_file = request.FILES.get('pdf_file')
        if not pdf_file:
            return self.error_response("pdf_file is required", status_code=400)

        from django.core.files.base import ContentFile
        from django.core.mail import EmailMessage
        from django.conf import settings

        invoice.pdf_file.save(
            f"invoice_{invoice.invoice_number}.pdf",
            ContentFile(pdf_file.read()),
            save=True
        )
        invoice.pdf_generated_at = timezone.now()
        invoice.can_edit = False
        invoice.save(update_fields=['pdf_generated_at', 'can_edit'])

        send_email = request.data.get('send_email', 'false').lower() == 'true'
        if send_email and invoice.client.email:
            email_body = f"""
                Dear {invoice.client.name},

                Please find attached Invoice #{invoice.invoice_number}.
                Total Amount: £{invoice.total}
                Pay here: {invoice.payment_link}

                Best regards,
                {request.user.email}
            """
            email = EmailMessage(
                subject=f"Invoice #{invoice.invoice_number}",
                body=email_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[invoice.client.email],
            )
            invoice.pdf_file.open('rb')
            email.attach(f"invoice_{invoice.invoice_number}.pdf", invoice.pdf_file.read(), 'application/pdf')
            invoice.pdf_file.close()
            email.send()

        return self.success_response(
            {'pdf_url': f"{settings.BASE_URL}{invoice.pdf_file.url}"},
            "PDF uploaded and email sent" if send_email else "PDF uploaded successfully"
        )