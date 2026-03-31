

from .serializers import FolderSerializer,QuoteSerializer,QuoteItemSerializer,InvoiceSerializer,InvoiceItemSerializer,ScannedDocumentSerializer
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from django.views.decorators.csrf import csrf_exempt
from utils.n8n_webhooks import n8n_client
import logging
import io
import csv
from django.utils import timezone
from django.core.mail import EmailMessage, send_mail
from django.http import HttpResponse
from django.conf import settings
from django.db.models import Prefetch, Count, Sum
from django.shortcuts import get_object_or_404, redirect
from django.db import transaction
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework import filters
from .models import Quote, QuoteItem, InvoiceItem ,Folder,Invoice,QuoteToken,QuoteCounter,InvoiceCounter,ensure_scanned_folder,ScannedDocument
from clientapp.models import Client
from rest_framework.exceptions import ValidationError
logger = logging.getLogger(__name__)
from rest_framework import viewsets, status, serializers
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from io import BytesIO
from decimal import Decimal
from quoteapp.utils import generate_quote_pdf,generate_invoice_pdf
from django.core.files.base import ContentFile
from datetime import timedelta
from django.conf import settings
import stripe
from utils.payment import create_stripe_payment_link
# from notificationapp.firebase_config import send_fcm_notification
import json
logger = logging.getLogger(__name__)
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from decimal import Decimal, ROUND_HALF_UP
from .serializers import NewInvoiceCreateSerializer,NewQuoteCreateSerializer,NewQuoteItemResponseSerializer,NewQuoteItemSerializer,NewQuoteResponseSerializer, NewInvoiceResponseSerializer,QuoteListRetrieveSerializer
from django.shortcuts import render
from notificationapp.notification_helpers import notify_quote_accepted, notify_invoice_paid
# ---------------------------
# Standard Response Mixin
# ---------------------------
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


# ---------------------------
# Utility: Ensure client folder
# ---------------------------
def ensure_client_folder(user, client):
    """
    Auto-create folder for a client if it doesn't exist.
    Folder name = "<client.id>_<client.name>"
    """
    #folder_name = f"{obj.id}_{obj.name.replace(' ', '_')}"
    folder_name = f"{client.name.replace(' ', '_')}"
    folder, created = Folder.objects.get_or_create(
        user=user,
        folder_name=folder_name
    )
    return folder


