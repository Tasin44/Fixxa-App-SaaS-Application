

# clientapp/serializers.py
from rest_framework import serializers
from clientapp.models import Client,ClientService
from django.db.models import Sum
from quoteapp.models import Folder, Quote, Invoice


# ------------------------------
# ClientService Serializer
# ------------------------------
class ClientServiceSerializer(serializers.ModelSerializer):
    """Serializer for ClientService with related quote data"""
    service_type = serializers.ReadOnlyField(source='service_type')  # Use property
    quote_status = serializers.ReadOnlyField(source='quote_status')  # Use property; removed duplicate
    service_location = serializers.ReadOnlyField(source='service_location')  # Use property
    quote_sent_date = serializers.ReadOnlyField(source='quote_sent_date')  # Use property
    quote_id = serializers.ReadOnlyField(source='quote.quote_id')
    amount_earned = serializers.ReadOnlyField(source='amount_earned')  # Use property

    class Meta:
        model = ClientService
        fields = [
            'id',
            'quote_id',
            'quote_sent_date',
            # 'total',
            'amount_earned',
            'notes',
            'service_type',
            'quote_status',
            'service_location'
        ]
        read_only_fields = ['id']


# ------------------------------
# Client List Serializer
# ------------------------------
class ClientListSerializer(serializers.ModelSerializer):
    """Optimized serializer for client lists (reduces N+1 queries)"""
    total_services = serializers.ReadOnlyField()
    total_earnings = serializers.ReadOnlyField()
    latest_service_date = serializers.ReadOnlyField()
    accepted_quotes_count = serializers.ReadOnlyField()
    image=serializers.SerializerMethodField()

    class Meta:
        model = Client
        fields = [
            'id',
            'name',
            'email',
            'phone_number',
            'image',
            'address',
            'source',
            'total_services',
            'total_earnings',
            'latest_service_date',
            'created_at',
            'accepted_quotes_count',

        ]
        read_only_fields = [
            'id', 'created_at', 'total_services', 'total_earnings', 'latest_service_date'
        ]

    def get_image(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
        return None

# ------------------------------
# Client Detail Serializer
# ------------------------------
class ClientDetailSerializer(serializers.ModelSerializer):
    """Detailed client serializer with related data"""
    total_services = serializers.ReadOnlyField()
    total_earnings = serializers.ReadOnlyField()
    latest_service_date = serializers.ReadOnlyField()
    services = ClientServiceSerializer(many=True, read_only=True)
    quotes_count = serializers.SerializerMethodField()
    invoices_count = serializers.SerializerMethodField()
    folder_name = serializers.SerializerMethodField()
    accepted_quotes_count = serializers.SerializerMethodField()

    image=serializers.SerializerMethodField()

    class Meta:
        model = Client
        fields = [
            'id',
            'user',
            'name',
            'email',
            'phone_number',
            'image',
            'address',
            'source',
            'is_deleted',
            'deleted_at',
            'created_at',
            'updated_at',
            'total_services',
            'total_earnings',
            'latest_service_date',
            'accepted_quotes_count',
            'services',
            'quotes_count',
            'invoices_count',
            'folder_name'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'total_services',
            'total_earnings', 'latest_service_date'
        ]
    def get_image(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
        return None
    def get_quotes_count(self, obj):
        """Count quotes for this client"""
        return obj.quotes.filter(is_deleted=False).count()

    def get_invoices_count(self, obj):
        """Count invoices for this client"""
        return obj.invoices.count()
    
    def get_accepted_quotes_count(self, obj):
        """Count how many quotes were accepted by this client"""
        return obj.quotes.filter(quote_status='won', is_deleted=False).count()
        
    def get_folder_name(self, obj):
        try:
            # folder = Folder.objects.get(user=obj.user, folder_name=obj.name)❌
            '''
            Reason behind removing the above line-

            In ensure_client_folder() I name the folder like:
            folder_name = f"{client.id}_{client.name.replace(' ', '_')}"
            That means lookup by just obj.name will always fail → causes another 500 error later.
            '''
            #folder_name = f"{obj.id}_{obj.name.replace(' ', '_')}"
            folder_name = f"{obj.name.replace(' ', '_')}"  # ✅ match ensure_client_folder

            folder = Folder.objects.get(user=obj.user, folder_name=folder_name)
            #return folder.folder_name
            return obj.name  # Return clean name for frontend display
        except Folder.DoesNotExist:
            return None
        

class ClientServiceSummarySerializer(ClientServiceSerializer):
    class Meta(ClientServiceSerializer.Meta):
        fields = ['id','quote_status','quote_sent_date']


# ------------------------------
# Client Create / Update Serializer
# ------------------------------
class ClientCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for client creation and updates"""
    class Meta:
        model = Client
        fields = [
            'id',
            'name',
            'email',
            'phone_number',
            'image',
            'address',
            'source',
        ]
        read_only_fields = ['id']

    def validate_name(self, value):
        """Validate client name"""
        if not value or not value.strip():
            raise serializers.ValidationError("Client name cannot be empty")
        
        #name length validation 
        '''
        if len(value.strip()) < 2:
            raise serializers.ValidationError("Client name must be at least 2 characters long")
        '''

        return value.strip()

    def validate_phone_number(self, value):
        """Validate phone number format + uniqueness"""
        if not value:
            raise serializers.ValidationError("Phone number is required")

        #phone number length validation 
        '''
        if len(value) < 10:
            raise serializers.ValidationError("Phone number must be at least 10 digits")
        '''

        user = self.context['request'].user
        qs = Client.objects.filter(user=user, phone_number=value, is_deleted=False)

        if self.instance:
            qs = qs.exclude(id=self.instance.id)

        #easy version 
        '''

            if self.instance:  # Update operation
                existing = Client.objects.filter(
                    user=self.context['request'].user,
                    phone_number=value,
                    is_deleted=False
                ).exclude(id=self.instance.id)
            else:  # Create operation
                existing = Client.objects.filter(
                    user=self.context['request'].user,
                    phone_number=value,
                    is_deleted=False
                )
        '''
        if qs.exists():
            raise serializers.ValidationError("Client with this phone number already exists")

        return value

    def validate_email(self, value):
        """Validate email uniqueness per user"""
        if value:
            user = self.context['request'].user
            qs = Client.objects.filter(user=user, email=value, is_deleted=False)
            # Check for duplicate email for this user

            if self.instance:
                qs = qs.exclude(id=self.instance.id)

            if qs.exists():
                raise serializers.ValidationError("Client with this email already exists")

        return value

    '''
    def validate(self, data):
        """Cross-field validation"""
        # Ensure at least one contact method is provided
        if not data.get('phone_number') and not data.get('email'):
            raise serializers.ValidationError("Either phone number or email must be provided")
        return data
    '''
    '''
    Previous validate(self, data) likely did:
        phone = data.get('phone_number')
        email = data.get('email')
    so both became None if not included in PATCH → validation failed.

    Why new code(below ) works:
        It first checks new incoming values in data
        If missing, it falls back to old saved values from self.instance
        So changing only name still keeps existing phone/email valid, and validation passes.
    '''
    def validate(self, data):
        """Cross-field validation (works for create + partial update)"""
        phone = data.get(
            'phone_number',
            self.instance.phone_number if self.instance else None
        )
        email = data.get(
            'email',
            self.instance.email if self.instance else None
        )

        if not phone and not email:
            raise serializers.ValidationError("Either phone number or email must be provided")
        return data
    
    
    def create(self, validated_data):
        """Create client with auto folder creation"""
        user = self.context['request'].user
        if not user or user.is_anonymous:
            raise serializers.ValidationError("Authentication required to create a client")
        validated_data['user'] = user
        client = super().create(validated_data)
        
        # Folder creation is handled by Client.save() method
        return client

    def update(self, instance, validated_data):
        """Update client and handle folder rename if name changes"""
        old_name = instance.name
        client = super().update(instance, validated_data)

        # Update folder name if client name changed        
        if old_name != client.name:
            # old_folder_name = f"{client.id}_{old_name.replace(' ', '_')}"
            # new_folder_name = f"{client.id}_{client.name.replace(' ', '_')}"
            old_folder_name = f"{old_name.replace(' ', '_')}"
            new_folder_name = f"{client.name.replace(' ', '_')}"
            # Folder.objects.update_or_create(# Create new folder if old one doesn't exist

            #     user=client.user,
            #     # folder_name=old_name,
            #     folder_name=old_folder_name,
            #     defaults={'folder_name': client.name}
            # ).update(folder_name=new_folder_name)
            Folder.objects.filter(
                user=client.user,
                folder_name=old_folder_name
            ).update(folder_name=new_folder_name)
        return client


# ------------------------------
# Client Import Serializer
# ------------------------------
class ClientImportSerializer(serializers.ModelSerializer):
    """Specialized serializer for contact import"""
    class Meta:
        model = Client
        fields = ['name', 'email', 'phone_number', 'address', 'source']
        extra_kwargs = {
            'source': {'read_only': True} # Auto-set to 'imported'
        }

    def validate_phone_number(self, value):
        user = self.context['request'].user
        qs = Client.objects.filter(user=user, phone_number=value, is_deleted=False)
        if qs.exists():
            raise serializers.ValidationError("Client with this phone number already exists")
        return value

    def validate_email(self, value):
        """Validate email uniqueness per user"""
        if value:
            user = self.context['request'].user
            qs = Client.objects.filter(user=user, email=value, is_deleted=False)
            # Check for duplicate email for this user

            if self.instance:
                qs = qs.exclude(id=self.instance.id)

            if qs.exists():
                raise serializers.ValidationError("Client with this email already exists")

        return value
    

    def validate(self, data):
        """Bulk validation for imported contacts"""

        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError("Request context is required")

        
        user = request.user
        
        # Check for existing clients with same phone/email
        # Ensure at least one contact method
        if not data.get('phone_number') and not data.get('email'):
            raise serializers.ValidationError("Either phone number or email must be provided")
        
        # Auto-set source to imported
        data['source'] = 'imported'
        return data


# ------------------------------
# Stats / Search / Utility
# ------------------------------
#last 30 days added client and top client, client with services 

'''
class ClientStatsSerializer(serializers.Serializer):
    """Serializer for client statistics"""
    total_clients = serializers.IntegerField()
    clients_with_services = serializers.IntegerField()
    total_earnings = serializers.DecimalField(max_digits=12, decimal_places=2)
    recent_clients = serializers.IntegerField(help_text="Clients added in last 30 days")
    top_clients = serializers.ListField(child=serializers.DictField())
'''

class ClientSearchSerializer(serializers.ModelSerializer):
    """Lightweight serializer for search results"""
    class Meta:
        model = Client
        fields = ['id', 'name', 'email', 'phone_number', 'source']


class ClientQuoteSummarySerializer(serializers.ModelSerializer):
    """Minimal quote data for client details"""
    status = serializers.CharField(source='get_quote_status_display')

    class Meta:
        model = Quote
        fields = ['quote_id', 'total', 'status', 'created_at','sent_at']


class ClientInvoiceSummarySerializer(serializers.ModelSerializer):
    """Minimal invoice data for client details"""
    status = serializers.CharField(source='get_quote_status_display')

    class Meta:
        model = Invoice
        fields = ['invoice_id', 'invoice_number', 'total', 'status', 'created_at']



