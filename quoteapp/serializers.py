
from rest_framework import serializers
from quoteapp.models import Folder,Quote,QuoteItem,Invoice,InvoiceItem,ScannedDocument
from decimal import Decimal
import json
import logging
logger = logging.getLogger(__name__)
from decimal import Decimal, ROUND_HALF_UP

class FolderSerializer(serializers.ModelSerializer):
    class Meta:
        model=Folder
        fields='__all__'
        read_only_fields = ['folder_id', 'created_at', 'updated_at']

    def validate_folder_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Folder name cannot be empty.")
        return value
    
class ScannedDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScannedDocument
        # fields = ['id', 'user', 'client', 'image', 'created_at']
        fields = ['id', 'client', 'folder','image', 'created_at']

        read_only_fields = ['id', 'folder','created_at']

    def validate(self, data):
        # if not data.get('client'):
        #     raise serializers.ValidationError({'client': 'Client is required.'})
        if not data.get('image'):
            raise serializers.ValidationError({'image': 'Image file is required.'})
        return data
    


class QuoteItemSerializer(serializers.ModelSerializer):
    # id = serializers.IntegerField()  # 👈 Add this line

    id = serializers.IntegerField(required=False, allow_null=True)  # ← CHANGED: made optional

    class Meta:
        model = QuoteItem
        fields = [
            "id",
            "quote_description",   # was description
            "service_type",
            "material_name",       # was materials
            "quantity",            # newly added
            "unit_price",          # newly added
            "service_duration",    # was duration
            # "duration_unit",
            "service_rate",        # was rate
        ]

    '''
    def validate(self, attrs):
        request_method = self.context['request'].method
        if request_method in ['PUT', 'PATCH'] and not attrs.get('id'):
            raise serializers.ValidationError({"id": "This field is required when updating a quote."})
        return attrs
    '''
    # ✅ CHANGE 2: Update validation logic
    def validate(self, attrs):
        request = self.context.get('request')
        if not request:
            return attrs
            
        request_method = request.method
        
        # For updates, id is mandatory
        if request_method in ['PUT', 'PATCH']:
            if 'id' not in attrs or attrs.get('id') is None:
                raise serializers.ValidationError({
                    "id": "Item ID is mandatory when updating a quote."
                })
        
        # For creation, remove id if provided (will auto-assign)
        if request_method == 'POST':
            attrs.pop('id',None)  # ← NEW: Remove id, will be auto-assigned by database
        
        return attrs
    
    def update(self, instance, validated_data):
        validated_data['amount'] = validated_data.get('quantity', instance.quantity) * validated_data.get('unit_price', instance.unit_price)
        return super().update(instance, validated_data)

    def create(self, validated_data):
        validated_data['amount'] = validated_data.get('quantity') * validated_data.get('unit_price')
        return super().create(validated_data)

