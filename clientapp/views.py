

from django.db.models import Prefetch, Count, Sum

from quoteapp.models import Quote
# clientapp/views.py
"""
ClientApp Views - Optimized for performance and maintainability
Handles client management, service tracking, and contact imports
"""

import logging
from datetime import timedelta

from django.utils import timezone
from django.db import transaction
from django.db.models import (
    Q, Count, Sum, Prefetch, F, Value, 
    DecimalField, Max
)
from django.db.models.functions import Coalesce
from django.core.cache import cache
from django.http import Http404

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, JSONParser
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination

from .models import Client, ClientService
from .serializers import (
    ClientListSerializer,
    ClientDetailSerializer,
    ClientCreateUpdateSerializer,
    ClientImportSerializer,
    ClientServiceSerializer,
    ClientSearchSerializer,
    ClientQuoteSummarySerializer,
    ClientInvoiceSummarySerializer,
    ClientServiceSummarySerializer

)

logger = logging.getLogger(__name__)


class StandardPagination(PageNumberPagination):
    """Standard pagination for all viewsets"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


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
# Client ViewSet
# ---------------------------
class ClientViewSet(StandardResponseMixin, viewsets.ModelViewSet):
    """
    Client CRUD operations with advanced optimization
    - Prevents N+1 queries with select_related and prefetch_related
    - Handles manual creation and contact imports
    - Auto-creates folder structures
    - Implements caching for frequently accessed data
    """
    
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, JSONParser]
    pagination_class = StandardPagination
    
    def get_serializer_class(self):
        """
        Dynamic serializer selection based on action
        Optimizes data transfer by using lighter serializers for lists
        """
        if self.action == 'list':
            return ClientListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return ClientCreateUpdateSerializer
        elif self.action == 'import_from_contact':
            return ClientImportSerializer
        elif self.action == 'search':
            return ClientSearchSerializer
        return ClientDetailSerializer

    def get_queryset(self):
        """
        Highly optimized queryset to prevent N+1 queries
        - select_related: Fetches related user in single query
        - prefetch_related: Optimizes related object fetching
        - annotate: Adds computed fields at database level
        """
        # Import here to avoid circular dependency
        from quoteapp.models import Quote, Invoice
        
        # Build optimized queryset with all necessary joins
        '''
❓❓❓What to use-
⚙️ Option 1: order_by('-quote__sent_at')

Pros

Keeps ordering aligned with the actual quote sent date (chronologically correct).
Useful if you ever edit Quote.sent_at manually.

Cons

Adds a SQL join between ClientService → Quote, which is slightly slower.

If any quote is NULL or missing, ordering can behave unexpectedly.

⚙️ Option 2: order_by('-id') ✅ (your idea)

Pros

Simple and efficient — uses the table’s own primary key.
Works perfectly if your ClientService entries are created in the same order as quotes.
No joins = faster query.

Cons

It only represents the creation order of client services, not actual quote date order (if quotes are edited later).

💡 My recommendation:

If your use case is just “show the latest client services first,”
then yes — order_by('-id') is the cleanest and fastest choice.
        
        '''
        queryset = Client.objects.filter(
            user=self.request.user,
            is_deleted=False
        ).select_related(
            'user'  # Single JOIN for user data
        ).prefetch_related(
            # Optimize service fetching with quote data
            Prefetch(
                'services',
                queryset=ClientService.objects.select_related('quote').order_by('-quote__sent_at')#can also user here ('-id')
                    # .order_by('-quote_sent_date') #❌can't use a @property in a .filter(), .order_by(), .annotate(), .values()
                    #will get error like: Cannot resolve keyword 'quote_sent_date' into field.
            ),

            # Optimize quote fetching
            Prefetch(
                'quotes',
                queryset=Quote.objects.filter(is_deleted=False)
                    .select_related('folder') #whatever present in select_related(), .only should be contain it
                    .only('quote_id', 'total', 'quote_status', 'created_at','folder')
            ),
            # Optimize invoice fetching
            Prefetch(
                'invoices',

                #removing because invoice model has no folder field

                # queryset=Invoice.objects.select_related('quote', 'folder')
                #     .only('invoice_id', 'invoice_number', 'total', 'status', 'created_at','quote','folder')

                queryset=Invoice.objects.select_related('quote')
                    .only('invoice_id', 'invoice_number', 'total', 'quote_status', 'created_at','quote')
            )
        ).annotate(
            total_services=Count('services', distinct=True),
            total_earnings=Coalesce(
                # Sum('services__amount'),❌ClientService model does not have any database field called 'amount',only 'amount_earned' present which is python property 
                Sum('services__quote__invoices__total'),
                Value(0),
                output_field=DecimalField()
            ),
            latest_service_date=Max('services__quote__sent_at'), # Use Max() for accuracy; F() may pick an arbitrary value if multiple services exist
            accepted_quotes_count=Count(
                'quotes',
                filter=Q(quotes__quote_status='won', quotes__is_deleted=False),
                #quotes is a reverse relation from Client → Quote (ManyToOneRel).
                # if I use quotes__status='won', then 
                # ❌Erro: django.core.exceptions.FieldError: Unsupported lookup 'status' for ManyToOneRel or join on the field not permitted.
                distinct=True
            )
        ).order_by('-created_at')
        
        
        return queryset
    
    def get_serializer_context(self):
        """
        Pass request context to serializers (needed for validation)
        """
        context = super().get_serializer_context()
        context['request'] = self.request
        return context 
    
    def _client_list_version_key(self, user_id):
        return f"client_list_version_{user_id}"

    def _get_client_list_version(self, user_id):
        return cache.get(self._client_list_version_key(user_id), 1)

    def _bump_client_list_version(self, user_id):
        key = self._client_list_version_key(user_id)
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 2, None)     
    
    def list(self, request, *args, **kwargs):
        """
        List clients with advanced filtering and search
        Implements caching for frequently accessed lists
        """
        try:
            # Build cache key based on user and filters
            #cache_key = f"client_list_{request.user.id}_{request.GET.urlencode()}"
            version = self._get_client_list_version(request.user.id)
            cache_key = f"client_list_v{version}_{request.user.id}_{request.GET.urlencode()}"
            
            # Try to get from cache first
            cached_data = cache.get(cache_key)
            if cached_data and not request.GET.get('no_cache'):
                return self.success_response(
                    cached_data, 
                    "Clients fetched successfully (cached)"
                )
            
            # Build filtered queryset
            queryset = self.filter_queryset(self.get_queryset())
            
            # Apply search filter
            search_query = request.query_params.get('search')
            if search_query:
                queryset = queryset.filter(
                    Q(name__icontains=search_query) |
                    Q(email__icontains=search_query) |
                    Q(phone_number__icontains=search_query)
                )
            
            # Apply source filter
            source_filter = request.query_params.get('source')
            if source_filter in ['manual', 'imported']:
                queryset = queryset.filter(source=source_filter)
            
            # Apply service filter
            has_services = request.query_params.get('has_services')
            if has_services:
                if has_services.lower() == 'true':
                    queryset = queryset.filter(total_services__gt=0)
                else:
                    queryset = queryset.filter(total_services=0)
            
            # Apply date range filter
            date_from = request.query_params.get('date_from')
            date_to = request.query_params.get('date_to')
            if date_from:
                queryset = queryset.filter(created_at__gte=date_from)
            if date_to:
                queryset = queryset.filter(created_at__lte=date_to)
            
            # Paginate results
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                # Cache the result for 5 minutes
                cache.set(cache_key, serializer.data, 300)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(queryset, many=True)
            # Cache the result
            cache.set(cache_key, serializer.data, 300)
            
            return self.success_response(
                serializer.data,
                "Clients fetched successfully"
            )
            
        except Exception as e:
            logger.error(f"Client list error: {str(e)}", exc_info=True)
            return self.error_response(
                f"Failed to fetch clients: {str(e)}",
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def retrieve(self, request, *args, **kwargs):
        """
        Get single client with full details
        Uses detailed serializer with all related data
        """
        try:
            client = self.get_object()
            serializer = ClientDetailSerializer(client)
            return self.success_response(
                serializer.data,
                "Client details fetched successfully"
            )
        # except Client.DoesNotExist: ❌ because DRF's get_object() raises Http404, not Client.DoesNotExist.
        except Http404:
            return self.error_response(
                "Client not found",
                status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Client retrieve error: {str(e)}", exc_info=True)
            return self.error_response(
                f"Failed to fetch client details: {str(e)}",
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def create(self, request, *args, **kwargs):
        """
        Create new client with automatic folder creation
        Validates duplicates and creates filesystem structure
        """
        try:
            serializer = self.get_serializer(data=request.data)
            
            if not serializer.is_valid():
                print("VALIDATION ERRORS:", serializer.errors)  # ADD THIS
                return self.error_response(
                    "Validation failed",
                    status.HTTP_400_BAD_REQUEST,
                    serializer.errors
                )
            
            with transaction.atomic():
                print("ABOUT TO SAVE CLIENT")  # ADD THIS
                # Save client (folder creation handled in model's save method)
                client = serializer.save()
                print(f"CLIENT SAVED: {client.id}")  # ADD THIS
                # Re-query to include prefetched/annotated data
                client = self.get_queryset().get(id=client.id)               
                # Invalidate cache for this user
                #cache.delete_pattern(f"client_list_{request.user.id}_*")
                self._bump_client_list_version(request.user.id)
                cache.delete(f"client_stats_{request.user.id}")
                
                # Return detailed client data
                ##detail_serializer = ClientDetailSerializer(client)
                detail_serializer = ClientDetailSerializer(client, context={'request': request})
                
            return self.success_response(
                detail_serializer.data,
                "Client created successfully",
                status.HTTP_201_CREATED
            )
            
        except ValidationError as e:
            return self.error_response(
                str(e),
                status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            import traceback
            print("FULL ERROR:")  # ADD THIS
            print(traceback.format_exc())  # ADD THIS
            logger.error(f"Client creation error: {str(e)}", exc_info=True)
            return self.error_response(
                f"Failed to create client: {str(e)}", 
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    def update(self, request, *args, **kwargs):
        """
        Update client with folder rename if name changes
        Handles partial updates efficiently
        """
        try:
            client = self.get_object()
            partial = kwargs.pop('partial', False)
            serializer = self.get_serializer(
                client,
                data=request.data,
                partial=partial
            )
            
            if not serializer.is_valid():
                return self.error_response(
                    "Validation failed",
                    status.HTTP_400_BAD_REQUEST,
                    serializer.errors
                )
            
            with transaction.atomic():
                # Save updates (folder rename handled in serializer)
                client = serializer.save()
                # Re-query to include prefetched/annotated data
                client = self.get_queryset().get(id=client.id)          
                # Invalidate cache
                #cache.delete_pattern(f"client_list_{request.user.id}_*")
                self._bump_client_list_version(request.user.id)
                cache.delete(f"client_stats_{request.user.id}")
                cache.delete(f"client_detail_{client.id}")
                
                # Return detailed client data
                # detail_serializer = ClientDetailSerializer(client)
                detail_serializer = ClientDetailSerializer(client, context={'request': request}) # FOR request.buildabsolute url image
            
            return self.success_response(
                detail_serializer.data,
                "Client updated successfully"
            )
            
        # except Client.DoesNotExist: ❌ because DRF's get_object() raises Http404, not Client.DoesNotExist.
        except Http404:
            return self.error_response(
                "Client not found",
                status.HTTP_404_NOT_FOUND
            )
        except ValidationError as e:
            return self.error_response(
                str(e),
                status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Client update error: {str(e)}", exc_info=True)
            return self.error_response(
                # "Failed to update client",
                f"Failed to update client: {str(e)}", 
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'], url_path='check-exists')
    def check_exists(self, request):
        """
        Check if client exists by phone/email
        Used by Flutter app before importing contacts
        """
        try:
            phone_number = request.data.get('phone_number')
            email = request.data.get('email')
            
            if not phone_number and not email:
                return self.error_response(
                    "Phone number or email is required",
                    status.HTTP_400_BAD_REQUEST
                )
            
            # Build query
            query = Q(user=request.user, is_deleted=False)
            if phone_number:
                query &= Q(phone_number=phone_number)
            if email:
                query &= Q(email=email)
            
            # Check existence
            client = Client.objects.filter(query).first()
            
            if client:
                serializer = ClientListSerializer(client)
                return self.success_response(
                    {
                        "exists": True,
                        "client": serializer.data
                    },
                    "Client found"
                )
            else:
                # return self.error_response(
                #     {
                #         "exists": False,
                #         "client": None
                #     },
                #     "Client not found",
                #     status.HTTP_404_NOT_FOUND   # ✅ Use 404, not 500                
                #     )
                return self.error_response(
                    "Client not found",
                    status.HTTP_404_NOT_FOUND,
                    data={"exists": False, "client": None}
                )
            
        except Exception as e:
            logger.error(f"Client existence check error: {str(e)}", exc_info=True)
            return self.error_response(
                # "Failed to check client existence",
                f"Failed to check client existence: {str(e)}", 
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
    @action(detail=False, methods=['post'], url_path='import-from-contact')
    def import_from_contact(self, request):
        """
        Import client from phone contacts
        Validates and creates client with 'imported' source
        """
        try:
            # Validate required fields
            if not request.data.get('name'):
                return self.error_response(
                    "Client name is required",
                    status.HTTP_400_BAD_REQUEST
                )
            
            if not request.data.get('phone_number'):
                return self.error_response(
                    "Phone number is required",
                    status.HTTP_400_BAD_REQUEST
                )
            
            serializer = ClientImportSerializer(
                data=request.data,
                context={'request': request}
            )
            
            if not serializer.is_valid():
                return self.error_response(
                    "Validation failed",
                    status.HTTP_400_BAD_REQUEST,
                    serializer.errors
                )
            
            with transaction.atomic():
                # Create client with imported source
                client_data = serializer.validated_data
                client_data['user'] = request.user
                client = Client.objects.create(**client_data)
                
                # Invalidate cache
                #cache.delete_pattern(f"client_list_{request.user.id}_*")
                self._bump_client_list_version(request.user.id)
                cache.delete(f"client_stats_{request.user.id}")
                                
                # Return detailed client data
                #detail_serializer = ClientDetailSerializer(client)
                detail_serializer = ClientDetailSerializer(client, context={'request': request})
            
            return self.success_response(
                detail_serializer.data,
                "Client imported successfully from contact",
                status.HTTP_201_CREATED
            )
            
        except ValidationError as e:
            return self.error_response(
                str(e),
                status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Client import error: {str(e)}", exc_info=True)
            return self.error_response(
                # "Failed to import client from contact",
                f"Failed to import client from contact: {str(e)}", 
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )
      
      
    @action(detail=False, methods=['post'], url_path='bulk-check')
    def bulk_check(self, request):
        """
        Check multiple contacts at once for efficiency
        Optimized for batch contact imports
        """
        try:
            contacts = request.data.get('contacts', [])
            
            if not contacts:
                return self.error_response(
                    "Contacts list is required",
                    status.HTTP_400_BAD_REQUEST
                )
            
            # Limit batch size to prevent abuse
            if len(contacts) > 100:
                return self.error_response(
                    "Maximum 100 contacts allowed per request",
                    status.HTTP_400_BAD_REQUEST
                )
            
            # Collect all phone numbers and emails
            phone_numbers = [c.get('phone_number') for c in contacts if c.get('phone_number')]
            emails = [c.get('email') for c in contacts if c.get('email')]
            
            # Single query to check all contacts
            existing_clients = Client.objects.filter(
                user=request.user,
                is_deleted=False
            ).filter(
                Q(phone_number__in=phone_numbers) |
                Q(email__in=emails)
            ).values('phone_number', 'email')
            
            # Build lookup sets for O(1) checking
            existing_phones = {c['phone_number'] for c in existing_clients if c['phone_number']}
            existing_emails = {c['email'] for c in existing_clients if c['email']}
            
            # Check each contact
            results = []
            for contact in contacts:
                phone = contact.get('phone_number')
                email = contact.get('email')
                
                exists = (phone in existing_phones) or (email and email in existing_emails)
                
                results.append({
                    "phone_number": phone,
                    "email": email,
                    "exists": exists
                })
            
            return self.success_response(
                {"results": results},
                "Bulk client check completed"
            )
            
        except Exception as e:
            logger.error(f"Bulk client check error: {str(e)}", exc_info=True)
            return self.error_response(
                # "Failed to perform bulk client check",
                f"Failed to perform bulk client check: {str(e)}", 
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    #client search by his name       
    @action(detail=False, methods=['get'])
    def search(self, request):
        """
        Fast search endpoint for client lookup
        Returns minimal data for quick results
        """
        try:
            query = request.query_params.get('q', '').strip()
            
            if not query:
                return self.error_response(
                    "Search query is required",
                    status.HTTP_400_BAD_REQUEST
                )
            
            if len(query) < 2:
                return self.error_response(
                    "Search query must be at least 2 characters",
                    status.HTTP_400_BAD_REQUEST
                )
            
            # Limit search results for performance
            clients = Client.objects.filter(
                user=request.user,
                is_deleted=False
            ).filter(
                Q(name__icontains=query) |
                Q(email__icontains=query) |
                Q(phone_number__icontains=query)
            ).only(
                'id', 'name', 'email', 'phone_number', 'source'
            )[:20]  # Limit to 20 results
            
            serializer = ClientSearchSerializer(clients, many=True)

            if len(serializer.data)==0:
                return self.error_response(
                    "Client with the search query not found",
                    status.HTTP_404_NOT_FOUND,
                    data={"exists": False, "client": None}
                )            

            return self.success_response(
                serializer.data,
                f"Found {len(serializer.data)} clients"
            )
            
        except Exception as e:
            logger.error(f"Client search error: {str(e)}", exc_info=True)
            return self.error_response(
                # "Failed to search clients",
                f"Failed to search clients: {str(e)}", 
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )            
            
    @action(detail=True, methods=['get'], url_path='summary')
    def summary(self, request, pk=None):
        """
        Get complete client summary including client details, quotes, invoices, and services
        """
        try:
            client = self.get_object()
            quotes = client.quotes.filter(is_deleted=False)
            invoices = client.invoices.all()
            services = client.services.all()
    
            data = {
                # 'client': ClientDetailSerializer(client).data,
                'client': ClientDetailSerializer(client, context={'request': request}).data,  # ✅
                'quotes': ClientQuoteSummarySerializer(quotes, many=True).data,
                'invoices': ClientInvoiceSummarySerializer(invoices, many=True).data,
                'services': ClientServiceSummarySerializer(services, many=True).data,
            }
            return self.success_response(data, "Client summary fetched successfully")
    
        except Exception as e:
            logger.error(f"Client summary error: {str(e)}")
            return self.error_response(f"Failed to fetch client summary: {str(e)}", status.HTTP_500_INTERNAL_SERVER_ERROR)

    

    def destroy(self, request, *args, **kwargs):
        """
        Soft delete client after checking dependencies
        Ensures no active quotes/invoices before deletion
        """
        try:
            client = self.get_object()
            
            # Check for active quotes
            if client.quotes.filter(is_deleted=False).exists():
                return self.error_response(
                    "Cannot delete client with active quotes",
                    status.HTTP_400_BAD_REQUEST
                )
            
            # Check for invoices
            if client.invoices.exists():
                return self.error_response(
                    "Cannot delete client with invoices",
                    status.HTTP_400_BAD_REQUEST
                )
            
            with transaction.atomic():
                # Soft delete
                client.is_deleted = True
                client.deleted_at = timezone.now()
                client.save(update_fields=['is_deleted', 'deleted_at'])
                
                # Invalidate cache
                #cache.delete_pattern(f"client_list_{request.user.id}_*")
                self._bump_client_list_version(request.user.id)
                cache.delete(f"client_stats_{request.user.id}")
            
            return self.success_response(
                {"client_id": client.id},
                "Client deleted successfully"
            )
            
        # except Client.DoesNotExist: ❌ because DRF's get_object() raises Http404, not Client.DoesNotExist.
        except Http404:
            return self.error_response(
                "Client not found",
                status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Client deletion error: {str(e)}", exc_info=True)
            return self.error_response(
                # "Failed to delete client",
                f"Failed to delete client: {str(e)}", 
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Get aggregated client statistics for dashboard
        Uses database aggregation for efficiency
        """
        try:
            # Cache key for statistics
            cache_key = f"client_stats_{request.user.id}"
            cached_stats = cache.get(cache_key)
            
            if cached_stats:
                return self.success_response(
                    cached_stats,
                    "Client statistics fetched successfully (cached)"
                )
            
            # Get base queryset
            clients = Client.objects.filter(
                user=request.user,
                is_deleted=False
            )
            
            # Calculate statistics using database aggregation
            stats = {
                'total_clients': clients.count(),
                'clients_with_services': clients.filter(
                    services__isnull=False
                ).distinct().count(),
                'total_earnings': clients.aggregate(
                    total=Coalesce(
                        Sum('invoices__total'),
                        Value(0),
                        output_field=DecimalField()
                    )
                )['total'],
                'recent_clients': clients.filter(
                    created_at__gte=timezone.now() - timedelta(days=30)
                ).count(),
                'by_source': list(
                    clients.values('source').annotate(
                        count=Count('id')
                    ).order_by('-count')
                ),
                'top_clients': list(
                    clients.annotate(
                        total_spent=Coalesce(
                            # Sum('services__amount'),❌ClientService model does not have any database field called 'amount',only 'amount_earned' present which is python property 
                            Sum('services__quote__invoices__total'),
                            Value(0),
                            output_field=DecimalField()
                        )
                    ).filter(
                        total_spent__gt=0
                    ).order_by('-total_spent')[:5].values(
                        'id', 'name', 'total_spent'
                    )
                )
            }
            
            # Cache for 10 minutes
            cache.set(cache_key, stats, 600)
            
            return self.success_response(
                stats,
                "Client statistics fetched successfully"
            )
            
        except Exception as e:
            logger.error(f"Client statistics error: {str(e)}", exc_info=True)
            return self.error_response(
                # "Failed to fetch client statistics",
                f"Failed to fetch client statistics: {str(e)}", 
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    #=====================================================================================================
    #this are redundant, but keeping them if necessary in frontend

    @action(detail=True, methods=['get'])
    def services(self, request, pk=None):
        """
        Get all services for a specific client
        Paginated and optimized query
        """
        try:
            client = self.get_object()
            # services = client.services.select_related('quote').order_by('-quote_sent_date')
            services = client.services.select_related('quote').order_by('-quote__sent_at')
            
            page = self.paginate_queryset(services)
            if page is not None:
                serializer = ClientServiceSerializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = ClientServiceSerializer(services, many=True)
            return self.success_response(
                serializer.data,
                "Client services fetched successfully"
            )
            
        except Exception as e:
            logger.error(f"Service list error: {str(e)}", exc_info=True)
            return self.error_response(
                # "Failed to fetch client services",
                f"Failed to fetch client services: {str(e)}", 
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    @action(detail=True, methods=['get'])
    def quotes(self, request, pk=None):
        """
        Get all quotes for a specific client
        """
        try:
            # Import here to avoid circular dependency
            from quoteapp.serializers import QuoteSerializer
            
            client = self.get_object()
            quotes = client.quotes.filter(is_deleted=False).select_related('folder')
            
            page = self.paginate_queryset(quotes)
            if page is not None:
                serializer = QuoteSerializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = QuoteSerializer(quotes, many=True)
            return self.success_response(
                serializer.data,
                "Client quotes fetched successfully"
            )
            
        # except Client.DoesNotExist: ❌ because DRF's get_object() raises Http404, not Client.DoesNotExist.
        except Http404:
            return self.error_response(
                "Client not found",
                status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Client quotes error: {str(e)}", exc_info=True)
            return self.error_response(
                # "Failed to fetch client quotes",
                f"Failed to fetch client quotes: {str(e)}", 
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def invoices(self, request, pk=None):
        """
        Get all invoices for a specific client
        """
        try:
            # Import here to avoid circular dependency
            from quoteapp.serializers import InvoiceSerializer
            
            client = self.get_object()
            # invoices = client.invoices.select_related('quote', 'folder')#removing because invoice model has no folder field
            invoices = client.invoices.select_related('quote')
            
            page = self.paginate_queryset(invoices)
            if page is not None:
                serializer = InvoiceSerializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = InvoiceSerializer(invoices, many=True)
            return self.success_response(
                serializer.data,
                "Client invoices fetched successfully"
            )
            
        # except Client.DoesNotExist: ❌ because DRF's get_object() raises Http404, not Client.DoesNotExist.
        except Http404:
            return self.error_response(
                "Client not found",
                status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Client invoices error: {str(e)}", exc_info=True)
            return self.error_response(
                # "Failed to fetch client invoices",
                f"Failed to fetch client invoices: {str(e)}",
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ---------------------------
# ClientService ViewSet
# ---------------------------
class ClientServiceViewSet(StandardResponseMixin, viewsets.ModelViewSet):
            """CRUD for ClientService linked to accepted quotes"""
            serializer_class = ClientServiceSerializer
            permission_classes = [IsAuthenticated]
            parser_classes = [MultiPartParser, JSONParser]
        
        
            def get_queryset(self):
                return ClientService.objects.filter(client__user=self.request.user)\
                    .select_related('client', 'quote').order_by('-quote__sent_at')  # Fix ordering
                    
                    
            def list(self, request, *args, **kwargs):
                """
                List clients with advanced filtering and search
                Implements caching for frequently accessed lists
                """
                try:
                    cache_key = f"client_list_{request.user.id}_{request.GET.urlencode()}"
                    cached_data = cache.get(cache_key)
                    if cached_data and not request.GET.get('no_cache'):
                        return self.success_response(
                            cached_data,
                            "Clients fetched successfully (cached)"
                        )
            
                    queryset = self.filter_queryset(self.get_queryset())
            
                    # Apply filters
                    search_query = request.query_params.get('search')
                    if search_query:
                        queryset = queryset.filter(
                            Q(name__icontains=search_query) |
                            Q(email__icontains=search_query) |
                            Q(phone_number__icontains=search_query)
                        )
            
                    source_filter = request.query_params.get('source')
                    if source_filter in ['manual', 'imported']:
                        queryset = queryset.filter(source=source_filter)
            
                    has_services = request.query_params.get('has_services')
                    if has_services:
                        if has_services.lower() == 'true':
                            queryset = queryset.filter(service_count__gt=0)
                        else:
                            queryset = queryset.filter(service_count=0)
            
                    date_from = request.query_params.get('date_from')
                    date_to = request.query_params.get('date_to')
                    if date_from:
                        queryset = queryset.filter(created_at__gte=date_from)
                    if date_to:
                        queryset = queryset.filter(created_at__lte=date_to)
            
                    # Paginate
                    page = self.paginate_queryset(queryset)
                    if page is not None:
                        serializer = self.get_serializer(page, many=True)
                        response_data = {
                            "count": self.paginator.page.paginator.count,
                            "page": self.paginator.page.number,
                            "page_size": self.paginator.get_page_size(request),
                            "results": serializer.data
                        }
                        cache.set(cache_key, response_data, 300)
                        return self.success_response(response_data, "Clients fetched successfully")
            
                    serializer = self.get_serializer(queryset, many=True)
                    cache.set(cache_key, serializer.data, 300)
                    return self.success_response(serializer.data, "Clients fetched successfully")
            
                except Exception as e:
                    logger.error(f"Client list error: {str(e)}", exc_info=True)
                    return self.error_response(
                        # "Failed to fetch clients",
                        f"Failed to fetch clients: {str(e)}", 
                        status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
                        
                        
            def create(self, request, *args, **kwargs):
                """Create service only for accepted quote"""
                try:
                    quote_id = request.data.get('quote')
                    if not quote_id:
                        return self.error_response("Quote is required", status.HTTP_400_BAD_REQUEST)
                    try:
                        quote = Quote.objects.get(quote_id=quote_id, user=request.user)
                        if quote.quote_status != 'won':
                            return self.error_response("Can only create service for accepted quote", status.HTTP_400_BAD_REQUEST)
                    except Quote.DoesNotExist:
                        return self.error_response("Quote not found", status.HTTP_404_NOT_FOUND)
        
                    serializer = self.get_serializer(data=request.data)
                    serializer.is_valid(raise_exception=True)
                    with transaction.atomic():
                        service = serializer.save()
                    return self.success_response(serializer.data, "Client service created successfully", status.HTTP_201_CREATED)
                except ValidationError as e:
                    return self.error_response(str(e), status.HTTP_400_BAD_REQUEST)
                except Exception as e:
                    logger.error(f"Client service creation error: {str(e)}")
                    return self.error_response(f"Failed to create client service : {str(e)}", status.HTTP_500_INTERNAL_SERVER_ERROR)
                    
        
            def update(self, request, *args, **kwargs):
                """Update ClientService"""
                try:
                    instance = self.get_object()
                    serializer = self.get_serializer(instance, data=request.data, partial=True)
                    serializer.is_valid(raise_exception=True)
                    with transaction.atomic():
                        service = serializer.save()
                    return self.success_response(serializer.data, "Client service updated successfully")
                except ValidationError as e:
                    return self.error_response(str(e), status.HTTP_400_BAD_REQUEST)
                except Exception as e:
                    logger.error(f"Client service update error: {str(e)}")
                    return self.error_response(f"Failed to update client service: {str(e)}", status.HTTP_500_INTERNAL_SERVER_ERROR)
                    
        
            def destroy(self, request, *args, **kwargs):
                """Delete ClientService"""
                try:
                    service = self.get_object()
                    service.delete()
                    return self.success_response({"service_id": service.id}, "Client service deleted successfully")
                except Exception as e:
                    logger.error(f"Client service deletion error: {str(e)}")
                    return self.error_response(f"Failed to delete client service: {str(e)}", status.HTTP_500_INTERNAL_SERVER_ERROR)
                    