# ---------------------------
# Folder ViewSet
# ---------------------------
class FolderViewSet(StandardResponseMixin, viewsets.ModelViewSet):
    """
    CRUD operations for Folders.
    Includes quote & invoice counts and N+1 prevention.
    """
    serializer_class = FolderSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, JSONParser]

    def get_queryset(self):
        """
        Optimized queryset with select_related, prefetch_related, and annotations.
        Prevents N+1 queries.
        """
        return (
            Folder.objects.filter(user=self.request.user)
            .select_related("user")
            .prefetch_related(
                Prefetch("quotes", queryset=Quote.objects.filter(is_deleted=False)),
                Prefetch("invoices", queryset=Invoice.objects.all())
            )
            .annotate(
                quotes_count=Count("quotes"),
                invoices_count=Count("invoices")
            )
            .order_by("folder_name")
        )

    def list(self, request, *args, **kwargs):
        """List all folders for current user with counts"""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.get_serializer(queryset, many=True)
            return self.success_response(serializer.data, "Folders fetched successfully")
        except Exception as e:
            logger.error(f"Folder list error: {str(e)}")
            return self.error_response("Failed to fetch folders", status.HTTP_500_INTERNAL_SERVER_ERROR)

    def create(self, request, *args, **kwargs):
        """Create new folder for current user"""
        try:
            # serializer = self.get_serializer(data=request.data)
            serializer = self.get_serializer(data=request.data, files=request.FILES)
            serializer.is_valid(raise_exception=True)
            serializer.save(user=self.request.user)
            return self.success_response(serializer.data, "Folder created successfully", status.HTTP_201_CREATED)
        except serializers.ValidationError as e:
            return self.error_response(str(e.detail), status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Folder creation error: {str(e)}")
            return self.error_response("Failed to create folder", status.HTTP_500_INTERNAL_SERVER_ERROR)

    def destroy(self, request, *args, **kwargs):
        """Delete folder only if empty (no quotes or invoices)"""
        try:
            instance = self.get_object()
            if instance.quotes.exists() or instance.invoices.exists():
                return self.error_response(
                    "Cannot delete folder containing quotes or invoices. Move them first.",
                    status.HTTP_400_BAD_REQUEST,
                )
            self.perform_destroy(instance)
            return self.success_response(None, "Folder deleted successfully")
        except Exception as e:
            logger.error(f"Folder deletion error: {str(e)}")
            return self.error_response("Failed to delete folder", status.HTTP_500_INTERNAL_SERVER_ERROR)

    '''
    @action(detail=True, methods=['get'], url_path='quotes')
    def folder_quotes(self, request, pk=None):

        try:
            folder = self.get_object()
            quotes = folder.quotes.filter(is_deleted=False).select_related('client')
                    # ✅ FIX: Use serializer to get all quote data including items
            serializer = QuoteSerializer(quotes, many=True)
            return self.success_response(serializer.data, "Folder quotes fetched successfully")
        except Exception as e:
            logger.error(f"Folder quotes error: {str(e)}")
            return self.error_response(
                f"Failed to fetch folder quotes: {str(e)}", 
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    '''
    # @action(detail=True, methods=['get'], url_path='quotes')
    # def folder_quotes(self, request, pk=None):
    #     """
    #     Return ONLY quote PDFs (no quote JSON)
    #     """
    #     try:
    #         folder = self.get_object()

    #         quotes = folder.quotes.filter(
    #             is_deleted=False,
    #             pdf_file__isnull=False
    #         ).select_related('client')

    #         data = []
    #         for quote in quotes:
    #             data.append({
    #                 "quote_id": quote.quote_id,
    #                 "quote_number": quote.quote_number,
    #                 "client": quote.client.name,
    #                 "pdf_url": request.build_absolute_uri(quote.pdf_file.url),
    #                 "generated_at": quote.pdf_generated_at,
    #             })

    #         return self.success_response(
    #             data,
    #             "Quote PDFs fetched successfully"
    #         )

    #     except Exception as e:
    #         logger.error(f"Folder quotes error: {str(e)}")
    #         return self.error_response(
    #             "Failed to fetch quote PDFs",
    #             status.HTTP_500_INTERNAL_SERVER_ERROR
    #         )
    @action(detail=True, methods=['get'], url_path='quotes')
    def folder_quotes(self, request, pk=None):
        """
        Return ONLY quote PDFs (safe with error handling)
        """
        try:
            folder = self.get_object()

            quotes = folder.quotes.filter(
                is_deleted=False,
                pdf_file__isnull=False
            ).select_related('client')

            data = []

            for quote in quotes:
                try:
                    # Safety check: skip if pdf_file is None or empty
                    if not quote.pdf_file or not quote.pdf_file.name:
                        logger.warning(
                            f"Skipping quote {quote.quote_id}: missing PDF file"
                        )
                        continue

                    # Build URL safely
                    pdf_url = request.build_absolute_uri(quote.pdf_file.url)
                    
                    data.append({
                        "quote_id": quote.quote_id,
                        "quote_number": quote.quote_number,
                        "client": quote.client.name,
                        "pdf_url": pdf_url,
                        "generated_at": quote.pdf_generated_at,
                    })

                except Exception as file_error:
                    logger.warning(
                        f"Skipping quote {quote.quote_id}: {str(file_error)}"
                    )
                    continue

            return self.success_response(
                data,
                "Quote PDFs fetched successfully"
            )

        except Exception as e:
            logger.error(f"Folder quotes error: {str(e)}")
            return self.error_response(
                f"Failed to fetch quote PDFs {e}",
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
    @action(detail=True, methods=['get'], url_path='invoices')
    def folder_invoices(self, request, pk=None):
        """
        Return ONLY invoice PDFs (safe)
        """
        try:
            folder = self.get_object()

            invoices = folder.invoices.filter(
                is_deleted=False,
                pdf_file__isnull=False
            ).select_related('client')

            data = []

            for invoice in invoices:
                try:
                    if not invoice.pdf_file or not invoice.pdf_file.name:
                        continue  # skip broken reference

                    data.append({
                        "invoice_id": invoice.invoice_id,
                        "invoice_number": invoice.invoice_number,
                        "client": invoice.client.name,
                        "pdf_url": request.build_absolute_uri(invoice.pdf_file.url),
                        "generated_at": invoice.pdf_generated_at,
                    })

                except Exception as file_error:
                    logger.warning(
                        f"Skipping invoice {invoice.invoice_id}: missing PDF file"
                    )
                    continue

            return self.success_response(
                data,
                "Invoice PDFs fetched successfully"
            )

        except Exception as e:
            logger.error(f"Folder invoices error: {str(e)}")
            return self.error_response(
                "Failed to fetch invoice PDFs",
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'], url_path='scanned-images')
    def folder_scanned_images(self, request, pk=None):
        try:
            folder = self.get_object()
            
            scanned_docs = ScannedDocument.objects.filter(
                user=request.user,
                folder=folder  # CHANGED THIS LINE
            )
            
            data = []
            for doc in scanned_docs:
                data.append({
                    "id": doc.id,
                    "client": doc.client.name if doc.client else None,  # HANDLE NULL CLIENT
                    "image_url": request.build_absolute_uri(doc.image.url),
                    "created_at": doc.created_at,
                })
            
            return self.success_response(data, "Scanned images fetched successfully")
            
        except Exception as e:
            logger.error(f"Scanned images error: {str(e)}")
            return self.error_response(f"Failed to fetch scanned images {e}", status.HTTP_500_INTERNAL_SERVER_ERROR)

    '''
    @action(detail=True, methods=['get'], url_path='scanned-images')
    def folder_scanned_images(self, request, pk=None):
        """
        Return scanned image URLs only
        """
        try:
            folder = self.get_object()

            scanned_docs = ScannedDocument.objects.filter(
                user=request.user,
                client__in=folder.quotes.values_list('client_id', flat=True)
            )

            data = []
            for doc in scanned_docs:
                data.append({
                    "id": doc.id,
                    "client": doc.client.name,
                    "image_url": request.build_absolute_uri(doc.image.url),
                    "created_at": doc.created_at,
                })

            return self.success_response(
                data,
                "Scanned images fetched successfully"
            )

        except Exception as e:
            logger.error(f"Scanned images error: {str(e)}")
            return self.error_response(
                "Failed to fetch scanned images",
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )
   
    '''  

    '''
    @action(detail=True, methods=['get'], url_path='invoices')
    def folder_invoices(self, request, pk=None):
        try:
            folder = self.get_object()
            invoices = folder.invoices.all().select_related('client')

            serializer = InvoiceSerializer(invoices, many=True)
            return self.success_response(serializer.data, "Folder invoices fetched successfully")
            
        except Exception as e:
            logger.error(f"Folder invoices error: {str(e)}")
            return self.error_response(
                f"Failed to fetch folder invoices: {str(e)}", 
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    '''
    '''
    # @action(detail=True, methods=['get'], url_path='invoices')
    # def folder_invoices(self, request, pk=None):
    #     """
    #     Return ONLY invoice PDFs (no invoice JSON)
    #     """
    #     try:
    #         folder = self.get_object()

    #         invoices = folder.invoices.filter(
    #             is_deleted=False,
    #             pdf_file__isnull=False
    #         ).select_related('client')

    #         data = []
    #         for invoice in invoices:
    #             data.append({
    #                 "invoice_id": invoice.invoice_id,
    #                 "invoice_number": invoice.invoice_number,
    #                 "client": invoice.client.name,
    #                 "pdf_url": request.build_absolute_uri(invoice.pdf_file.url),
    #                 "generated_at": invoice.pdf_generated_at,
    #             })

    #         return self.success_response(
    #             data,
    #             "Invoice PDFs fetched successfully"
    #         )

    #     except Exception as e:
    #         logger.error(f"Folder invoices error: {str(e)}")
    #         return self.error_response(
    #             "Failed to fetch invoice PDFs",
    #             status.HTTP_500_INTERNAL_SERVER_ERROR
    #         )
    '''






# =============================================================================Scan ===================================================================

class ImageScanUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = ScannedDocumentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                "success": False,
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        # ✅ ALWAYS force scanned documents folder
        scanned_folder = ensure_scanned_folder(request.user)

        scanned_doc = serializer.save(
            user=request.user,
            folder=scanned_folder
        )

        return Response({
            "success": True,
            "message": "Scanned image uploaded successfully.",
            "data": ScannedDocumentSerializer(scanned_doc).data
        }, status=status.HTTP_201_CREATED)

# =============================================================================QUOTE VIEWS ===================================================================
# quoteapp/views.py

class QuoteViewSet(StandardResponseMixin, viewsets.ModelViewSet):
    """
    CRUD operations for Quotes with advanced optimization
    Handles quote creation, sending, PDF generation, export, and status updates
    """
    serializer_class = QuoteSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, JSONParser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['description', 'client__name', 'status']
    ordering_fields = ['created_at', 'issue_date', 'due_date', 'total']

    def get_queryset(self):
        """
        Optimized queryset to prevent N+1 queries
        Uses select_related for user, client, folder; prefetch_related for items, invoices
        """
        return Quote.objects.filter(user=self.request.user, is_deleted=False)\
            .select_related('user', 'client', 'folder')\
            .prefetch_related(
                Prefetch('items', queryset=QuoteItem.objects.all()),
                Prefetch('invoices', queryset=Invoice.objects.all())
            )\
            .order_by('-created_at')

    def get_serializer_context(self):
        """Add request and edit method to serializer context for voice/manual validation"""
        context = super().get_serializer_context()
        context['request'] = self.request
        context['edit_method'] = self.request.data.get('source', 'manual')
        return context

    # def list(self, request, *args, **kwargs):
    #     """
    #     Get quotes with filtering and pagination
    #     Supports status, source, client, folder, and date range filters
    #     """
    #     try:
    #         queryset = self.filter_queryset(self.get_queryset())

    #         # Status filter
    #         status_filter = request.query_params.get('status')#The API endpoint receives ?status=draft from the frontend, so you need:
    #         '''
    #         URL parameter name: status (what the frontend sends), so .get('status') is correct
    #         Database field name: quote_status (what Django ORM uses)
    #         '''
    #         if status_filter:
    #             if status_filter == 'sent':
    #                 queryset = queryset.filter(quote_status__in=['sent', 'won', 'lost'])
    #             else:
    #                 queryset = queryset.filter(quote_status=status_filter)

    #         # Source filter (voice/manual)
    #         source_filter = request.query_params.get('source')
    #         if source_filter:
    #             queryset = queryset.filter(source=source_filter)

    #         # Client filter
    #         client_id = request.query_params.get('client_id')
    #         if client_id:
    #             queryset = queryset.filter(client_id=client_id)

    #         # Folder filter
    #         folder_id = request.query_params.get('folder_id')
    #         if folder_id:
    #             queryset = queryset.filter(folder_id=folder_id)

    #         # Date range filter
    #         start_date = request.query_params.get('start_date')
    #         end_date = request.query_params.get('end_date')
    #         if start_date and end_date:
    #             queryset = queryset.filter(issue_date__range=[start_date, end_date])

    #         # Paginate
    #         page = self.paginate_queryset(queryset)
    #         if page is not None:
    #             serializer = self.get_serializer(page, many=True)
                
    #             # return self.get_paginated_response(serializer.data)

    #             paginated_response = self.get_paginated_response(serializer.data)
    #             return self.success_response(
    #                 paginated_response.data,
    #                 "Data fetched successfully"
    #             )
            
    #         serializer = self.get_serializer(queryset, many=True)
    #         return self.success_response(serializer.data, "Quotes fetched successfully")
    #     except Exception as e:
    #         logger.error(f"Quote list error: {str(e)}")
    #         return self.error_response("Failed to fetch quotes", status.HTTP_500_INTERNAL_SERVER_ERROR)
    def retrieve(self, request, *args, **kwargs):
        """Get single quote - returns new-create format"""
        try:
            instance = self.get_object()
            serializer = QuoteListRetrieveSerializer(instance, context={'request': request})
            return self.success_response(serializer.data, "Quote fetched successfully")
        except Exception as e:
            logger.error(f"Quote retrieve error: {str(e)}")
            return self.error_response(f"Failed to fetch quote: {str(e)}", status.HTTP_500_INTERNAL_SERVER_ERROR)

    def list(self, request, *args, **kwargs):
        """Get quotes - returns new-create format"""
        try:
            queryset = self.filter_queryset(self.get_queryset())

            # Status filter
            status_filter = request.query_params.get('status')
            if status_filter:
                if status_filter == 'sent':
                    queryset = queryset.filter(quote_status__in=['sent', 'won', 'lost'])
                else:
                    queryset = queryset.filter(quote_status=status_filter)

            # Source filter
            source_filter = request.query_params.get('source')
            if source_filter:
                queryset = queryset.filter(source=source_filter)

            # Client filter
            client_id = request.query_params.get('client_id')
            if client_id:
                queryset = queryset.filter(client_id=client_id)

            # Folder filter
            folder_id = request.query_params.get('folder_id')
            if folder_id:
                queryset = queryset.filter(folder_id=folder_id)

            # Date range filter
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            if start_date and end_date:
                queryset = queryset.filter(issue_date__range=[start_date, end_date])

            # Paginate
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = QuoteListRetrieveSerializer(page, many=True, context={'request': request})
                paginated_response = self.get_paginated_response(serializer.data)
                return self.success_response(paginated_response.data, "Data fetched successfully")

            serializer = QuoteListRetrieveSerializer(queryset, many=True, context={'request': request})
            return self.success_response(serializer.data, "Quotes fetched successfully")

        except Exception as e:
            logger.error(f"Quote list error: {str(e)}")
            return self.error_response("Failed to fetch quotes", status.HTTP_500_INTERNAL_SERVER_ERROR)


    def create(self, request, *args, **kwargs):
        """
        Create new quote with items and auto-associate folder
        Validates client and ensures atomicity
        """
        try:
            data = request.data.copy()

            client_id = data.get('client')
            print("Raw data:", request.data)
            if not client_id:
                return self.error_response("Client is required", status.HTTP_400_BAD_REQUEST)

            try:
                client = Client.objects.get(id=client_id, user=request.user)
            except Client.DoesNotExist:
                return self.error_response("Client not found", status_code=status.HTTP_404_NOT_FOUND)
                # return self.error_response("Client not found", status.HTTP_404_NOT_FOUND)

            folder = ensure_client_folder(request.user, client)
            data['folder'] = folder.folder_id

            # Parse items manually
            items_str = data.get('items')
            items_data = []
            if items_str:
                if isinstance(items_str, str):
                    try:
                        parsed = json.loads(items_str)
                        if isinstance(parsed, dict):
                            parsed = [parsed]
                        items_data = parsed
                        print(f"Parsed {len(items_data)} items")
                    except json.JSONDecodeError:
                        return self.error_response('Invalid JSON for items', status.HTTP_400_BAD_REQUEST)
                elif isinstance(items_str, list):
                    items_data = items_str
                    print(f"Got {len(items_data)} items from list")

            # Pop items from data (avoid nested serializer)
            data.pop('items', None)

            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            '''
            with transaction.atomic():
                quote = serializer.save(user=request.user)

                # Create items directly
                for item_dict in items_data:
                    item_dict.pop('id', None)
                    item_dict['duration_unit'] = data.get("duration_unit", "hours")
                    QuoteItem.objects.create(quote=quote, **item_dict)
            '''
            with transaction.atomic():
                # Create quote WITHOUT quote_number first
                validated_data = serializer.validated_data
                validated_data['user'] = request.user
                validated_data['subtotal'] = Decimal('0.00')
                validated_data['total'] = Decimal('0.00')
                
                # Generate quote number INSIDE transaction
                year = timezone.now().year
                counter_obj, created = QuoteCounter.objects.select_for_update().get_or_create(
                    user=request.user,
                    year=year
                )
                counter_obj.counter += 1
                counter_obj.save()
                # validated_data['quote_number'] = f"QT-{year}-{counter_obj.counter:04d}"
                # validated_data['quote_number'] = f"QT-{request.user.id}-{year}-{counter_obj.counter:04d}"
                # short_uid = "-".join(str(request.user.id).split('-')[:2])# first block of UUID
                # validated_data['invoice_number'] = f"INV-{request.user.id}-{year}-{counter_obj.counter:04d}"
                short_uid = str(request.user.id)[:4]  # Takes first 8 chars: "1e95c583"
                validated_data['quote_number'] = f"QT-{short_uid}-{year}-{counter_obj.counter:02d}"
                
                # Now create the quote with the quote_number
                quote = Quote.objects.create(**validated_data)
                # ✅ SIGNATURE HANDLING GOES HERE
                if "signature" in request.FILES:
                    quote.signature = request.FILES["signature"]
                    quote.save(update_fields=['signature'])

                # Create items directly
                for item_dict in items_data:
                    item_dict.pop('id', None)
                    item_dict['duration_unit'] = data.get("duration_unit", "hours")
                    QuoteItem.objects.create(quote=quote, **item_dict)

                quote.refresh_from_db()# 🚨 Re-fetch quote after all items are committed, without this line , I was getting subtotal and total 0 problem
                quote.calculate_totals()
                quote.save(update_fields=['subtotal', 'total'])
                quote = Quote.objects.prefetch_related('items').get(pk=quote.pk)#for this line, item list is coming in response

            output_serializer = self.get_serializer(quote)
            return self.success_response(
                output_serializer.data,
                "Quote created successfully",
                status.HTTP_201_CREATED
            )
        except ValidationError as e:
            return self.error_response(str(e), status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Quote creation error: {str(e)}")
            return self.error_response(f"Failed to create quote {e}", status.HTTP_500_INTERNAL_SERVER_ERROR)       

    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if not instance.can_edit:
                return self.error_response("Cannot edit after PDF generation", status.HTTP_400_BAD_REQUEST)

            data = request.data.copy()
            
            # ✅ Extract and parse items BEFORE passing to serializer
            items_str = data.get("items")
            items_data = []
            
            if items_str:
                if isinstance(items_str, str):
                    try:
                        parsed = json.loads(items_str)
                        if isinstance(parsed, dict):
                            parsed = [parsed]
                        items_data = parsed
                        print(f"✅ Parsed {len(items_data)} items for update")
                        print(f"✅ Items data: {items_data}")
                    except json.JSONDecodeError:
                        return self.error_response("Invalid JSON for items", status.HTTP_400_BAD_REQUEST)
                elif isinstance(items_str, list):
                    items_data = items_str
                    print(f"✅ Got {len(items_data)} items from list")
            
            # ✅ REMOVE items from data to prevent serializer processing
            data.pop('items', None)
            
            # ✅ Update quote fields (without items)
            serializer = self.get_serializer(instance, data=data, partial=True)
            serializer.is_valid(raise_exception=True)
            
            with transaction.atomic():
                quote = serializer.save()
                
                # ✅ Handle signature separately
                if "signature" in request.FILES:
                    quote.signature = request.FILES["signature"]
                    quote.save(update_fields=['signature'])
                
                # ✅ NOW handle items manually (like in create())
                if items_data:
                    current_items = {item.id: item for item in quote.items.all()}
                    print(f"✅ Current item IDs in DB: {list(current_items.keys())}")
                    
                    for item_dict in items_data:
                        # Support both 'id' and 'item_id' in request
                        item_id = item_dict.get('id') or item_dict.get('item_id')
                        print(f"✅ Processing item_id: {item_id}")
                        
                        if item_id:
                            if item_id not in current_items:
                                return self.error_response(
                                    f"Item ID {item_id} does not belong to Quote #{quote.quote_id}",
                                    status.HTTP_400_BAD_REQUEST
                                )
                            
                            # Update existing item
                            item = current_items[item_id]
                            for key, value in item_dict.items():
                                if key not in ['id', 'item_id']:  # Skip ID fields
                                    setattr(item, key, value)
                            item.save()
                            print(f"✅ Updated item {item_id}")
                        else:
                            # Create new item
                            item_dict.pop('id', None)
                            item_dict.pop('item_id', None)
                            item_dict['duration_unit'] = data.get("duration_unit", "hours")
                            QuoteItem.objects.create(quote=quote, **item_dict)
                            print(f"✅ Created new item")
                
                # ✅ Recalculate totals
                quote.refresh_from_db()
                quote.calculate_totals()
                quote.save(update_fields=['subtotal', 'total'])
            
            return self.success_response(
                self.get_serializer(quote).data,
                "Quote updated successfully"
            )

        except ValidationError as e:
            return self.error_response(str(e), status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Quote update error: {str(e)}")
            return self.error_response(f"Failed to update quote: {str(e)}", status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def destroy(self, request, *args, **kwargs):
        """Soft delete quote"""
        try:
            quote = self.get_object()
            quote.is_deleted = True
            quote.deleted_at = timezone.now()
            quote.save()
            return self.success_response({"quote_id": quote.quote_id}, "Quote deleted successfully")
        except Exception as e:
            logger.error(f"Quote deletion error: {str(e)}")
            return self.error_response(f"Failed to delete quote {e}", status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_permissions(self):
        """Allow unauthenticated access for accept/reject actions"""
        if self.action in ['accept', 'reject']:
            return []  # No authentication required
        return super().get_permissions()  # Default: requires authentication
    
    def get_object(self):
        """Override to allow unauthenticated access for accept/reject"""
        if self.action in ['accept', 'reject']:
            # ✅ Don't filter by user for accept/reject - just get by pk
            queryset = Quote.objects.all()
            obj = get_object_or_404(queryset, pk=self.kwargs['pk'])
            return obj
        return super().get_object()  # Normal behavior for other actions
    
    '''
    @action(detail=True, methods=['post'], url_path='send')
    def send(self, request, pk=None):
        try:
            quote = self.get_object()
            if quote.quote_status not in ['draft', 'sent']:
                return self.error_response(f"Cannot send quote with status: {quote.quote_status}", status.HTTP_400_BAD_REQUEST)

            # Validate required fields
            missing_fields = []
            if not quote.client.email:
                missing_fields.append("client.email")
            # if not quote.service_type:
            #     missing_fields.append("description")
            if not quote.issue_date:
                missing_fields.append("issue_date")
            if not quote.due_date:
                missing_fields.append("due_date")
            if not quote.items.exists():
                missing_fields.append("items")
            if missing_fields:
                return self.error_response(f"Missing required fields: {', '.join(missing_fields)}", status.HTTP_400_BAD_REQUEST)

            sent_via = request.data.get('sent_via', 'email')
            if sent_via in ['email', 'both'] and not quote.client.email:
                return self.error_response("Client email required for email sending", status.HTTP_400_BAD_REQUEST)
            
            # ✅ NEW: Create secure token with expiry
            quote_token = QuoteToken.objects.create(
                quote=quote,
                expires_at=timezone.now() + timedelta(days=30)  # Token valid for 30 days
            )

            # ✅ UPDATED: Use stored token in links
            quote.accept_link = f"{settings.BASE_URL}/quoteapp/quotes/{quote.quote_id}/accept/?token={quote_token.token}"
            quote.reject_link = f"{settings.BASE_URL}/quoteapp/quotes/{quote.quote_id}/reject/?token={quote_token.token}"
            quote.quote_status = 'sent'
            quote.sent_via = sent_via
            quote.sent_at = timezone.now()
            quote.save()

            # ✅ NEW: Generate PDF if not exists
            if not quote.pdf_file:
                pdf_bytes = generate_quote_pdf(quote)  # Use our real PDF generator
                quote.pdf_file.save(
                    f"quote_{quote.quote_number}.pdf",
                    ContentFile(pdf_bytes),
                    save=True
                )

            # Send email
            if sent_via in ['email', 'both']:
                # ✅ UPDATED: Better email with HTML formatting

                #these 3 lines from previous quote 
                # ✅ Accept Quote: {quote.accept_link}
                # ❌ Reject Quote: {quote.reject_link}
                # This link expires on {quote_token.expires_at.strftime('%Y-%m-%d')}.
                email_body = f"""
                Dear {quote.client.name},
                
                Please find attached Quote #{quote.quote_number} for your review.
                
                Issue Date: {quote.issue_date}
                Due Date: {quote.due_date}
                Total Amount: £{quote.total}
                
                Please review the quote and approve
                
                Best regards,
                {request.user.email}
                """
                
                email = EmailMessage(
                    subject=f"Quote #{quote.quote_number} from {request.user.email}",
                    body=email_body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[quote.client.email],
                    headers={'Reply-To': request.user.email}
                )

                # Attach PDF
                if quote.pdf_file and quote.pdf_file.storage.exists(quote.pdf_file.name):
                    with quote.pdf_file.open('rb') as pdf:
                        email.attach(f"quote_{quote.quote_number}.pdf", pdf.read(), 'application/pdf')

                email.send()

            # Fake WhatsApp (replace with real API)
            if sent_via in ['whatsapp', 'both']:
                whatsapp_url = f"https://api.whatsapp.com/send?phone={quote.client.phone_number}&text=Quote%20%23{quote.quote_id}:%20Accept%20{quote.accept_link}%20Reject%20{quote.reject_link}"
                logger.info(f"Simulated WhatsApp send: {whatsapp_url}")

            #return self.success_response(QuoteSerializer(quote).data, f"Quote sent successfully via {sent_via}")#after sending the qoute, I was getting previous quote response 
            response_serializer = NewQuoteResponseSerializer(
                quote,
                context={'request': request}
            )

            return self.success_response(
                response_serializer.data,
                f"Quote sent successfully via {sent_via}"
            )
        except Exception as e:
            logger.error(f"Quote send error: {str(e)}")
            return self.error_response(f"Failed to send quote {e}", status.HTTP_500_INTERNAL_SERVER_ERROR)

    '''


    @action(detail=True, methods=['post'], url_path='generate-pdf')
    def generate_pdf(self, request, pk=None):
        """
        Generate PDF for quote and lock editing
        Stub: Actual PDF generation handled by frontend or external library
        """
        try:
            quote = self.get_object()
            if quote.pdf_file and quote.pdf_generated_at:
                return self.error_response("PDF already generated", status.HTTP_400_BAD_REQUEST)

            # Simulate PDF bytes (replace with real PDF generation later)
            # buffer = io.BytesIO()
            # buffer.write(b"%PDF-1.4 simulated pdf content here %EOF")  # dummy content
            # pdf_bytes = buffer.getvalue()

            # ✅ NEW: Use real PDF generator
            pdf_bytes = generate_quote_pdf(quote)

            # Update quote fields
            quote.pdf_generated_at = timezone.now()
            quote.can_edit = False

            # Save PDF file
            quote.pdf_file.save(
                f"quote_{quote.quote_number}.pdf",
                ContentFile(pdf_bytes),
                save=False
            )

            # Save other fields too
            quote.save()
            return self.success_response(
                {'pdf_url': quote.pdf_file.url if quote.pdf_file else None},
                "PDF generated successfully"
            )
        except Exception as e:
            logger.error(f"PDF generation error: {str(e)}")
            return self.error_response(f"Failed to generate PDF {e}", status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'], url_path='export')
    def export(self, request, pk=None):
        try:
            quote = self.get_object()
            export_type = request.query_params.get('type', 'pdf').lower()

            # ====================== 📄 PDF Export ======================
            if export_type == 'pdf':
                if not quote.pdf_file:
                    # ✅ Reuse generate_quote_pdf (no duplicate code)
                    pdf_bytes = generate_quote_pdf(quote)
                    quote.pdf_file.save(
                        f"quote_{quote.quote_number}.pdf",
                        ContentFile(pdf_bytes),
                        save=True
                    )
                    quote.pdf_generated_at = timezone.now()
                    quote.can_edit = False
                    quote.save()

                # Read and return the stored PDF file
                quote.pdf_file.open('rb')
                response = HttpResponse(quote.pdf_file.read(), content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="quote_{quote.quote_number}.pdf"'
                quote.pdf_file.close()
                return response

            # ====================== 🧾 CSV Export ==============================================================================\
            
            # elif export_type == 'csv':
            #     output = io.StringIO()
            #     writer = csv.writer(output)
            #     writer.writerow([
            #         'Description', 'Service Type', 'Material Name', 'Quantity', 
            #         'Unit Price', 'Service Duration', 'Duration Unit', 'Service Rate', 'Total'
            #     ])

            #     for item in quote.items.all():
            #         material_cost = float(item.quantity) * float(item.unit_price)
            #         service_cost = float(item.service_duration) * float(item.service_rate)
            #         item_total = material_cost + service_cost

            #         writer.writerow([
            #             item.quote_description,
            #             item.service_type,
            #             item.material_name or '',
            #             item.quantity,
            #             item.unit_price,
            #             item.service_duration,
            #             item.duration_unit,
            #             item.service_rate,
            #             item_total
            #         ])

            #     # ✅ Save CSV to client folder
            #     csv_filename = f"quote_{quote.quote_number}.csv"
            #     quote.csv_file.save(csv_filename, ContentFile(output.getvalue()), save=True)
                
            #     response = HttpResponse(output.getvalue(), content_type='text/csv')
            #     # response['Content-Disposition'] = f'attachment; filename="quote_{quote.quote_number}.csv"'
            #     response['Content-Disposition'] = f'attachment; filename="{csv_filename}"'

            #     return response
            #=========================================================================================================================/
            elif export_type == 'csv':
                output = io.StringIO()
                writer = csv.writer(output)

                # Header aligned with NewQuoteResponseSerializer
                writer.writerow([
                    "Quote Number",
                    "Issue Date",
                    "Due Date",
                    "Client Name",
                    "Client Email",
                    "Description",
                    "Quantity",
                    "Unit Price",
                    "Item Total"
                ])

                subtotal = Decimal('0.00')

                for item in quote.items.all():
                    item_total = item.quantity * item.unit_price
                    subtotal += item_total

                    writer.writerow([
                        quote.quote_number,
                        quote.issue_date.strftime("%Y-%m-%d") if quote.issue_date else "",
                        quote.due_date.strftime("%Y-%m-%d") if quote.due_date else "",
                        quote.client.name,
                        quote.client.user.email if quote.client.user else "",
                        item.quote_description,
                        item.quantity,
                        item.unit_price,
                        item_total
                    ])

                vat_amount = subtotal * (quote.vat_rate / Decimal('100'))
                total = subtotal + vat_amount

                writer.writerow([])
                writer.writerow(["Subtotal", "", "", "", "", "", "", "", subtotal])
                writer.writerow(["VAT", "", "", "", "", "", "", "", vat_amount])
                writer.writerow(["Total", "", "", "", "", "", "", "", total])
            #     # ✅ Save CSV to client folder
                csv_filename = f"quote_{quote.quote_number}.csv"
                if quote.csv_file:
                    quote.csv_file.delete(save=False)
                output.seek(0)
                quote.csv_file.save(csv_filename, ContentFile(output.getvalue()), save=True)
                response = HttpResponse(output.getvalue(), content_type='text/csv')
                response['Content-Disposition'] = f'attachment; filename="quote_{quote.quote_number}.csv"'
                return response
            # ====================== 📊 Excel Export ===============================================\
            # elif export_type == 'excel':
            #     data = []
            #     for item in quote.items.all():
            #         material_cost = float(item.quantity) * float(item.unit_price)
            #         service_cost = float(item.service_duration) * float(item.service_rate)
            #         item_total = material_cost + service_cost

            #         data.append({
            #             'Description': item.quote_description,
            #             'Service Type': item.service_type,
            #             'Material Name': item.material_name or '',
            #             'Quantity': item.quantity,
            #             'Unit Price': item.unit_price,
            #             'Service Duration': item.service_duration,
            #             'Duration Unit': item.duration_unit,
            #             'Service Rate': item.service_rate,
            #             'Total': item_total
            #         })

            #     df = pd.DataFrame(data)
            #     output = io.BytesIO()
            #     df.to_excel(output, index=False, engine='openpyxl')
            #     output.seek(0)

            #     # ✅ Save Excel file to client folder
            #     excel_filename = f"quote_{quote.quote_number}.xlsx"
            #     quote.excel_file.save(excel_filename, ContentFile(output.getvalue()), save=True)

            #     response = HttpResponse(
            #         output.getvalue(),
            #         content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            #     )
            #     # response['Content-Disposition'] = f'attachment; filename="quote_{quote.quote_number}.xlsx"'
            #     response['Content-Disposition'] = f'attachment; filename="{excel_filename}"'

            #     return response
            #=================================================================================================/
            elif export_type == 'excel':
                data = []

                subtotal = Decimal('0.00')

                for item in quote.items.all():
                    item_total = item.quantity * item.unit_price
                    subtotal += item_total

                    data.append({
                        "Quote Number": quote.quote_number,
                        # "Issue Date": quote.issue_date,
                        # "Due Date": quote.due_date,
                        "Issue Date": quote.issue_date.strftime("%Y-%m-%d") if quote.issue_date else "",
                        "Due Date": quote.due_date.strftime("%Y-%m-%d") if quote.due_date else "",
                        "Client Name": quote.client.name,
                        #"Client Email": quote.client.email,
                        "Client Email": quote.client.user.email if quote.client.user else "",
                        "Description": item.quote_description,
                        "Quantity": item.quantity,
                        "Unit Price": float(item.unit_price),
                        "Item Total": float(item_total),
                    })

                vat_amount = subtotal * (quote.vat_rate / Decimal('100'))
                total = subtotal + vat_amount

                data.append({})
                data.append({"Description": "Subtotal", "Item Total": float(subtotal)})
                data.append({"Description": "VAT", "Item Total": float(vat_amount)})
                data.append({"Description": "Total", "Item Total": float(total)})

                df = pd.DataFrame(data)

                output = io.BytesIO()
                df.to_excel(output, index=False, engine='openpyxl')
                output.seek(0)
            #     # ✅ Save Excel file to client folder
                excel_filename = f"quote_{quote.quote_number}.xlsx"
                quote.excel_file.save(excel_filename, ContentFile(output.getvalue()), save=True)
                response = HttpResponse(
                    output.getvalue(),
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
                response['Content-Disposition'] = f'attachment; filename="quote_{quote.quote_number}.xlsx"'
                return response
            return self.error_response("Invalid export type", status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"Export error: {str(e)}")
            return self.error_response(f"Failed to export quote: {str(e)}", status.HTTP_500_INTERNAL_SERVER_ERROR)


    # @action(detail=True, methods=['post'], url_path='accept')
    @action(detail=True, methods=['get'], url_path='accept')  
    def accept(self, request, pk=None):
        try:
            quote = self.get_object()
            token_value = request.query_params.get('token')
            
            # ✅ NEW: Validate token properly from database
            try:
                quote_token = QuoteToken.objects.get(quote=quote, token=token_value)
            except QuoteToken.DoesNotExist:
                return self.error_response("Invalid token", status.HTTP_403_FORBIDDEN)
            
            # ✅ NEW: Check if token is valid (not used and not expired)
            '''
            if not quote_token.is_valid():
                return self.error_response("Token has expired or already been used", status.HTTP_403_FORBIDDEN)
            '''
            if not quote_token.is_valid():
                return render(
                    request,
                    "quoteapp/quote_already_accepted.html",
                    {"quote": quote}
                )

            '''
            if quote.quote_status != 'sent':
                return self.error_response(f"Cannot accept quote with status: {quote.quote_status}", status.HTTP_400_BAD_REQUEST)
            '''

            
            if quote.quote_status != 'sent':
                return render(
                    request,
                    "quoteapp/quote_invalid_status.html",
                    {"quote": quote}
                )
            
            if quote.quote_status == 'won':
                return render(
                    request,
                    "quoteapp/quote_already_accepted.html",
                    {"quote": quote}
                )
            # Update quote status
            quote.quote_status = 'won'
            quote.save()
            notify_quote_accepted(quote)
            # send_fcm_notification(
            #     user=quote.user,
            #     title="Quote Accepted! 🎉",
            #     body=f"Quote #{quote.quote_number} accepted by {quote.client.name}",
            #     notification_type='quote_accepted',
            #     extra_data={'quote_id': str(quote.quote_id)}
            # )    

            # ✅ NEW: Mark token as used
            quote_token.is_used = True
            quote_token.save()
            
            # ✅ NEW: Send confirmation email to business owner
            try:
                confirmation_email = EmailMessage(
                    subject=f"Quote #{quote.quote_number} ACCEPTED by {quote.client.name}",
                    body=f"""
                    Good news! Your quote has been accepted.
                    
                    Quote Number: {quote.quote_number}
                    Client: {quote.client.name}
                    Email: {quote.client.email}
                    Total Amount: £{quote.total}
                    Accepted At: {timezone.now().strftime('%Y-%m-%d %H:%M')}
                    
                    You can now proceed with the work and create an invoice.
                    """,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[quote.user.email],  # Send to business owner
                )
                confirmation_email.send()
            except Exception as e:
                logger.error(f"Failed to send confirmation email: {str(e)}")
            
            #return self.success_response({"quote_id": quote.quote_id}, "Quote accepted successfully")
            return render(
                request,
                "quoteapp/quote_accepted.html",
                {"quote": quote}
            )
        except Exception as e:
            logger.error(f"Quote accept error: {str(e)}")
            return self.error_response(f"Failed to accept quote: {str(e)}", status.HTTP_500_INTERNAL_SERVER_ERROR)


    @action(detail=True, methods=['get'], url_path='reject')
    def reject(self, request, pk=None):
        try:
            quote = self.get_object()
            token_value = request.query_params.get('token')
            
            # ✅ NEW: Validate token properly from database
            try:
                quote_token = QuoteToken.objects.get(quote=quote, token=token_value)
            except QuoteToken.DoesNotExist:
                return self.error_response("Invalid token", status.HTTP_403_FORBIDDEN)
            
            # ✅ NEW: Check if token is valid
            if not quote_token.is_valid():
                return self.error_response("Token has expired or already been used", status.HTTP_403_FORBIDDEN)
            
            if quote.quote_status != 'sent':
                return self.error_response(f"Cannot reject quote with status: {quote.quote_status}", status.HTTP_400_BAD_REQUEST)
            
            # Update quote status
            quote.quote_status = 'lost'
            quote.save()
            # send_fcm_notification(
            #     user=quote.user,
            #     title="Quote Rejected",
            #     body=f"Quote #{quote.quote_number} rejected by {quote.client.name}",
            #     notification_type='quote_rejected',
            #     extra_data={'quote_id': str(quote.quote_id)}
            # )
            # ✅ NEW: Mark token as used
            quote_token.is_used = True
            quote_token.save()
            
            # ✅ NEW: Send notification email to business owner
            try:
                confirmation_email = EmailMessage(
                    subject=f"Quote #{quote.quote_number} REJECTED by {quote.client.name}",
                    body=f"""
                    Your quote has been rejected.
                    
                    Quote Number: {quote.quote_number}
                    Client: {quote.client.name}
                    Email: {quote.client.email}
                    Total Amount: £{quote.total}
                    Rejected At: {timezone.now().strftime('%Y-%m-%d %H:%M')}
                    
                    You may want to follow up with the client to understand their concerns.
                    """,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[quote.user.email],  # Send to business owner
                )
                confirmation_email.send()
            except Exception as e:
                logger.error(f"Failed to send notification email: {str(e)}")
            
            return self.success_response({"quote_id": quote.quote_id}, "Quote rejected")
        except Exception as e:
            logger.error(f"Quote reject error: {str(e)}")
            return self.error_response(f"Failed to reject quote: {str(e)}", status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], url_path='upload-pdf')
    def upload_pdf(self, request, pk=None):
        """
        Frontend sends generated PDF → backend stores it and emails it.
        POST /quoteapp/quotes/{id}/upload-pdf/
        Form-data: pdf_file (file), send_email (bool, optional)
        """
        try:
            quote = self.get_object()
            pdf_file = request.FILES.get('pdf_file')
            if not pdf_file:
                return self.error_response("pdf_file is required", status.HTTP_400_BAD_REQUEST)

            # Store PDF
            quote.pdf_file.save(
                f"quote_{quote.quote_number}.pdf",
                ContentFile(pdf_file.read()),
                save=True
            )
            quote.pdf_generated_at = timezone.now()
            quote.can_edit = False
            quote.save(update_fields=['pdf_generated_at', 'can_edit'])

            # Optionally send email
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
        except Exception as e:
            logger.error(f"PDF upload error: {str(e)}")
            return self.error_response(f"Failed to upload PDF: {str(e)}", status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Get quote statistics for dashboard
        """
        try:
            quotes = self.get_queryset()
            stats = {
                'total': quotes.count(),
                'draft': quotes.filter(quote_status='draft').count(),  # ✅ CORRECT
                'sent': quotes.filter(quote_status__in=['sent', 'won', 'lost']).count(),  # ✅ CORRECT
                'won': quotes.filter(quote_status='won').count(),  # ✅ CORRECT
                'lost': quotes.filter(quote_status='lost').count(),  # ✅ CORRECT
                # 'total_value': quotes.aggregate(total=Sum('total'))['total'] or 0,
                # Only sum totals of won quotes
                'total_value': quotes.filter(quote_status='won').aggregate(total=Sum('total'))['total'] or 0,

            }
            return self.success_response(stats, "Statistics fetched successfully")
        except Exception as e:
            logger.error(f"Statistics error: {str(e)}")
            return self.error_response("Failed to fetch statistics", status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    @action(detail=True, methods=['get'], url_path='financials')
    def financials(self, request, pk=None):
        """
        GET /quoteapp/quotes/{quote_id}/financials/
        Returns: subtotal, discount, vat_rate, total for a specific quote
        """
        try:
            quote = self.get_object()
            
            financial_data = {
                'quote_id': quote.quote_id,
                'quote_number': quote.quote_number,
                'subtotal': str(quote.subtotal),
                'discount_amount': str(quote.discount_amount),
                'discount_type': quote.discount_type,
                'vat_rate': str(quote.vat_rate),
                'total': str(quote.total)
            }
            
            return self.success_response(
                financial_data, 
                "Financial details fetched successfully"
            )
        except Exception as e:
            logger.error(f"Financial details error: {str(e)}")
            return self.error_response(
                "Failed to fetch financial details", 
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    # -----------------------
    # Internal Helpers
    # -----------------------
    def _send_quote_notification(self, quote, sent_via):
        """Stub: integrate with Email/WhatsApp later"""
        logger.info(f"Quote {quote.quote_id} sent via {sent_via}")
        return True            
            
            


# ---------------------------
# Invoice ViewSet
# ---------------------------
class InvoiceViewSet(StandardResponseMixin, viewsets.ModelViewSet):
    """
    CRUD operations for Invoices with payment handling
    Handles invoice creation, sending, payment tracking
    """
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, JSONParser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['invoice_number', 'client__name', 'status']
    ordering_fields = ['created_at', 'issue_date', 'due_date', 'total']
    
    def get_queryset(self):
        """Optimized queryset for invoices with related data"""
        return Invoice.objects.filter(user=self.request.user, is_deleted=False)\
            .select_related('user', 'client', 'quote')\
            .prefetch_related(
                Prefetch('items', queryset=InvoiceItem.objects.all())
            )\
            .order_by('-created_at')
    
    def get_serializer_context(self):
        """Add request context to serializer"""
        context = super().get_serializer_context()
        context['request'] = self.request
        context['edit_method'] = self.request.data.get('edit_method', 'manual')
        return context

    def list(self, request, *args, **kwargs):
        """Get invoices with filtering and pagination"""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            
            # Status filter
            status_filter = request.query_params.get('status')
            if status_filter:
                queryset = queryset.filter(payment_status=status_filter)
            
            # Client filter
            client_id = request.query_params.get('client_id')
            if client_id:
                queryset = queryset.filter(client_id=client_id)
            
            # Quote filter
            quote_id = request.query_params.get('quote_id')
            if quote_id:
                queryset = queryset.filter(quote_id=quote_id)
            
            # Paid status filter
            is_paid = request.query_params.get('is_paid')
            if is_paid is not None:
                queryset = queryset.filter(is_paid=is_paid.lower() == 'true')
            
            # Paginate
            page = self.paginate_queryset(queryset)
            # if page is not None:
            #     serializer = self.get_serializer(page, many=True)
            #     # return self.get_paginated_response(serializer.data)
            #     paginated_response = self.get_paginated_response(serializer.data)
            #     return self.success_response(
            #         paginated_response.data,
            #         "Data fetched successfully"
            #     )
            # '''
            # This way all endpoints (including paginated ones) will go through your StandardResponseMixin.success_response and keep the same API response structure.
            # '''
            # serializer = self.get_serializer(queryset, many=True)
            if page is not None:
                serializer = NewInvoiceResponseSerializer(page, many=True, context={'request': request})
                paginated_response = self.get_paginated_response(serializer.data)
                return self.success_response(paginated_response.data, "Data fetched successfully")
            
            serializer = NewInvoiceResponseSerializer(queryset, many=True, context={'request': request})
            return self.success_response(serializer.data, "Invoices fetched successfully")
            
        except Exception as e:
            logger.error(f"Invoice list error: {str(e)}")
            return self.error_response(f"Failed to fetch invoices {e}", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def retrieve(self, request, *args, **kwargs):
        """Get single invoice - returns new-create format"""
        try:
            instance = self.get_object()
            serializer = NewInvoiceResponseSerializer(instance, context={'request': request})
            return self.success_response(serializer.data, "Invoice fetched successfully")
        except Exception as e:
            logger.error(f"Invoice retrieve error: {str(e)}")
            return self.error_response(f"Failed to fetch invoice: {str(e)}", status.HTTP_500_INTERNAL_SERVER_ERROR)
    def create(self, request, *args, **kwargs):
        """Create new invoice with auto-folder assignment"""
        try:
            data = request.data.copy()
            
            # if request.FILES.get('signature'):
            #     data['signature'] = request.FILES.get('signature')
            if 'discount_amount' in data: 
                data['discount_amount'] = str(
                    Decimal(str(data['discount_amount'])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                )
            
            # 🔧 Ensure vat_rate is Decimal with precision
            if 'vat_rate' in data:
                data['vat_rate'] = str(
                    Decimal(str(data['vat_rate'])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                )
            client_id = data.get('client')
            if not client_id:
                return self.error_response("Client is required", status_code=status.HTTP_400_BAD_REQUEST)
            
            # Fixed: Get connected_id from BusinessProfile
            connected_id = request.user.business_profile.stripe_account_id if hasattr(request.user, 'business_profile') else None
            if not connected_id:
                    return self.error_response("Complete Stripe onboarding first", status_code=400)
            
            # Validate client exists
            try:
                client = Client.objects.get(id=client_id, user=request.user)
            except Client.DoesNotExist:
                return self.error_response("Client not found", status_code=status.HTTP_404_NOT_FOUND)

            '''
            # Auto-associate folder
            folder = ensure_client_folder(request.user, client)
            data['folder'] = folder.id
            '''
            # Auto-use client’s existing folder
            # folder_name = f"{client.id}_{client.name.replace(' ', '_')}"
            folder_name = f"{client.name.replace(' ', '_')}"

            '''
            client_id is an integer, not a model instance.
            So this line will crash:

            ❌client_id.name

            because integers don’t have a .name attribute.
            '''
           
            folder = Folder.objects.filter(user=request.user, folder_name=folder_name).first()
            if not folder:
                return self.error_response("Client folder not found", status_code=status.HTTP_404_NOT_FOUND)
            data['folder'] = folder.folder_id

            # Handle invoice creation from quote
            quote_id = data.get('quote')
            if quote_id:
                try:
                    quote = Quote.objects.get(quote_id=quote_id, user=request.user)
                    if quote.quote_status != 'won':
                        return self.error_response(
                            "Can only create invoice from accepted quote",
                           status_code=status.HTTP_404_NOT_FOUND
                        )
                except Quote.DoesNotExist:
                    return self.error_response("Quote not found", status_code=status.HTTP_404_NOT_FOUND)

            # ✅ Parse items safely (FORM-DATA or raw JSON)
            items_str = data.get("items")
            items_data = []

            if items_str:
                if isinstance(items_str, str):
                    try:
                        parsed = json.loads(items_str)
                        if isinstance(parsed, dict):
                            parsed = [parsed]
                        items_data = parsed
                    except json.JSONDecodeError:
                        return self.error_response(
                            "Invalid JSON for items field.",
                            status_code=status.HTTP_404_NOT_FOUND
                        )
                elif isinstance(items_str, list):
                    items_data = items_str

            # Remove items before passing serializer
            # data.pop("items", None)

            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            
            with transaction.atomic():
                # invoice = serializer.save(user=request.user)
                validated_data = serializer.validated_data
                validated_data['user'] = request.user
                validated_data['subtotal'] = Decimal('0.00')
                validated_data['total'] = Decimal('0.00')

                year = timezone.now().year
                counter_obj, _ = InvoiceCounter.objects.select_for_update().get_or_create(
                    user=request.user,
                    year=year
                )
                counter_obj.counter += 1
                counter_obj.save()

             
                # validated_data['invoice_number'] = f"INV-{request.user.id}-{year}-{counter_obj.counter:04d}"  
                # short_uid = "-".join(str(request.user.id).split('-')[:2])# first block of UUID
                # validated_data['invoice_number'] = f"INV-{short_uid}-{year}-{counter_obj.counter:04d}"
                short_uid = str(request.user.id)[:4]  # Takes first 8 chars: "1e95c583"
                validated_data['invoice_number'] = f"INV-{short_uid}-{year}-{counter_obj.counter:02d}"

                invoice = Invoice.objects.create(**validated_data)
                # ✅ Save signature file
                # if request.FILES.get("signature"):
                #     invoice.signature = request.FILES.get("signature")
                #     invoice.save(update_fields=["signature"])               
                # Generate invoice number if not provided
                    # ✅ SIGNATURE HANDLING GOES HERE (same as quote)
                if "signature" in request.FILES:
                    invoice.signature = request.FILES["signature"]
                    invoice.save(update_fields=['signature'])
                # if not invoice.invoice_number:
                #     invoice.invoice_number = invoice.generate_invoice_number()
                #     invoice.save(update_fields=["invoice_number"])
                #     invoice.save()
                
                # invoice.calculate_amounts()
                # invoice.save()
                
                ## ✅ Create Invoice Items
                for item_dict in items_data:
                    item_dict.pop("id", None)
                    item_dict['duration_unit'] = data.get("duration_unit", "hours")  # ← ADDed THIS LINE for moving duration and unit to the items
                    InvoiceItem.objects.create(invoice=invoice, **item_dict)

                invoice.refresh_from_db()  # reload item
                invoice.calculate_amounts()
                invoice.save(update_fields=['subtotal', 'total'])


                #Generate payment link automatically
                payment_link = create_stripe_payment_link(invoice)
                if payment_link:
                    invoice.payment_link = payment_link
                    invoice.save(update_fields=["payment_link"])
                    # invoice.save()             
            return self.success_response(
                # serializer.data,
                self.get_serializer(invoice).data,
                "Invoice created successfully",
                status.HTTP_201_CREATED
            )
            
        except serializers.ValidationError as e:
            return self.error_response(str(e.detail), status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Invoice creation error: {str(e)}")
            return self.error_response(f"Failed to create invoice {e}", status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def update(self, request, *args, **kwargs):
        """Update invoice with validation"""
        try:
            instance = self.get_object()
            if not instance.can_edit:
                return self.error_response("Cannot edit after PDF generation", status.HTTP_400_BAD_REQUEST)
            
            data = request.data.copy()
            
            # ✅ Extract and parse items BEFORE passing to serializer
            items_str = data.get("items")
            items_data = []
            
            if items_str:
                if isinstance(items_str, str):
                    try:
                        parsed = json.loads(items_str)
                        if isinstance(parsed, dict):
                            parsed = [parsed]
                        items_data = parsed
                        print(f"✅ Parsed {len(items_data)} items for update")
                        print(f"✅ Items data: {items_data}")
                    except json.JSONDecodeError:
                        return self.error_response("Invalid JSON for items", status.HTTP_400_BAD_REQUEST)
                elif isinstance(items_str, list):
                    items_data = items_str
                    print(f"✅ Got {len(items_data)} items from list")
            
            # ✅ REMOVE items from data to prevent serializer processing
            data.pop('items', None)
            
            # ✅ Update invoice fields (without items)
            serializer = self.get_serializer(instance, data=data, partial=True)
            serializer.is_valid(raise_exception=True)
            
            with transaction.atomic():
                invoice = serializer.save()
                
                # ✅ Handle signature separately
                if request.FILES.get('signature'):
                    invoice.signature = request.FILES.get('signature')
                    invoice.save(update_fields=['signature'])
                
                # ✅ NOW handle items manually (like in create())
                if items_data:
                    current_items = {item.item_id: item for item in invoice.items.all()}
                    print(f"✅ Current item IDs in DB: {list(current_items.keys())}")
                    
                    for item_dict in items_data:
                        # Support both 'id' and 'item_id' in request
                        item_id = item_dict.get('item_id') or item_dict.get('id')
                        print(f"✅ Processing item_id: {item_id}")
                        
                        if item_id:
                            if item_id not in current_items:
                                return self.error_response(
                                    f"Item ID {item_id} does not belong to Invoice #{invoice.invoice_id}",
                                    status.HTTP_400_BAD_REQUEST
                                )
                            
                            # Update existing item
                            item = current_items[item_id]
                            for key, value in item_dict.items():
                                if key not in ['id', 'item_id']:  # Skip ID fields
                                    setattr(item, key, value)
                            item.save()
                            print(f"✅ Updated item {item_id}")
                        else:
                            # Create new item
                            item_dict.pop('id', None)
                            item_dict.pop('item_id', None)
                            item_dict['duration_unit'] = data.get("duration_unit", "hours")  # ← ADDed THIS LINE 
                            InvoiceItem.objects.create(invoice=invoice, **item_dict)
                            print(f"✅ Created new item")
                
                # ✅ Recalculate totals
                invoice.refresh_from_db()
                invoice.calculate_amounts()
                invoice.save(update_fields=['subtotal', 'total'])
            
            return self.success_response(
                self.get_serializer(invoice).data,
                "Invoice updated successfully"
            )
            
        except serializers.ValidationError as e:
            return self.error_response(str(e.detail), status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Invoice update error: {str(e)}")
            return self.error_response(f"Failed to update invoice: {str(e)}", status.HTTP_500_INTERNAL_SERVER_ERROR)


    def destroy(self, request, *args, **kwargs):
        """Soft delete quote"""
        try:
            invoice = self.get_object()
            # invoice.is_deleted = True
            if invoice.is_deleted:
             return self.error_response("Invoice not found or already deleted", status.HTTP_404_NOT_FOUND)
            
            invoice.is_deleted = True
            invoice.deleted_at = timezone.now()
            invoice.save()
            return self.success_response({"invoice_id": invoice.invoice_id}, "Invoice deleted successfully")
        except Exception as e:
            logger.error(f"Invoice deletion error: {str(e)}")
            return self.error_response(f"Failed to delete invoice {e}", status.HTTP_500_INTERNAL_SERVER_ERROR)
   
    '''
    @action(detail=True, methods=['post'], url_path='send')
    def send(self, request, pk=None):
        """Send invoice via email/WhatsApp with payment link & PDF"""
        try:
            invoice = self.get_object()

            if invoice.payment_status not in ['draft', 'sent', 'unpaid']:
                return self.error_response(
                    f"Cannot send invoice with status: {invoice.payment_status}",
                    status.HTTP_400_BAD_REQUEST
                )

            # ✅ Validate required fields
            missing_fields = []
            if not invoice.client.email:
                missing_fields.append("client.email")
            if not invoice.payment_link:
                missing_fields.append("payment_link")
            if not invoice.items.exists():
                missing_fields.append("items")

            if missing_fields:
                return self.error_response(
                    f"Missing required fields: {', '.join(missing_fields)}",
                    status.HTTP_400_BAD_REQUEST
                )

            sent_via = request.data.get('sent_via', 'email')
            if sent_via in ['email', 'both'] and not invoice.client.email:
                return self.error_response("Client email required for email sending", status.HTTP_400_BAD_REQUEST)

            # ✅ Update invoice status
            invoice.payment_status = 'sent'
            invoice.sent_via = sent_via
            invoice.sent_at = timezone.now()

            # ✅ Generate PDF if not exists
            if not invoice.pdf_file:
                pdf_bytes = generate_invoice_pdf(invoice)  # ⬅️ you'll create this function (similar to generate_quote_pdf)
                invoice.pdf_file.save(
                    f"invoice_{invoice.invoice_number}.pdf",
                    ContentFile(pdf_bytes),
                    save=True
                )

            invoice.save()

            # ✅ Send email
            if sent_via in ['email', 'both']:
                email_body = f"""
                Dear {invoice.client.name},

                Please find attached Invoice #{invoice.invoice_number}.

                Issue Date: {invoice.issue_date}
                Due Date: {invoice.due_date}
                Total Amount: £{invoice.total}

                Pay securely using this link:
                {create_stripe_payment_link(invoice)}

                Best regards,
                {request.user.email}
                """
                email = EmailMessage(
                    subject=f"Invoice #{invoice.invoice_number} from {request.user.email}",
                    body=email_body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[invoice.client.email],
                    headers={'Reply-To': request.user.email}
                )

                if invoice.pdf_file and invoice.pdf_file.storage.exists(invoice.pdf_file.name):
                    with invoice.pdf_file.open('rb') as pdf:
                        email.attach(f"invoice_{invoice.invoice_number}.pdf", pdf.read(), 'application/pdf')

                email.send()

            # ✅ Fake WhatsApp (simulated)
            if sent_via in ['whatsapp', 'both']:
                whatsapp_url = f"https://api.whatsapp.com/send?phone={invoice.client.phone_number}&text=Invoice%20%23{invoice.invoice_number}:%20Pay%20{invoice.payment_link}"
                logger.info(f"Simulated WhatsApp send: {whatsapp_url}")

            return self.success_response(InvoiceSerializer(invoice).data, f"Invoice sent successfully via {sent_via}")

        except Exception as e:
            logger.error(f"Invoice send error: {str(e)}")
            return self.error_response(f"Failed to send invoice: {str(e)}", status.HTTP_500_INTERNAL_SERVER_ERROR)

    '''

    @action(detail=True, methods=['post'])
    def mark_paid(self, request, pk=None):
        """Mark invoice as paid and update related quote"""
        try:
            invoice = self.get_object()
            
            
            if invoice.is_paid:
                return self.error_response("Invoice already paid", status.HTTP_400_BAD_REQUEST)
            
            invoice.is_paid = True
            invoice.payment_status = 'paid'  # ✅ CORRECT
            invoice.paid_date = timezone.now().date()
            invoice.save()
            
            # Update related quote status if exists
            if invoice.quote:
                invoice.quote.quote_status = 'won'
                invoice.quote.save()
            
            return self.success_response(
                InvoiceSerializer(invoice).data,
                "Invoice marked as paid successfully"
            )
            
        except Exception as e:
            logger.error(f"Mark paid error: {str(e)}")
            return self.error_response("Failed to mark invoice as paid", status.HTTP_500_INTERNAL_SERVER_ERROR)


    #added 9th october
    @action(detail=True, methods=['post'], url_path='generate-pdf')
    def generate_pdf(self, request, pk=None):
        """Generate PDF for invoice and lock editing"""
        try:
            invoice = self.get_object()#self.get_object() in DRF gets the single model instance based on the URL’s pk., that why on it's url, it required id
            
            # if invoice.pdf_file and invoice.pdf_generated_at:
            #     return self.error_response("PDF already generated", status.HTTP_400_BAD_REQUEST)

            pdf_bytes = generate_invoice_pdf(invoice)

            invoice.pdf_generated_at = timezone.now()
            invoice.can_edit = False
            invoice.pdf_file.save(
                f"invoice_{invoice.invoice_number}.pdf",
                ContentFile(pdf_bytes),
                save=True
            )

            return self.success_response(
                {'pdf_url': invoice.pdf_file.url if invoice.pdf_file else None},
                "PDF generated successfully"
            )
        except Exception as e:
            logger.error(f"PDF generation error: {str(e)}")
            return self.error_response(f"Failed to generate PDF: {str(e)}", status.HTTP_500_INTERNAL_SERVER_ERROR)
   
   
    @action(detail=True, methods=['get'], url_path='export')
    def export(self, request, pk=None):
        """Export invoice to PDF, CSV, or Excel — same as quote"""
        try:
            invoice = self.get_object()
            export_type = request.query_params.get('type', 'pdf').lower()

            # 📄 PDF Export
            if export_type == 'pdf':
                if not invoice.pdf_file:
                    pdf_bytes = generate_invoice_pdf(invoice)
                    invoice.pdf_file.save(
                        f"invoice_{invoice.invoice_number}.pdf",
                        ContentFile(pdf_bytes),
                        save=True
                    )
                    invoice.pdf_generated_at = timezone.now()
                    invoice.can_edit = False
                    invoice.save()

                invoice.pdf_file.open('rb')
                response = HttpResponse(invoice.pdf_file.read(), content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="invoice_{invoice.invoice_number}.pdf"'
                invoice.pdf_file.close()
                return response

            # 📊 CSV Export
            elif export_type == 'csv':
                output = io.StringIO()
                writer = csv.writer(output)
                '''
                writer.writerow(['Description', 'Service Type', 'Material Name', 'Quantity', 'Unit Price', 'Service Duration', 'Duration Unit', 'Service Rate', 'Total'])

                for item in invoice.items.all():
                    material_cost = float(item.quantity) * float(item.unit_price)
                    service_cost = float(item.service_duration) * float(item.service_rate)
                    item_total = material_cost + service_cost
                    writer.writerow([
                        item.quote_description,
                        item.service_type,
                        item.material_name or '',
                        item.quantity,
                        item.unit_price,
                        item.service_duration,
                        item.duration_unit,
                        item.service_rate,
                        item_total
                    ])
                '''
                writer.writerow(['Description', 'Quantity', 'Unit Price', 'Total'])

                for item in invoice.items.all():
                    total = float(item.quantity) * float(item.unit_price)
                    writer.writerow([
                        item.quote_description,
                        item.quantity,
                        item.unit_price,
                        total
                    ])
                # ✅ Save CSV to client folder
                csv_filename = f"invoice_{invoice.invoice_number}.csv"
                invoice.csv_file.save(csv_filename, ContentFile(output.getvalue()), save=True)
                response = HttpResponse(output.getvalue(), content_type='text/csv')
                # response['Content-Disposition'] = f'attachment; filename="invoice_{invoice.invoice_number}.csv"'
                response['Content-Disposition'] = f'attachment; filename="{csv_filename}"'
                return response

            # 📊 Excel Export
            elif export_type == 'excel':
                data = []
                '''
                for item in invoice.items.all():
                    material_cost = float(item.quantity) * float(item.unit_price)
                    service_cost = float(item.service_duration) * float(item.service_rate)
                    item_total = material_cost + service_cost
                    data.append({
                        'Description': item.quote_description,
                        'Service Type': item.service_type,
                        'Material Name': item.material_name or '',
                        'Quantity': item.quantity,
                        'Unit Price': item.unit_price,
                        'Service Duration': item.service_duration,
                        'Duration Unit': item.duration_unit,
                        'Service Rate': item.service_rate,
                        'Total': item_total
                    })
                '''
                for item in invoice.items.all():
                    total = float(item.quantity) * float(item.unit_price)
                    data.append({
                        'Description': item.quote_description,
                        'Quantity': item.quantity,
                        'Unit Price': item.unit_price,
                        'Total': total
                    })

                df = pd.DataFrame(data)
                output = io.BytesIO()
                df.to_excel(output, index=False, engine='openpyxl')
                output.seek(0)
                    # ✅ Save Excel file to client folder
                excel_filename = f"invoice_{invoice.invoice_number}.xlsx"
                invoice.excel_file.save(excel_filename, ContentFile(output.getvalue()), save=True)
                response = HttpResponse(
                    output.getvalue(),
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
                # response['Content-Disposition'] = f'attachment; filename="invoice_{invoice.invoice_number}.xlsx"'
                response['Content-Disposition'] = f'attachment; filename="{excel_filename}"'
                return response

            return self.error_response("Invalid export type", status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"Export error: {str(e)}")
            return self.error_response(f"Failed to export invoice: {str(e)}", status.HTTP_500_INTERNAL_SERVER_ERROR)

#I think it's not necessary for the project requirments, but doing it to see if the statistics is ok 
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get invoice statistics for dashboard"""
        try:
            invoices = self.get_queryset()
            stats = {
                'total': invoices.count(),
                'draft': invoices.filter(quote_status='draft').count(),  # ✅ CORRECT
                'sent': invoices.filter(quote_status='sent').count(),  # ✅ CORRECT
                'paid': invoices.filter(payment_status='paid').count(),  # ✅ CORRECT
                'overdue': invoices.filter(payment_status='overdue').count(),  # ✅ CORRECT
                'total_value': invoices.aggregate(total=Sum('total'))['total'] or 0,
                'paid_value': invoices.filter(payment_status='paid').aggregate(paid=Sum('total'))['paid'] or 0,  # ✅ CORRECT
            }
            return self.success_response(stats, "Statistics fetched successfully")
        except Exception as e:
            logger.error(f"Statistics error: {str(e)}")
            return self.error_response("Failed to fetch statistics", status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], url_path='upload-pdf')
    def upload_pdf(self, request, pk=None):
        """
        Frontend sends generated PDF → backend stores it and emails it.
        POST /quoteapp/invoices/{id}/upload-pdf/
        Form-data: pdf_file (file), send_email (bool, optional)
        """
        try:
            invoice = self.get_object()
            pdf_file = request.FILES.get('pdf_file')
            if not pdf_file:
                return self.error_response("pdf_file is required", status.HTTP_400_BAD_REQUEST)

            # Store PDF
            invoice.pdf_file.save(
                f"invoice_{invoice.invoice_number}.pdf",
                ContentFile(pdf_file.read()),
                save=True
            )
            invoice.pdf_generated_at = timezone.now()
            invoice.can_edit = False
            invoice.save(update_fields=['pdf_generated_at', 'can_edit'])

            # Optionally send email
            send_email = request.data.get('send_email', 'false').lower() == 'true'
            if send_email and invoice.client.email:
                payment_section = ""
                if invoice.payment_link:
                        payment_section = f"""
                Payment Link:
                {invoice.payment_link}
                """
                email_body = f"""
                Dear {invoice.client.name},

                Please find attached Invoice #{invoice.invoice_number}.
                Total Amount: £{invoice.total}
                
                {payment_section}

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
                #{'pdf_url': invoice.pdf_file.url},
                {'pdf_url': f"{settings.BASE_URL}{invoice.pdf_file.url}"},
                "PDF uploaded and email sent" if send_email else "PDF uploaded successfully"
            )
        except Exception as e:
            logger.error(f"PDF upload error: {str(e)}")
            return self.error_response(f"Failed to upload PDF: {str(e)}", status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='financial-statistics')
    def financial_statistics(self, request):
        """
        GET /quoteapp/invoices/financial-statistics/?period=monthly&year=2026&month=2
        GET /quoteapp/invoices/financial-statistics/?period=weekly&year=2026&week=8
        GET /quoteapp/invoices/financial-statistics/?period=yearly&year=2026
        GET /quoteapp/invoices/financial-statistics/  (all time)
        """
        try:
            from django.db.models import Sum, Count, Q
            from django.utils.timezone import now
            import datetime

            invoices = self.get_queryset()  # already filtered by user & not deleted
            period = request.query_params.get('period')  # monthly | weekly | yearly | None
            year = request.query_params.get('year')
            month = request.query_params.get('month')
            week = request.query_params.get('week')

            today = now().date()

            # --- Apply period filter ---
            if period == 'yearly' and year:
                invoices = invoices.filter(issue_date__year=int(year))

            elif period == 'monthly' and year and month:
                invoices = invoices.filter(
                    issue_date__year=int(year),
                    issue_date__month=int(month)
                )

            elif period == 'weekly' and year and week:
                invoices = invoices.filter(
                    issue_date__iso_year=int(year),
                    issue_date__week=int(week)
                )

            # --- Aggregations ---
            totals = invoices.aggregate(
                total_invoices=Count('invoice_id'),
                total_amount=Sum('total'),
                paid_amount=Sum('total', filter=Q(payment_status='paid')),
                unpaid_amount=Sum('total', filter=Q(payment_status='unpaid')),
                overdue_amount=Sum('total', filter=Q(payment_status='overdue')),
            )

            stats = {
                'period': period or 'all_time',
                'filters': {
                    'year': year,
                    'month': month,
                    'week': week,
                },
                'total_invoices': totals['total_invoices'] or 0,
                'total_amount': float(totals['total_amount'] or 0),
                'paid_amount': float(totals['paid_amount'] or 0),
                'unpaid_amount': float(totals['unpaid_amount'] or 0),
                'overdue_amount': float(totals['overdue_amount'] or 0),
                'paid_count': invoices.filter(payment_status='paid').count(),
                'unpaid_count': invoices.filter(payment_status='unpaid').count(),
                'overdue_count': invoices.filter(payment_status='overdue').count(),
                'manual_count': invoices.filter(source='manual').count(),
                'voice_count': invoices.filter(source='voice').count(),
            }

            return self.success_response(stats, "Financial statistics fetched successfully")

        except Exception as e:
            logger.error(f"Financial statistics error: {str(e)}")
            return self.error_response(f"Failed to fetch financial statistics: {str(e)}", status.HTTP_500_INTERNAL_SERVER_ERROR)

stripe.api_key = settings.STRIPE_SECRET_KEY

def payment_success_view(request):
    session_id = request.GET.get('session_id')
    invoice_id = request.GET.get('invoice_id')#claude-2nd

    if not session_id:
        return HttpResponse("<h3>Session ID missing.</h3>", status=400)
    
    try:
        '''
        invoice = Invoice.objects.get(invoice_id=invoice_id)
        session = stripe.checkout.Session.retrieve(session_id)
        invoice_id = session.metadata.get('invoice_id')  # ✅ retrieve from metadata
        connected_id = invoice.user.business_profile.stripe_account_id
        '''
        # Extract invoice_id from session_id URL parameter first
        #invoice_id = request.GET.get('invoice_id')#claude 1st

        invoice = Invoice.objects.get(invoice_id=invoice_id)#claude-2nd

        '''
        if invoice_id:
            # Direct method - get invoice from URL
            invoice = Invoice.objects.get(invoice_id=invoice_id)
        else:
            # Fallback - retrieve from Stripe session
            # ✅ FIX: Retrieve using connected account
            invoice = Invoice.objects.filter(payment_link__contains=session_id).first()
            if not invoice:
                return HttpResponse("<h3>Invoice not found</h3>", status=404)
            
            account_id = invoice.user.business_profile.stripe_account_id
            session = stripe.checkout.Session.retrieve(
                session_id,
                stripe_account=account_id  # ✅ ADD THIS
            )
            invoice_id = session.metadata.get('invoice_id')
            invoice = Invoice.objects.get(invoice_id=invoice_id)

        if invoice.is_paid:
            return HttpResponse(f"""
                <!DOCTYPE html>
                <html>
                <head><title>Payment Successful</title></head>
                <body style="font-family: Arial; text-align: center; padding: 50px;">
                    <h1 style="color: green;">✅ Payment Successful!</h1>
                    <p>Invoice <strong>#{invoice.invoice_number}</strong> has been paid.</p>
                    <p>Amount: <strong>£{invoice.total}</strong></p>
                    <p>You will receive a confirmation email shortly.</p>
                </body>
                </html>
            """)
        else:
            return HttpResponse("""
                <h1 style="color: orange;">⏳ Payment Processing...</h1>
                <p>Your payment is being verified. Please check your email.</p>
            """)
        '''

        if not invoice.is_paid:#means “if the invoice is not already paid” — so it updates it to paid only once (to avoid re-saving or overwriting an already-paid invoice).
            invoice.is_paid = True
            invoice.payment_status = 'paid'
            invoice.paid_date = timezone.now().date()
            invoice.save()
            # ✅ TRIGGER NOTIFICATION HERE
            notify_invoice_paid(invoice)
            # send_fcm_notification(
            #     user=invoice.user,
            #     title="Payment Received! 💰",
            #     body=f"£{invoice.total} received for Invoice #{invoice.invoice_number}",
            #     notification_type='payment_completed',
            #     extra_data={'invoice_id': str(invoice.invoice_id)}
            # )
            # Update related quote if exists
            if invoice.quote:
                invoice.quote.quote_status = 'won'
                invoice.quote.save()
            # ✅ Send email to both owner and client
            subject = f"Payment Confirmation – Invoice #{invoice.invoice_number}"
            message = f"""
            Good News!
            The payment for Invoice #{invoice.invoice_number} (£{invoice.total}) has been successfully completed.

            Client: {invoice.client.name}
            Date: {invoice.paid_date}

            Thank you for your business.Keep Stay with us.
            """
            recipients = [invoice.user.email, invoice.client.email]
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipients)        
        return HttpResponse(f"""
            <!DOCTYPE html>
            <html>
            <head><title>Payment Successful</title></head>
            <body style="font-family: Arial; text-align: center; padding: 50px;">
                <h1 style="color: green;">✅ Payment Successful!</h1>
                <p>Invoice <strong>#{invoice.invoice_number}</strong> has been paid.</p>
                <p>Amount: <strong>£{invoice.total}</strong></p>
                <p>You will receive a confirmation email shortly.</p>
            </body>
            </html>
        """)
        
    except Invoice.DoesNotExist:
        return HttpResponse("<h3>❌ Invoice not found</h3>", status=404)
        
    
    except Exception as e:
        logger.error(f"Payment success error: {e}")
        return HttpResponse(f"<h3>❌ Error: {e}</h3>", status=400)
    

@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return HttpResponse(status=400)
    
    # ✅ Listen to charge.succeeded instead
    '''
    if event['type'] == 'charge.succeeded':
        charge = event['data']['object']
        invoice_id = charge.get('metadata', {}).get('invoice_id')
    '''
    #this below 3 lines added by gork
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        invoice_id = session.get('metadata', {}).get('invoice_id')
        
        if invoice_id:
            try:
                invoice = Invoice.objects.get(invoice_id=invoice_id)
                if not invoice.is_paid:
                    invoice.is_paid = True
                    invoice.payment_status = 'paid'
                    invoice.paid_date = timezone.now().date()
                    invoice.save()

                    # ✅ TRIGGER NOTIFICATION HERE
                    notify_invoice_paid(invoice)
                    logger.info(f"Invoice {invoice_id} marked paid")
            except Invoice.DoesNotExist:
                logger.error(f"Invoice {invoice_id} not found")
    
    return HttpResponse(status=200)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_invoice_from_quote(request, quote_id):
    """
    Create invoice from accepted quote
    Special endpoint for quote-to-invoice workflow
    """
    try:
        quote = get_object_or_404(Quote, quote_id=quote_id, user=request.user)
        
        if quote.quote_status != 'won':
            return Response({
                "success": False,
                "statusCode": 400,
                "message": "Can only create invoice from accepted quote",
                "data": None,
                "timestamp": timezone.now().isoformat()
            }, status=400)
        
        # Check if invoice already exists for this quote
        if Invoice.objects.filter(quote=quote).exists():
            return Response({
                "success": False,
                "statusCode": 400,
                "message": "Invoice already exists for this quote",
                "data": None,
                "timestamp": timezone.now().isoformat()
            }, status=400)
        
        with transaction.atomic():
            # Create invoice from quote data
            invoice = Invoice.objects.create(
                user=request.user,
                client=quote.client,
                quote=quote,
                source=quote.source,
                folder=quote.folder,
                # Copy financial data
                subtotal=quote.subtotal,
                discount_amount=quote.discount_amount,
                discount_type=quote.discount_type,
                vat_rate=quote.vat_rate,
                total=quote.total,
                issue_date=timezone.now().date(),
                due_date=quote.due_date.strftime('%Y-%m-%d') if hasattr(quote.due_date, 'strftime') else quote.due_date,
                # service_location=quote.effective_service_location,
                #payment_link=f"{settings.BASE_URL}/payment/{quote.quote_id}"  # Placeholder
                # payment_link=f"{settings.BASE_URL}/payment/{invoice.invoice_id}"

            )
            
            '''
            # Copy quote items to invoice items
            for quote_item in quote.items.all():
                InvoiceItem.objects.create(
                    invoice=invoice,
                    quote_description=quote_item.quote_description,  # ADD THIS
                    material_name=quote_item.material_name,
                    quantity=quote_item.quantity,
                    unit_price=quote_item.unit_price,
                    # amount=quote_item.amount,  # Already calculated
                    # amount=(quote_item.quantity * quote_item.unit_price) + (quote_item.service_duration * quote_item.service_rate),
                    service_duration=quote_item.service_duration,
                    service_type=quote_item.service_type,
                    service_rate=quote_item.service_rate,
                    duration_unit=quote_item.duration_unit,
                    # freeze_totals=True  # ✅ prevent recalculation

                )
            
        # ❌ Do NOT call calculate_amounts() here
        # invoice.calculate_amounts()
        # invoice.save()
        InvoiceItem.save(freeze_totals=True)  # ✅ pass it here
        serializer = InvoiceSerializer(invoice)
            
            '''
        for quote_item in quote.items.all():
            item = InvoiceItem(
                invoice=invoice,
                quote_description=quote_item.quote_description,
                material_name=quote_item.material_name,
                quantity=quote_item.quantity,
                unit_price=quote_item.unit_price,
                service_duration=quote_item.service_duration,
                service_type=quote_item.service_type,
                service_rate=quote_item.service_rate,
                duration_unit=quote_item.duration_unit
            )
            item.save(freeze_totals=True)  # ✅ pass freeze_totals here

        serializer = InvoiceSerializer(invoice)


        payment_link = create_stripe_payment_link(invoice)
        if payment_link:
            invoice.payment_link = payment_link
            invoice.save()
            logger.info(f"✅ Payment link created: {payment_link}")  # ADD THIS
        else:
            logger.error(f"❌ Failed to create payment link for invoice {invoice.invoice_id}")  # ADD THIS
        serializer = InvoiceSerializer(invoice)

        return Response({
            "success": True,
            "statusCode": 201,
            "message": "Invoice created from quote successfully",
            "data": serializer.data,
            "timestamp": timezone.now().isoformat()
        }, status=201)
        
    except Exception as e:
        logger.error(f"Invoice from quote error: {str(e)}")
        return Response({
            "success": False,
            "statusCode": 500,
            "message": f"Failed to create invoice from quote {e}",
            "data": None,
            "timestamp": timezone.now().isoformat()
        }, status=500)



#previous webhook
'''
#previous webhook handler which is used for n8n purpose
@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])  # n8n will call this, so no auth needed
def quote_accept_reject_webhook(request):
    """
    Webhook endpoint for n8n to update quote status when client clicks accept/reject
    This is called from the email links sent by n8n
    """
    try:
        data = request.data
        quote_id = data.get('quote_id')
        action = data.get('action')  # 'accept' or 'reject'
        
        if not quote_id or not action:
            return Response(
                {'error': 'quote_id and action are required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Find and update quote
        try:
            quote = Quote.objects.get(quote_id=quote_id)
        except Quote.DoesNotExist:
            return Response(
                {'error': 'Quote not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Update quote status based on action
        if action == 'accept':
            quote.status = 'won'
            # Create ClientService record when quote is accepted
            ClientService.objects.create(
                client=quote.client,
                quote=quote,
                quote_accepted_date=timezone.now().date(),
                amount=quote.total,
                notes=f"Quote #{quote.quote_id} accepted via email"
            )
        elif action == 'reject':
            quote.status = 'lost'
        else:
            return Response(
                {'error': 'Invalid action. Must be "accept" or "reject"'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        quote.save()
        
        # Send update back to n8n for HubSpot sync and further processing
        webhook_data = {
            'quote_id': quote.quote_id,
            'status': quote.status,
            'action': action,
            'timestamp': timezone.now().isoformat(),
            'client_name': quote.client.name,
            'client_email': quote.client.email,
            'total_amount': float(quote.total)
        }
        
        # If accepted, trigger invoice generation
        if action == 'accept':
            n8n_client.send_webhook('quote-accepted-generate-invoice', webhook_data)
        else:
            n8n_client.send_webhook('quote-rejected', webhook_data)
        
        return Response({'success': True, 'status': quote.status})
        
    except Exception as e:
        logger.error(f"Error in quote accept/reject webhook: {str(e)}")
        return Response(
            {'error': 'Internal server error'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
   
'''
     

# Webhook Handler
@api_view(['POST'])
@permission_classes([AllowAny])  # Public endpoint
def quote_webhook_handler(request, action, quote_id):
    """
    Webhook handler for client quote actions (accept/reject)
    Called when client clicks email links
    """
    try:
        quote = get_object_or_404(Quote, quote_id=quote_id)

        if action == 'accept':
            if quote.quote_status != 'sent':
                return Response({
                    "success": False,
                    "statusCode": 400,
                    "message": f"Cannot accept quote with status: {quote.quote_status}",
                    "data": None,
                    "timestamp": timezone.now().isoformat()
                }, status=400)

            quote.quote_status = 'won'
            quote.save()
            message = "Quote accepted successfully"
            # ✅ TRIGGER NOTIFICATION HERE
            notify_quote_accepted(quote)

        elif action == 'reject':
            quote.quote_status = 'lost'
            quote.save()
            message = "Quote rejected"

        else:
            return Response({
                "success": False,
                "statusCode": 400,
                "message": "Invalid action. Use 'accept' or 'reject'",
                "data": None,
                "timestamp": timezone.now().isoformat()
            }, status=400)

        return Response({
            "success": True,
            "statusCode": 200,
            "message": message,
            "data": {
                "quote_id": quote.quote_id,
                "status": quote.quote_status,
                "client_name": quote.client.name
            },
            "timestamp": timezone.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Quote webhook error: {str(e)}")
        return Response({
            "success": False,
            "statusCode": 500,
            "message": "Internal server error",
            "data": None,
            "timestamp": timezone.now().isoformat()
        }, status=500)


@api_view(['GET'])
@permission_classes([AllowAny])  # Public endpoint
def payment_redirect_view(request, invoice_id):
    invoice = get_object_or_404(Invoice, invoice_id=invoice_id)
    
    if not invoice.payment_link:
        return HttpResponse("<h3>No payment link available for this invoice.</h3>", status=404)
    
    # Redirect user to Stripe Checkout URL
    return redirect(invoice.payment_link)


#-----------------------------------------------------------------------------------------------------------------------

class NewQuoteCreateView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, JSONParser]

    def post(self, request):
        try:
            serializer = NewQuoteCreateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data

            try:
                client = Client.objects.get(id=data['client'], user=request.user)
            except Client.DoesNotExist:
                return self.error_response("Client not found", 404)

            folder = ensure_client_folder(request.user, client)

            with transaction.atomic():
                year = timezone.now().year
                counter_obj, _ = QuoteCounter.objects.select_for_update().get_or_create(
                    user=request.user, year=year
                )
                counter_obj.counter += 1
                counter_obj.save()
                short_uid = str(request.user.id)[:4]
                quote_number = f"QT-{short_uid}-{year}-{counter_obj.counter:02d}"

                quote = Quote.objects.create(
                    user=request.user,
                    client=client,
                    folder=folder,
                    vat_rate=data['vat_rate'],
                    issue_date=data['issue_date'],
                    due_date=data['due_date'],
                    quote_number=quote_number,
                    subtotal=Decimal('0.00'),
                    total=Decimal('0.00'),
                    discount_amount=Decimal('0.00'),
                )

                for item in data['items']:
                    QuoteItem.objects.create(
                        quote=quote,
                        quote_description=item['quote_description'],
                        quantity=item['quantity'],
                        unit_price=item['unit_price'],
                        service_duration=0,
                        service_rate=0,
                    )

                # Recalculate: subtotal = sum(qty * unit_price)
                quote.refresh_from_db()
                items = quote.items.all()
                subtotal = sum(i.quantity * i.unit_price for i in items)
                vat_amount = subtotal * (quote.vat_rate / Decimal('100'))
                quote.subtotal = subtotal
                quote.total = subtotal + vat_amount
                quote.save(update_fields=['subtotal', 'total'])
                # ✅ Generate accept/reject links with token
                quote_token = QuoteToken.objects.create(
                    quote=quote,
                    expires_at=timezone.now() + timedelta(days=30)
                )
                quote.accept_link = f"{settings.BASE_URL}/quoteapp/quotes/{quote.quote_id}/accept/?token={quote_token.token}"
                quote.reject_link = f"{settings.BASE_URL}/quoteapp/quotes/{quote.quote_id}/reject/?token={quote_token.token}"
                quote.save(update_fields=['accept_link', 'reject_link'])
                '''
                #if we want to make the quote status always 'sent' after creating a quote 

                quote.quote_status = 'sent'  # ← ADD THIS LINE
                quote.save(update_fields=['accept_link', 'reject_link', 'quote_status'])  # ← add quote_status here
                '''
                
            quote = Quote.objects.prefetch_related('items').get(pk=quote.pk)
            response_serializer = NewQuoteResponseSerializer(quote, context={'request': request})
            return self.success_response(response_serializer.data, "Quote created successfully", 201)

        except Exception as e:
            return self.error_response(f"Failed to create quote: {e}", 500)


#--------------------------------------------------------------------------


class NewInvoiceCreateView(StandardResponseMixin, APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, JSONParser]

    def post(self, request):
        try:
            serializer = NewInvoiceCreateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data

            try:
                client = Client.objects.get(id=data['client'], user=request.user)
            except Client.DoesNotExist:
                return self.error_response("Client not found", 404)

            connected_id = request.user.business_profile.stripe_account_id if hasattr(request.user, 'business_profile') else None
            if not connected_id:
                return self.error_response("Complete Stripe onboarding first", 400)

            folder = ensure_client_folder(request.user, client)

            with transaction.atomic():
                year = timezone.now().year
                counter_obj, _ = InvoiceCounter.objects.select_for_update().get_or_create(
                    user=request.user, year=year
                )
                counter_obj.counter += 1
                counter_obj.save()
                short_uid = str(request.user.id)[:4]
                invoice_number = f"INV-{short_uid}-{year}-{counter_obj.counter:02d}"

                invoice = Invoice.objects.create(
                    user=request.user,
                    client=client,
                    folder=folder,
                    vat_rate=data['vat_rate'],
                    issue_date=data['issue_date'],
                    due_date=data['due_date'],
                    invoice_number=invoice_number,
                    subtotal=Decimal('0.00'),
                    total=Decimal('0.00'),
                    discount_amount=Decimal('0.00'),
                    bank_name=data.get('bank_name', ''),
                    account_name=data.get('account_name', ''),
                    sort_code=data.get('sort_code', ''),
                    account_no=data.get('account_no', ''),
                    payment_status='unpaid',
                )

                for item in data['items']:
                    InvoiceItem.objects.create(
                        invoice=invoice,
                        quote_description=item['quote_description'],
                        quantity=item['quantity'],
                        unit_price=item['unit_price'],
                        service_duration=0,
                        service_rate=0,
                    )

                invoice.refresh_from_db()
                items = invoice.items.all()
                subtotal = sum(i.quantity * i.unit_price for i in items)
                vat_amount = subtotal * (invoice.vat_rate / Decimal('100'))
                invoice.subtotal = subtotal
                invoice.total = subtotal + vat_amount
                invoice.save(update_fields=['subtotal', 'total'])

                payment_link = create_stripe_payment_link(invoice)
                if not payment_link:
                    raise Exception("Stripe payment link creation failed")

                invoice.payment_link = payment_link
                invoice.save(update_fields=['payment_link'])
                # if payment_link:
                #     invoice.payment_link = payment_link
                #     invoice.save(update_fields=['payment_link'])

            invoice = Invoice.objects.prefetch_related('items').get(pk=invoice.pk)
            response_serializer = NewInvoiceResponseSerializer(invoice, context={'request': request})
            return self.success_response(response_serializer.data, "Invoice created successfully", 201)

        except Exception as e:
            return self.error_response(f"Failed to create invoice: {e}", 500)