class QuoteSerializer(serializers.ModelSerializer):
    client_details=serializers.SerializerMethodField()
    # source = serializers.ChoiceField(choices=Quote.SOURCE_CHOICES, default='manual')
    '''
    removing the above source line :
    ✔ 1. source will NOT be accepted from frontend
        If frontend sends "source": "imported", DRF will ignore it.

    ✔ 2. source will still appear in responses
    But clients cannot modify it.
    '''
    source = serializers.CharField(read_only=True)
    items = QuoteItemSerializer(many=True, required=False)  # Added for items
    effective_service_location = serializers.SerializerMethodField()
    vat_amount = serializers.SerializerMethodField()  # 4th dec
    discount_value = serializers.SerializerMethodField()  #4th dec

    def get_client_details(self, obj):
        return obj.client_details
    
    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)
    #     # ✅ Pass context (especially request) to nested serializer
    #     self.fields['items'].context.update(self.context)
    # ✅ ADD THIS INSTEAD
    def get_fields(self):
        fields = super().get_fields()
        # fields['items'].context.update(self.context)
        return fields      
    class Meta:
        model=Quote
        fields = [
            "quote_id",
            "quote_number",
            # "user",
            "client",
            "folder",
            "source",
            "client_details",
            "discount_amount",
            "discount_type",
            "discount_value",  # 4th decADD THIS - the calculated discount
            "vat_amount",  #4th dec ADD THIS - the calculated VAT
            "subtotal",
            "vat_rate",
            "total",
            "issue_date",
            "due_date",
            "quote_status",
            "duration_unit",
            "sent_via",
            "sent_at",
            "signature",
            "pdf_file",
            "service_location",
            "is_deleted",
            "deleted_at",
            "pdf_generated_at",
            "can_edit",
            "created_at",
            "updated_at",
            "items",
            "effective_service_location",
        ]

        read_only_fields = ['quote_id', 'created_at', 'updated_at', 'subtotal', 'total', 'pdf_generated_at', 
        'can_edit']

        #no need to do obj.quotes.client_details because obj is already a Quote instance
    
    '''
    The Issue:

    obj here represents a single Quote instance (because it's inside the QuoteSerializer).

    obj.quotes is incorrect because quotes is a reverse relation to the Quote model from the Folder model, meaning that each folder can have multiple quotes, but the Quote model itself has only one client (related to Client).

    So, obj.quotes doesn't exist — obj is already a Quote object, and it has a direct client relation, not a quotes relation.
    '''
    
    def get_effective_service_location(self, obj):
        return obj.effective_service_location

    
    def validate(self, data):
        """Validate quote data before saving"""
        client = data.get('client')

        if data.get('quote_status') == 'sent':
            # Required fields
            required_fields = ['quote_id', 'issue_date', 'due_date']
            missing_fields = [f for f in required_fields if not data.get(f)]

            # Client validation
            if not client:
                missing_fields.append('client')
            else:
                if not client.email:
                    missing_fields.append('client.email')
                if not client.address:
                    missing_fields.append('client.address')

            if missing_fields:
                raise serializers.ValidationError({
                    'missing_fields': f"Required fields for sending quote: {', '.join(missing_fields)}"
                })

            # Extra validation if sending via email
            if data.get('sent_via') in ['email', 'both'] and not client.email:
                raise serializers.ValidationError({
                    'client.email': 'Client must have an email address to send via email'
                })

        # PDF edit restriction
        if data.get('pdf_file') and data.get('can_edit', True):
            raise serializers.ValidationError({'can_edit': 'Cannot set PDF while editable.'})
        
        if data.get('discount_amount', 0) < 0:#since a user could input discount_amount, so validation necessary
            raise serializers.ValidationError({'discount_amount': 'Must be a positive value or zero'})
        
        return data 
    
    '''
    ❓❓❓Why not those field validation still necessary?

    # Monetary fields validation
    for field in ['subtotal', 'discount_amount', 'total']:
        if field in data and data[field] is not None and data[field] < 0:
            raise serializers.ValidationError({
                field: 'Must be a positive value or zero'
            })   

    Answer: 

    -Your Quote and Invoice models already calculate things like subtotal, total, and amount using methods (calculate_amounts, calculate_totals).

    -That means these values are usually derived fields, not something the user should freely submit.

    In fact, in your serializers you already marked subtotal and total as read_only_fields — which is correct, because they shouldn’t be directly editable.

    So, if those fields are read-only and always computed internally, then this monetary validation is redundant.
    '''
    def get_vat_amount(self, obj):#added 4th dec
        """Calculate and return the actual VAT amount in currency"""
        from decimal import Decimal
        # Calculate discount value first
        discount_value = Decimal('0.00')
        if obj.discount_amount > 0:
            if obj.discount_type == 'percentage':
                discount_value = obj.subtotal * (obj.discount_amount / Decimal('100.00'))
            else:
                discount_value = obj.discount_amount
        # Calculate subtotal after discount
        subtotal_after_discount = obj.subtotal - discount_value
        # Calculate VAT on discounted subtotal
        vat_amount = subtotal_after_discount * (obj.vat_rate / Decimal('100.00'))
        return float(vat_amount)
    def get_discount_value(self, obj):#added 4th dec
        """Calculate and return the actual discount value in currency"""
        from decimal import Decimal
        discount_value = Decimal('0.00')
        if obj.discount_amount > 0:
            if obj.discount_type == 'percentage':
                discount_value = obj.subtotal * (obj.discount_amount / Decimal('100.00'))
            else:
                discount_value = obj.discount_amount
        return float(discount_value)
    def to_internal_value(self, data):
        items = None
        logger.debug(f"🧩 Raw items from request: {data.get('items')}")

        # Extract items based on data type (QueryDict or dict)
        if hasattr(data, 'getlist'):
            multi = data.getlist('items')
            if multi:
                items = multi if len(multi) > 1 else multi[0]
        if items is None:
            items = data.get('items')

        if items is None:
            return super().to_internal_value(data)

        # Copy data for modification
        def copy_data():
            return data.copy() if hasattr(data, 'copy') else dict(data)

        # Handle dict (e.g., JSON {"items": {...}})
        if isinstance(items, dict):
            data = copy_data()
            data['items'] = [items]
            return super().to_internal_value(data)

        # Handle string or bytes (e.g., form-data JSON string)
        if isinstance(items, (str, bytes)):
            text = items.decode() if isinstance(items, bytes) else items
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    parsed = [parsed]
                data = copy_data()
                data['items'] = parsed
                return super().to_internal_value(data)
            except json.JSONDecodeError:
                raise serializers.ValidationError({'items': 'Invalid JSON format for items field.'})

        # Handle list (e.g., JSON array or multiple form 'items' fields)
        if isinstance(items, list):
            parsed_list = []
            for elem in items:
                if isinstance(elem, (str, bytes)):
                    text = elem.decode() if isinstance(elem, bytes) else elem
                    try:
                        parsed_elem = json.loads(text)
                        parsed_list.append(parsed_elem)
                    except json.JSONDecodeError:
                        raise serializers.ValidationError({'items': 'Invalid JSON in one of the items entries.'})
                elif isinstance(elem, dict):
                    parsed_list.append(elem)
                else:
                    raise serializers.ValidationError({'items': 'Invalid item type in list.'})
            data = copy_data()
            data['items'] = parsed_list
            return super().to_internal_value(data)


    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        # if 'quote_number' not in validated_data:
        #     validated_data['quote_number'] = Quote(**validated_data).generate_quote_number()

        validated_data['subtotal'] = Decimal('0.00')
        validated_data['total'] = Decimal('0.00')

        quote = Quote.objects.create(**validated_data)

        # Create items
        # items_to_create = []
        # for item_data in items_data:
        #     item_data.pop('id', None)
        #     items_to_create.append(QuoteItem(quote=quote, **item_data))
        

        # if items_to_create:
        #     QuoteItem.objects.bulk_create(items_to_create)
        # ✅ NEW: Auto-assign IDs (1, 2, 3...) when creating items
        for index, item_data in enumerate(items_data, start=1):
            item_data.pop('id', None)  # Remove id if accidentally provided
            QuoteItem.objects.create(quote=quote, **item_data)
            # Database will auto-assign the primary key
        # 🔥 Refresh quote WITH prefetched items
        quote = Quote.objects.prefetch_related('items').get(pk=quote.pk)

        # Recalculate totals
        quote.calculate_totals()
        quote.save(update_fields=['subtotal', 'total'])

        return quote 

    def update(self, instance, validated_data):
        print(f"🔍 validated_data keys: {validated_data.keys()}")
        print(f"🔍 validated_data items: {validated_data.get('items', 'NO ITEMS')}")
        if not instance.can_edit:
            raise serializers.ValidationError('Cannot edit after PDF generation.')
        
        if instance.source == 'voice' and self.context.get('edit_method') != 'voice':
            raise serializers.ValidationError('Voice-created quote must be edited by voice.')
        
        if instance.source == 'manual' and self.context.get('edit_method') != 'manual':
            raise serializers.ValidationError('Manually-created quote must be edited manually.')
        
        if 'vat_rate' in validated_data or 'discount_amount' in validated_data or 'discount_type' in validated_data:
            raise serializers.ValidationError("VAT rate and discount cannot be changed after quote creation.")
        
        items_data = validated_data.pop('items', [])
        instance = super().update(instance, validated_data)

        if items_data:

            current_items = {item.id: item for item in instance.items.all()}
            sent_item_ids = []## Track which IDs were sent in the request new_7th_october
            
            for item_data in items_data:
                item_id = item_data.get('id')


                if item_id :
                    if item_id not in current_items:
                        raise serializers.ValidationError({
                            "item_error": f"Item ID {item_id} does not belong to Quote #{instance.quote_id}"
                        })
                    # Update existing item
                    item = current_items[item_id]
                    '''
                    for key, value in item_data.items():
                        setattr(item, key, value)
                    '''
                    for key, value in item_data.items():
                        # if key != 'id':  # Don't update the id field
                        if key != 'id':  # Don't update primary key
                                setattr(item, key, value)
                    item.save()
                    sent_item_ids.append(item_id)

                else:
            # ✅ Only create a new item if no id is provided at all
                    # item_data.pop('id', None)
                    item_data.pop('id', None)
                    QuoteItem.objects.create(quote=instance, **item_data)
        # Recalculate totals
        instance.calculate_totals()
        instance.save()
        return instance
    

# --------------------------
# InvoiceItem Serializer
# --------------------------
class InvoiceItemSerializer(serializers.ModelSerializer):
    item_id = serializers.IntegerField(required=False, allow_null=True)
    class Meta:
        model = InvoiceItem
        fields = [
            "item_id",
            "quote_description",  # ADD THIS
            "material_name",      # was materials
            "quantity",           # new
            "unit_price",         # new
            "service_duration",   # was duration
            "duration_unit",
            "service_rate",       # was rate
            "service_type", 
        ]
        # read_only_fields = ["amount"
    def validate(self, attrs):
        request = self.context.get('request')
        if not request:
            return attrs

        # For PATCH/PUT (update) → item_id must exist
        if request.method in ['PUT', 'PATCH']:
            if not attrs.get('item_id'):
                raise serializers.ValidationError({
                    "item_id": "Item ID is mandatory when updating an invoice item"
                })

        # For creation, remove ID if sent
        if request.method == 'POST':
            attrs.pop("item_id", None)

        return attrs

    def update(self, instance, validated_data):
        return super().update(instance, validated_data)

    def create(self, validated_data):
        return super().create(validated_data)

# Serializer for Invoice
class InvoiceSerializer(serializers.ModelSerializer):
    items = InvoiceItemSerializer(many=True, required=False)
    client_details = serializers.SerializerMethodField()
    is_paid = serializers.BooleanField(default=False)
    stripe_account_id = serializers.SerializerMethodField()

    def get_client_details(self, obj):
        return obj.client_details

    def get_stripe_account_id(self, obj):
        return obj.user.business_profile.stripe_account_id if hasattr(obj.user, 'business_profile') else None  # Fixed: Source from BusinessProfile
    
    class Meta:
        model = Invoice
        fields = [
            "invoice_id",
            "invoice_number",  # ✅ ADD THIS - you missed it
            # "user",
            "client",
            "folder",
            # "source",
            "client_details",
            "discount_amount",
            "discount_type",
            "subtotal",
            "vat_rate",
            "total",
            "issue_date",
            "due_date",
            "quote",
            "quote_status",
            "payment_status",
            "sent_via",
            "sent_at",
            "signature",
            "pdf_file",
            # "payment_speed",
            "pdf_generated_at",
            "can_edit",
            "created_at",
            "updated_at",
            "items",
            "payment_link",
            "is_paid",
            "paid_date",
            "effective_service_location",
            "stripe_account_id",
            "discount_type",
            "duration_unit",
        ]
        read_only_fields = ['invoice_id', 'created_at', 'updated_at', 'subtotal', 'total', 'client_details', 'pdf_generated_at', 'can_edit', 'invoice_number','stripe_account_id']
    
    def get_effective_service_location(self, obj):
        return obj.effective_service_location
    
    def to_internal_value(self, data):
        """Parse items from JSON string in multipart form-data"""
        items = None
        
        # Extract items based on data type (QueryDict or dict)
        if hasattr(data, 'getlist'):
            multi = data.getlist('items')
            if multi:
                items = multi if len(multi) > 1 else multi[0]
        if items is None:
            items = data.get('items')

        if items is None:
            return super().to_internal_value(data)

        # Copy data for modification
        def copy_data():
            return data.copy() if hasattr(data, 'copy') else dict(data)

        # Handle string or bytes (form-data JSON string)
        if isinstance(items, (str, bytes)):
            text = items.decode() if isinstance(items, bytes) else items
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    parsed = [parsed]
                # ✅ Map 'id' to 'item_id' for each item
                for item in parsed:
                    if 'id' in item and 'item_id' not in item:
                        item['item_id'] = item.pop('id')
                data = copy_data()
                data['items'] = parsed
                return super().to_internal_value(data)
            except json.JSONDecodeError:
                raise serializers.ValidationError({'items': 'Invalid JSON format for items field.'})

        if isinstance(items, dict):
            if 'id' in items and 'item_id' not in items:
                items['item_id'] = items.pop('id')
            data = copy_data()
            data['items'] = [items]
        elif isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and 'id' in item and 'item_id' not in item:
                    item['item_id'] = item.pop('id')
            data = copy_data()
            data['items'] = items
            
        return super().to_internal_value(data)
    
    def validate(self, data):


        # 🔧 Convert all monetary fields to Decimal with proper precision
        if 'discount_amount' in data and data['discount_amount'] is not None:
            data['discount_amount'] = Decimal(str(data['discount_amount'])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        if 'vat_rate' in data and data['vat_rate'] is not None: 
            data['vat_rate'] = Decimal(str(data['vat_rate'])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        if 'subtotal' in data and data['subtotal'] is not None:
            data['subtotal'] = Decimal(str(data['subtotal'])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        if 'total' in data and data['total'] is not None:
            data['total'] = Decimal(str(data['total'])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        # Check required fields for sending invoice
        if data.get('quote_status') == 'sent':
            required_fields = ['client', 'issue_date', 'due_date']
            missing_fields = [field for field in required_fields if not data.get(field)]
            
            if missing_fields:
                raise serializers.ValidationError({
                    'missing_fields': f"Required fields for sending invoice: {', '.join(missing_fields)}"
                })
            

            
        if 'sent_via' in data and data['sent_via'] != 'none' and not data.get('client').email:
            raise serializers.ValidationError({'client_email': 'Client email is required for sending.'})
        
        if 'pdf_file' in data and data.get('pdf_file') and data.get('can_edit', True):
            raise serializers.ValidationError({'can_edit': 'Cannot set PDF while editable.'})
        return data

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])

        if 'invoice_number' not in validated_data:
            validated_data['invoice_number'] = Invoice(**validated_data).generate_invoice_number()

        #invoice = Invoice.objects.create(invoice_number=invoice.generate_invoice_number(), **validated_data)
        #Removing the above line cause it called invoice.generate_invoice_number() before invoice exists.
        
        # ✅ Set initial values to avoid calculation in save()
        validated_data['subtotal'] = Decimal('0.00')
        validated_data['total'] = Decimal('0.00')
        '''
        #❌ without this abot two lines and without calling calculate_totals() in serializer, I got error like 'Invoice' instance needs to have a primary key value before this relationship can be used.' so in model save method, shouldnot call calculate_totals(). calculation in serializers is safe
        
        '''
        # ✅ just create invoice normally, view will inject invoice_number
        invoice = Invoice.objects.create(**validated_data)

        # ✅ NEW: Auto-assign IDs (1, 2, 3...) when creating items
        for index, item_data in enumerate(items_data, start=1):
            item_data.pop('id', None)  # Remove id if accidentally provided
            InvoiceItem.objects.create(invoice=invoice, **item_data)
            # Database will auto-assign the primary key

        
        # 3️⃣ Calculate totals now that items exist
        invoice.calculate_amounts() #recalculate in serializers is save
        invoice.save(update_fields=['subtotal', 'total'])
        return invoice 


    def update(self, instance, validated_data):
      
        if not instance.can_edit:
            raise serializers.ValidationError('Cannot edit after PDF generation.')
            
        if instance.source == 'voice' and self.context.get('edit_method') != 'voice':
            raise serializers.ValidationError('Voice-created invoice must be edited by voice.')
        
        if instance.source == 'manual' and self.context.get('edit_method') != 'manual':
            raise serializers.ValidationError('Manually-created invoice must be edited manually.')
            
        if 'vat_rate' in validated_data or 'discount_amount' in validated_data or 'discount_type' in validated_data:
            raise serializers.ValidationError("VAT rate and discount cannot be changed after quote creation.")
            
        items_data = validated_data.pop('items', [])
        # items_data = self.initial_data.get('items', [])
        instance = super().update(instance, validated_data)
        
        if items_data:

            current_items = {item.item_id: item for item in instance.items.all()}
            # sent_item_ids = []## Track which IDs were sent in the request new_7th_october
            
            for item_data in items_data:
                item_id = item_data.get('item_id')

                if item_id :
                    if item_id not in current_items:
                        raise serializers.ValidationError({
                            "item_error": f"Item ID {item_id} does not belong to Invoice #{instance.invoice_id}"
                        })
                    # Update existing item
                    item = current_items[item_id]
                    '''
                    for key, value in item_data.items():
                        setattr(item, key, value)
                    '''
                    for key, value in item_data.items():
                        # if key not in ['id', 'item_id']:  # Don't update the id field
                        if key != 'item_id':  # Don't update primary key
                                setattr(item, key, value)
                    item.save()
                    # sent_item_ids.append(item_id)

                else:
            # ✅ Only create a new item if no id is provided at all
                    item_data.pop('item_id', None)
                    # item_data.pop('id', None)
                    InvoiceItem.objects.create(invoice=instance, **item_data)

        instance.calculate_amounts()
        instance.save()
        return instance
    

#-------------------------------------------------------------------------------------------------------------------------
class NewQuoteItemSerializer(serializers.Serializer):
    quote_description = serializers.CharField()
    quantity = serializers.IntegerField(min_value=1)
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2)

class NewQuoteCreateSerializer(serializers.Serializer):
    client = serializers.IntegerField()
    vat_rate = serializers.DecimalField(max_digits=5, decimal_places=2, default=0)
    issue_date = serializers.DateField()
    due_date = serializers.DateField()
    items = NewQuoteItemSerializer(many=True)

class NewInvoiceCreateSerializer(serializers.Serializer):
    client = serializers.IntegerField()
    vat_rate = serializers.DecimalField(max_digits=5, decimal_places=2, default=0)
    issue_date = serializers.DateField()
    due_date = serializers.DateField()
    bank_name = serializers.CharField(required=False, allow_blank=True)
    account_name = serializers.CharField(required=False, allow_blank=True)
    sort_code = serializers.CharField(required=False, allow_blank=True)
    account_no = serializers.CharField(required=False, allow_blank=True)
    items = NewQuoteItemSerializer(many=True)

class NewQuoteItemResponseSerializer(serializers.ModelSerializer):
    total = serializers.SerializerMethodField()

    def get_total(self, obj):
        return float(obj.quantity * obj.unit_price)

    class Meta:
        model = QuoteItem
        fields = ['quote_description', 'quantity', 'unit_price', 'total']

class NewQuoteResponseSerializer(serializers.ModelSerializer):
    items = NewQuoteItemResponseSerializer(many=True)
    bill_to = serializers.SerializerMethodField()
    from_details = serializers.SerializerMethodField()
    client_logo = serializers.SerializerMethodField()
    vat_amount = serializers.SerializerMethodField()

    def get_bill_to(self, obj):
        return {
            "name": obj.client.name,
            "address": obj.client.address,
            "email": obj.client.email,
            "phone": obj.client.phone_number,
        }

    def get_from_details(self, obj):
        bp = getattr(obj.user, 'business_profile', None)
        return {
            "business_name": bp.business_name if bp else obj.user.email,
            "email": obj.user.email,
            "contact": bp.whatsapp_number if bp else None,
            "logo": self.context['request'].build_absolute_uri(bp.logo.url) if bp and bp.logo else None,
        }

    def get_client_logo(self, obj):
        bp = getattr(obj.user, 'business_profile', None)
        if bp and bp.logo:
            return self.context['request'].build_absolute_uri(bp.logo.url)
        return None

    def get_vat_amount(self, obj):
        return float(obj.subtotal * obj.vat_rate / 100)

    class Meta:
        model = Quote
        fields = [
            'quote_id', 'quote_number', 'issue_date', 'due_date',
            'client_logo', 'bill_to', 'from_details',
            'items', 'subtotal', 'vat_rate', 'vat_amount', 'total',
            'accept_link', 'quote_status',
        ]

# ...existing code...

class QuoteListRetrieveSerializer(serializers.ModelSerializer):
    """Serializer for GET /quotes/ and GET /quotes/{id}/ - matches new-create response format"""
    items = NewQuoteItemResponseSerializer(many=True)
    bill_to = serializers.SerializerMethodField()
    from_details = serializers.SerializerMethodField()
    client_logo = serializers.SerializerMethodField()
    vat_amount = serializers.SerializerMethodField()
    client_details = serializers.SerializerMethodField()
    # effective_service_location = serializers.SerializerMethodField()

    def get_bill_to(self, obj):
        return {
            "name": obj.client.name,
            "address": obj.client.address,
            "email": obj.client.email,
            "phone": obj.client.phone_number,
        }

    def get_from_details(self, obj):
        bp = getattr(obj.user, 'business_profile', None)
        request = self.context.get('request')
        return {
            "business_name": bp.business_name if bp else obj.user.email,
            "email": obj.user.email,
            "contact": bp.whatsapp_number if bp else None,
            "logo": request.build_absolute_uri(bp.logo.url) if request and bp and bp.logo else None,
        }

    def get_client_logo(self, obj):
        bp = getattr(obj.user, 'business_profile', None)
        request = self.context.get('request')
        if request and bp and bp.logo:
            return request.build_absolute_uri(bp.logo.url)
        return None

    def get_vat_amount(self, obj):
        return float(obj.subtotal * obj.vat_rate / 100)

    def get_client_details(self, obj):
        return obj.client_details

    # def get_effective_service_location(self, obj):
    #     return obj.effective_service_location

    class Meta:
        model = Quote
        fields = [
            'quote_id', 'quote_number', 'issue_date', 'due_date',
            'client', 'folder', 'source',
            'client_logo', 'bill_to', 'from_details', 'client_details',
            'items',
            'subtotal', 'vat_rate', 'vat_amount', 'total',
            'accept_link', 'quote_status',
            'sent_via', 'sent_at',
            'pdf_file', 'service_location',
            'is_deleted', 'deleted_at', 'pdf_generated_at', 'can_edit',
            'created_at', 'updated_at',
        ]
#------------------------------------------------------------------------------------------------------------------------
class NewInvoiceItemResponseSerializer(serializers.ModelSerializer):
    total = serializers.SerializerMethodField()

    def get_total(self, obj):
        return float(obj.quantity * obj.unit_price)

    class Meta:
        model = InvoiceItem
        fields = ['quote_description', 'quantity', 'unit_price', 'total']


class NewInvoiceResponseSerializer(serializers.ModelSerializer):
    items = NewInvoiceItemResponseSerializer(many=True)
    bill_to = serializers.SerializerMethodField()
    from_details = serializers.SerializerMethodField()
    client_logo = serializers.SerializerMethodField()
    vat_amount = serializers.SerializerMethodField()

    def get_bill_to(self, obj):
        return {
            "name": obj.client.name,
            "address": obj.client.address,
            "email": obj.client.email,
            "phone": obj.client.phone_number,
        }

    def get_from_details(self, obj):
        bp = getattr(obj.user, 'business_profile', None)
        return {
            "business_name": bp.business_name if bp else obj.user.email,
            "email": obj.user.email,
            "contact": bp.whatsapp_number if bp else None,
            "logo": self.context['request'].build_absolute_uri(bp.logo.url) if bp and bp.logo else None,
        }

    def get_client_logo(self, obj):
        bp = getattr(obj.user, 'business_profile', None)
        if bp and bp.logo:
            return self.context['request'].build_absolute_uri(bp.logo.url)
        return None

    def get_vat_amount(self, obj):
        return float(obj.subtotal * obj.vat_rate / 100)

    class Meta:
        model = Invoice
        fields = [
            'invoice_id', 'invoice_number', 'issue_date', 'due_date',
            'client_logo', 'bill_to', 'from_details',
            'items', 'subtotal', 'vat_rate', 'vat_amount', 'total',
            'payment_link', 'payment_status',
            'bank_name', 'account_name', 'sort_code', 'account_no',
        ]

