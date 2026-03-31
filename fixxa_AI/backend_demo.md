#Here is my full quoteapp and clientapp code(models.py, serializers.py , views.py).

quoteapp
from django.db import models
from django.db import transaction
from authapp.models import User
# from clientapp.models import Client❌reason circular import
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
from django.core.validators import MinValueValidator
import os
from django.conf import settings
from django.utils import timezone
from quoteapp.utils import get_client_upload_path
import uuid
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP


def scanned_image_upload_path(instance, filename):
    """
    media/scanned_documents/<user_id>/<filename>
    """
    return f"scanned_documents/{instance.user.id}/{filename}"

def ensure_scanned_folder(user):
    folder, created = Folder.objects.get_or_create(
        user=user,
        folder_name="Scanned Documents"
    )
    return folder

#GPT
def quote_pdf_upload_path(instance, filename):
    """Store quote PDFs in client-specific folder"""
    return get_client_upload_path(instance, "quotes", filename)


def invoice_pdf_upload_path(instance, filename):
    """Store invoice PDFs in client-specific folder"""
    return get_client_upload_path(instance, "invoices", filename)


def quote_signature_upload_path(instance, filename):
    """Store quote signatures inside client folder"""
    return get_client_upload_path(instance, os.path.join("signatures", "quotes"), filename)


def invoice_signature_upload_path(instance, filename):
    """Store invoice signatures inside client folder"""
    return get_client_upload_path(instance, os.path.join("signatures", "invoices"), filename)


class ServiceDocumentBase(models.Model):
    """Abstract base model for Quote and Invoice with common properties"""
    
    client = models.ForeignKey(
        "clientapp.Client",
        on_delete=models.CASCADE,
        related_name="%(class)ss"
    )
    class Meta:
        abstract = True

    @property
    def client_details(self):
        """Returns client contact information in a consistent way"""
        if not self.client:
            return {}
        return {
            "name": self.client.name,
            "email": self.client.email,
            "phone": self.client.phone_number,
            "address": self.client.address,
        }   
    
    @property
    def effective_service_location(self):
        """Returns service location or client address if not specified"""
        if hasattr(self, 'service_location') and self.service_location:
            return self.service_location
        elif hasattr(self, 'client') and self.client:
            return self.client.address
        return None

#claude
class Folder(models.Model):
    """Folder for organizing quotes"""
    folder_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='folders')
    folder_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('folder')
        verbose_name_plural = _('folders')
        ordering = ['folder_name']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'folder_name'],
                name='unique_folder_name_per_user'
            )
        ]
    
    def __str__(self):
        return self.folder_name


class ScannedDocument(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='scanned_documents')
    client = models.ForeignKey('clientapp.Client', on_delete=models.CASCADE, related_name='scanned_docs', null=True, blank=True)  # ADD THIS
    folder = models.ForeignKey(Folder, on_delete=models.CASCADE, related_name='scanned_images', null=True, blank=True)  # ADD THIS BACK
    image = models.ImageField(upload_to=scanned_image_upload_path)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'scanned_documents'
        ordering = ['-created_at']


    def __str__(self):
        return f"Scanned document ({self.id})"

        # return f"{self.document_type.capitalize()} scan for {self.client.name}"

class QuoteCounter(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    year = models.IntegerField()
    counter = models.IntegerField(default=0)

    class Meta:
        unique_together = ('user', 'year')

#claude : 18th aug
class Quote(ServiceDocumentBase):#used for manual/voice quote creation, to handle voice quote , we used voicenote model(which has a relationship with Quote)
    """Quote/Proposal model"""
    SOURCE_CHOICES = [
        ('manual', 'Manual'),
        ('voice', 'Voice'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Draft'),  # Initial state
        ('sent', 'Sent'),    # Sent to client
        # ('viewed', 'Viewed'),  # Client opened the quote
        ('won', 'Won'),  # Client explicitly accepted
        ('lost', 'Lost'),  # Client explicitly rejected
        # ('expired', 'Expired'),  # No response after expiry
        # ('paid', 'Paid'),     # Payment received
    ]


    SENT_VIA_CHOICES = [
        ('email', 'Email'),
        ('whatsapp', 'WhatsApp'),
        ('both', 'Both'),
        ('none', 'None'),
    ]

    DISCOUNT_TYPE_CHOICES = [  # CHANGED: Added discount type
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount'),
    ]
    DURATION_UNIT_CHOICES = [
        ('days', 'Days'),
        ('hours', 'Hours'),
    ]
    quote_id = models.AutoField(primary_key=True)
    quote_number = models.CharField(max_length=50, unique=True, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quotes')
    client = models.ForeignKey('clientapp.Client', on_delete=models.CASCADE, related_name='quotes')
    folder = models.ForeignKey(Folder, on_delete=models.SET_NULL, null=True, blank=True, related_name='quotes')
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default='manual')
    subtotal = models.DecimalField(_('subtotal'), max_digits=10, decimal_places=2)  # Sum of all amounts    
    discount_amount = models.DecimalField(_('discount amount'), max_digits=10, decimal_places=2, default=0.00)
    discount_type = models.CharField(_('discount type'), max_length=10, choices=DISCOUNT_TYPE_CHOICES, default='percentage')
    # vat_rate = models.DecimalField(_('VAT rate'), max_digits=5, decimal_places=2, default=20.00)  # CHANGED: Renamed from vat
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)

    total = models.DecimalField(_('total'), max_digits=10, decimal_places=2)  # Subtotal + VAT - Discount

    issue_date = models.DateField(_('issue date'))
    #Due will work as deadline, after this date, the quote will be rejected
    due_date = models.DateField(_('due date'))
    # due_date = models.CharField(max_length=20)
    duration_unit = models.CharField(max_length=10, choices=DURATION_UNIT_CHOICES, default='hours')
    quote_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    sent_via = models.CharField(max_length=20, choices=SENT_VIA_CHOICES, default='none')
    sent_at = models.DateTimeField(null=True, blank=True)
    signature = models.ImageField(
        upload_to=quote_signature_upload_path,
        null=True,
        blank=True
    )
    pdf_file = models.FileField(
        _('PDF file'),
        upload_to=quote_pdf_upload_path,
        null=True,
        blank=True
    )
    csv_file = models.FileField(upload_to=quote_pdf_upload_path, null=True, blank=True)
    excel_file = models.FileField(upload_to=quote_pdf_upload_path, null=True, blank=True)
    #will use here address from client table by using property
    service_location = models.CharField(
        _('service location'), 
        max_length=255, 
        blank=True, 
        null=True,
        help_text=_('Leave blank to use client address')
    )    #  services can be done in different addresses thats why used this field(not always in client address)
    
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    pdf_generated_at = models.DateTimeField(null=True, blank=True)
    can_edit = models.BooleanField(default=True)  # False after PDF generation

    accept_link = models.URLField(blank=True, null=True)#by own
    reject_link = models.URLField(blank=True, null=True)#by own

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    
    def calculate_totals(self):
        items = self.items.all()
        # Convert to Decimal safely
        def to_decimal(value):
            try:
                return Decimal(str(value))
            except:
                return Decimal('0.00')
        # Calculate service charge (duration × rate)
        service_charge = sum(
            item.service_duration * item.service_rate 
            for item in items
        ) if items else Decimal('0.00')
        
        # Calculate material cost (quantity × unit_price)
        material_cost = sum(
            item.quantity * item.unit_price 
            for item in items
        ) if items else Decimal('0.00')
        
        # Subtotal = service charge + material cost
        self.subtotal = service_charge + material_cost

        # Apply discount
        discount_value = Decimal('0.00')
        if self.discount_amount > 0:
            if self.discount_type == 'percentage':
                discount_value = self.subtotal * (self.discount_amount / Decimal('100.00'))
            else:
                discount_value = self.discount_amount

        subtotal_after_discount = self.subtotal - discount_value

        # Calculate VAT and total
        vat_amount = subtotal_after_discount * (self.vat_rate / Decimal('100.00'))
        # self.total = max(self.subtotal + vat_amount - discount_value, Decimal('0.00'))
        self.total = max(subtotal_after_discount + vat_amount, Decimal('0.00'))


    def save(self, *args, **kwargs):
      
        if 'pdf_file' in kwargs or (hasattr(self, 'pdf_file') and self.pdf_file and not self.pdf_generated_at):
            self.pdf_generated_at = timezone.now()
            self.can_edit = False
        
        super().save(*args, **kwargs)

  
    @transaction.atomic
    def generate_quote_number(self):
        year = timezone.now().year

        counter_obj, created = QuoteCounter.objects.select_for_update().get_or_create(
            user=self.user,
            year=year
        )

        counter_obj.counter += 1
        counter_obj.save()

        return f"QT-{year}-{counter_obj.counter:04d}"
    
    class Meta:
        db_table = 'quotes'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'quote_status']),
            models.Index(fields=['client']),
            models.Index(fields=['created_at']),
            models.Index(fields=['user', 'is_deleted']),
        ]
        
    def __str__(self):
        return f"Quote #{self.quote_id} - {self.client.name}"
    
'''
1. If you only keep Quote

Your Quote can store just one service/item (since you already added duration, rate, tax_rate etc. inside Quote).

That means each quote = exactly 1 line item.

But in your screenshot, a single quote clearly has multiple items (Item 1, Item 2, Item 3) → so this won’t fit.

2. If you add QuoteItem

Quote will be the header/master record → client, total, VAT, status, issue date, due date.

QuoteItem will be the line items → description, duration, rate, tax per item.

Each Quote can have multiple QuoteItems (1:N relationship).

Totals in Quote will be calculated from its items (sum of all QuoteItem.amount → subtotal, then apply VAT, discount, etc.).
'''


#QuoteItem stores all the row details.

class QuoteItem(models.Model):
    DURATION_UNIT_CHOICES = [
        ('days', 'Days'),
        ('hours', 'Hours'),
    ]
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name='items')
    quote_description = models.TextField()
    material_name = models.CharField(max_length=255, blank=True, null=True)
    quantity = models.IntegerField(validators=[MinValueValidator(1)],default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)],default=0.00)
    # amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])

    service_type= models.CharField(_('service name'), max_length=255,default='General Service')
    service_duration = models.DecimalField(max_digits=10, decimal_places=2,default=1)
    duration_unit = models.CharField(max_length=10, choices=DURATION_UNIT_CHOICES, default='hours')
    service_rate = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)],default=0.00)    
   
    def save(self, *args, **kwargs):

        super().save(*args, **kwargs)

    class Meta:
        db_table = 'quote_items'

    def __str__(self):
        return f"Item for Quote #{self.quote.quote_id} - {self.service_type}"



class InvoiceCounter(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    year = models.IntegerField()
    counter = models.IntegerField(default=0)

    class Meta:
        unique_together = ('user', 'year')


class Invoice(ServiceDocumentBase):
    """Final invoice matching your template exactly"""
    SOURCE_CHOICES = Quote.SOURCE_CHOICES 

    PAYMENT_SPEED_CHOICES = [
        ('standard', 'Standard Payment'),
        ('faster', 'Faster Payment'),
    ]

    PAYMENT_STATUS_CHOICES = [
        # ('draft', 'Draft'),
        # ('sent', 'Sent'),
        ('unpaid', 'Unpaid'),
        ('partial', 'Partially Paid'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),#delayed
    ]

    SENT_VIA_CHOICES = Quote.SENT_VIA_CHOICES
    DISCOUNT_TYPE_CHOICES = Quote.DISCOUNT_TYPE_CHOICES
    DURATION_UNIT_CHOICES = Quote.DURATION_UNIT_CHOICES
    # Core fields
    invoice_id = models.AutoField(primary_key=True)
    invoice_number = models.CharField(max_length=50, unique=True)

    
    quote = models.ForeignKey(Quote, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='invoices')
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default='manual')

    payment_speed = models.CharField(
    max_length=20,
    choices=PAYMENT_SPEED_CHOICES,
    default='standard',
    help_text='Payment processing speed option'
    )
    discount_amount = models.DecimalField(_('discount amount'), max_digits=10, decimal_places=2,validators=[MinValueValidator(0)] ,default=0.00)
    discount_type = models.CharField(_('discount type'), max_length=10, choices=DISCOUNT_TYPE_CHOICES, default='percentage')
    # amount = models.DecimalField(_('amount'), max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    subtotal = models.DecimalField(_('subtotal'), max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    vat_rate = models.DecimalField(_('VAT rate'), max_digits=5, decimal_places=2, default=20.00)
    total = models.DecimalField(_('total'), max_digits=10, decimal_places=2, validators=[MinValueValidator(0)],default=0.00)
    folder = models.ForeignKey(Folder, on_delete=models.SET_NULL, null=True, related_name='invoices')


    quote_status = models.CharField(max_length=20, choices=Quote.STATUS_CHOICES, default='unpaid')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='unpaid')
    sent_via = models.CharField(max_length=20, choices=SENT_VIA_CHOICES, default='none')#deeps: 19th sep
    sent_at = models.DateTimeField(null=True, blank=True)#deeps: 19th sep  
    issue_date = models.DateField(_('issue date'))
    #Due will work as deadline, after this date, the quote will be rejected
    due_date = models.DateField(_('due date'))
    paid_date = models.DateField(_('paid date'), null=True, blank=True)


    signature = models.ImageField(
        upload_to=invoice_signature_upload_path,
        null=True,
        blank=True
    )
    # PDF and sending
    # pdf_file = models.FileField(upload_to='invoices/', null=True, blank=True)
    pdf_file = models.FileField(
        upload_to=invoice_pdf_upload_path,
        null=True,
        blank=True
    )
    csv_file = models.FileField(upload_to=invoice_pdf_upload_path, null=True, blank=True)
    excel_file = models.FileField(upload_to=invoice_pdf_upload_path, null=True, blank=True)
    # folder = models.ForeignKey(Folder, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices')
    # CHANGED: Added PDF generation tracking
    pdf_generated_at = models.DateTimeField(null=True, blank=True)
    can_edit = models.BooleanField(default=True)  # False after PDF generation

    # Payment link (for Stripe integration later)
    # payment_link = models.URLField(blank=True, null=True)#deeps: 19th sep
    payment_link = models.URLField(max_length=1000, blank=True, null=True)

    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    # Mark as paid toggle
    is_paid = models.BooleanField(default=False)#deeps: 19th sep

    discount_type = models.CharField(
        _('discount type'),
        max_length=10,
        choices=DISCOUNT_TYPE_CHOICES,  # Reuse from Quote
        default='percentage'
    )
    duration_unit = models.CharField(
        max_length=10,
        choices=DURATION_UNIT_CHOICES,  # Reuse from Quote.DURATION_UNIT_CHOICES
        default='hours'
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def effective_service_location(self):
        """Return service location from quote if exists, else client address, else N/A"""
        if self.quote and getattr(self.quote, 'service_location', None):
            return self.quote.service_location
        elif hasattr(self, 'client') and getattr(self.client, 'address', None):
            return self.client.address
        return 'N/A'
   

    def calculate_amounts(self):
        """Calculate totals based on InvoiceItem amounts with service charge + material cost"""
        from decimal import Decimal, ROUND_HALF_UP
        
        items = self.items.all()
        
        # Calculate service charge (duration × rate)
        service_charge = sum(
            Decimal(str(item.service_duration)) * Decimal(str(item.service_rate))
            for item in items
        ) if items else Decimal('0.00')
        service_charge = service_charge.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # Calculate material cost (quantity × unit_price)
        material_cost = sum(
            Decimal(str(item.quantity)) * Decimal(str(item.unit_price))
            for item in items
        ) if items else Decimal('0.00')
        material_cost = material_cost.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # Subtotal = service charge + material cost
        self.subtotal = (service_charge + material_cost).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # Apply discount
        discount_value = Decimal('0.00')
        if self.discount_amount > 0:
            if self.discount_type == 'percentage':
                discount_value = (
                    self.subtotal * (Decimal(str(self.discount_amount)) / Decimal('100.00'))
                ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            else:  # fixed
                discount_value = Decimal(str(self.discount_amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            subtotal_after_discount = max(
                (self.subtotal - discount_value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                Decimal('0.00')
            )
        vat_amount = (
            subtotal_after_discount * (Decimal(str(self. vat_rate)) / Decimal('100.00'))
        ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.total = max(subtotal_after_discount + vat_amount, Decimal('0.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
  
    # CHANGED: Added PDF generation logic and payment status update in save method
    def save(self, *args, **kwargs):
        # if not self.invoice_number:
        #     self.invoice_number = self.generate_invoice_number()
            
        if 'pdf_file' in kwargs or (hasattr(self, 'pdf_file') and self.pdf_file and not self.pdf_generated_at):
            self.pdf_generated_at = timezone.now()
            self.can_edit = False  # Lock edits after PDF
        # self.calculate_amounts()  # Recalculate totals before saving is harmful in model, it'll case this error 'Failed to create invoice 'Invoice' instance needs to have a primary key value before this relationship can be used.'
        
        # Update status based on payment
        if self.is_paid :
            self.quote_status = 'paid'
            if not self.paid_date:
                self.paid_date = timezone.now().date()
        elif not self.is_paid and self.quote_status == 'paid':
        # If unpaying, revert to sent or unpaid
            self.quote_status = 'unpaid'
            self.paid_date = None
        
        # Check for overdue (if past due_date and still unpaid)
        if self.quote_status == 'unpaid' and self.due_date:
            try:
                due = timezone.datetime.strptime(self.due_date, '%Y-%m-%d').date()
                if due < timezone.now().date():
                    self.quote_status = 'overdue'
            except:
                pass
        super().save(*args, **kwargs) 

    
    class Meta:
        db_table = 'invoices'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'quote_status']),
            models.Index(fields=['client']),
            models.Index(fields=['created_at']),
            models.Index(fields=['invoice_number']),
        ]
    
    def __str__(self):
        return f"Invoice #{self.invoice_number} - {self.client.name}"


# REMOVED: InvoiceItem model as we're using single-item invoices for now
# Can be added later when multi-item support is needed

class InvoiceItem(models.Model):
    """Line items for invoices (simpler version)"""
    item_id = models.AutoField(primary_key=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    material_name = models.CharField(max_length=500, blank=True, null=True)
    quote_description = models.TextField(blank=True, null=True)  # ADD THIS

    quantity = models.IntegerField(validators=[MinValueValidator(1)],default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], default=0.00)
    # amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    
    service_duration = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)],default=1)
    service_type = models.CharField(_('service name'), max_length=255, default='General Service')
    service_rate = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)],default=0)
    duration_unit = models.CharField(max_length=10, choices=QuoteItem.DURATION_UNIT_CHOICES, default='hours')

    def save(self, *args, **kwargs):
        # freeze_totals = kwargs.pop('freeze_totals', False)
        super().save(*args, **kwargs)

    class Meta:
        db_table = 'invoice_items'


class QuoteToken(models.Model):
    """Store secure tokens for quote accept/reject with expiry"""
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name='tokens')
    token = models.UUIDField(default=uuid.uuid4, unique=True)  # Secure random token
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()  # Token expiry (e.g., 30 days)
    is_used = models.BooleanField(default=False)  # Mark as used after action
    
    class Meta:
        db_table = 'quote_tokens'
        
    def is_valid(self):
        """Check if token is still valid"""
        return not self.is_used and timezone.now() < self.expires_at
    
    def save(self, *args, **kwargs):
        # Auto-set expiry to 30 days from now if not set
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(days=30)
        super().save(*args, **kwargs)

serializers.py 

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

    source = serializers.CharField(read_only=True)
    items = QuoteItemSerializer(many=True, required=False)  # Added for items
    effective_service_location = serializers.SerializerMethodField()
    vat_amount = serializers.SerializerMethodField()  # 4th dec
    discount_value = serializers.SerializerMethodField()  #4th dec

    def get_client_details(self, obj):
        return obj.client_details
    
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

        validated_data['subtotal'] = Decimal('0.00')
        validated_data['total'] = Decimal('0.00')

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
    
views.py 


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
===================================================================Scan ===================================================================

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

    def list(self, request, *args, **kwargs):
        """
        Get quotes with filtering and pagination
        Supports status, source, client, folder, and date range filters
        """
        try:
            queryset = self.filter_queryset(self.get_queryset())

            # Status filter
            status_filter = request.query_params.get('status')#The API endpoint receives ?status=draft from the frontend, so you need:
            '''
            URL parameter name: status (what the frontend sends), so .get('status') is correct
            Database field name: quote_status (what Django ORM uses)
            '''
            if status_filter:
                if status_filter == 'sent':
                    queryset = queryset.filter(quote_status__in=['sent', 'won', 'lost'])
                else:
                    queryset = queryset.filter(quote_status=status_filter)

            # Source filter (voice/manual)
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
                serializer = self.get_serializer(page, many=True)
                
                # return self.get_paginated_response(serializer.data)

                paginated_response = self.get_paginated_response(serializer.data)
                return self.success_response(
                    paginated_response.data,
                    "Data fetched successfully"
                )
            
            serializer = self.get_serializer(queryset, many=True)
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
                short_uid = "-".join(str(request.user.id).split('-')[:2])# first block of UUID
                # validated_data['invoice_number'] = f"INV-{request.user.id}-{year}-{counter_obj.counter:04d}"
                validated_data['quote_number'] = f"QT-{short_uid}-{year}-{counter_obj.counter:04d}"
                
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
                email_body = f"""
                Dear {quote.client.name},
                
                Please find attached Quote #{quote.quote_number} for your review.
                
                Issue Date: {quote.issue_date}
                Due Date: {quote.due_date}
                Total Amount: £{quote.total}
                
                Please review and respond:
                ✅ Accept Quote: {quote.accept_link}
                ❌ Reject Quote: {quote.reject_link}
                
                This link expires on {quote_token.expires_at.strftime('%Y-%m-%d')}.
                
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

            return self.success_response(QuoteSerializer(quote).data, f"Quote sent successfully via {sent_via}")
        except Exception as e:
            logger.error(f"Quote send error: {str(e)}")
            return self.error_response(f"Failed to send quote {e}", status.HTTP_500_INTERNAL_SERVER_ERROR)


    @action(detail=True, methods=['post'], url_path='generate-pdf')
    def generate_pdf(self, request, pk=None):

        try:
            quote = self.get_object()
            if quote.pdf_file and quote.pdf_generated_at:
                return self.error_response("PDF already generated", status.HTTP_400_BAD_REQUEST)

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

            # ====================== 🧾 CSV Export ======================
            elif export_type == 'csv':
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow([
                    'Description', 'Service Type', 'Material Name', 'Quantity', 
                    'Unit Price', 'Service Duration', 'Duration Unit', 'Service Rate', 'Total'
                ])

                for item in quote.items.all():
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

                # ✅ Save CSV to client folder
                csv_filename = f"quote_{quote.quote_number}.csv"
                quote.csv_file.save(csv_filename, ContentFile(output.getvalue()), save=True)
                
                response = HttpResponse(output.getvalue(), content_type='text/csv')
                # response['Content-Disposition'] = f'attachment; filename="quote_{quote.quote_number}.csv"'
                response['Content-Disposition'] = f'attachment; filename="{csv_filename}"'

                return response

            # ====================== 📊 Excel Export ======================
            elif export_type == 'excel':
                data = []
                for item in quote.items.all():
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

                df = pd.DataFrame(data)
                output = io.BytesIO()
                df.to_excel(output, index=False, engine='openpyxl')
                output.seek(0)

                # ✅ Save Excel file to client folder
                excel_filename = f"quote_{quote.quote_number}.xlsx"
                quote.excel_file.save(excel_filename, ContentFile(output.getvalue()), save=True)

                response = HttpResponse(
                    output.getvalue(),
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
                # response['Content-Disposition'] = f'attachment; filename="quote_{quote.quote_number}.xlsx"'
                response['Content-Disposition'] = f'attachment; filename="{excel_filename}"'

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
            if not quote_token.is_valid():
                return self.error_response("Token has expired or already been used", status.HTTP_403_FORBIDDEN)
            
            if quote.quote_status != 'sent':
                return self.error_response(f"Cannot accept quote with status: {quote.quote_status}", status.HTTP_400_BAD_REQUEST)
            
            # Update quote status
            quote.quote_status = 'won'
            quote.save()

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
            
            return self.success_response({"quote_id": quote.quote_id}, "Quote accepted successfully")
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

    def _send_quote_notification(self, quote, sent_via):
        """Stub: integrate with Email/WhatsApp later"""
        logger.info(f"Quote {quote.quote_id} sent via {sent_via}")
        return True            
            
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
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                # return self.get_paginated_response(serializer.data)
                paginated_response = self.get_paginated_response(serializer.data)
                return self.success_response(
                    paginated_response.data,
                    "Data fetched successfully"
                )

            serializer = self.get_serializer(queryset, many=True)
            return self.success_response(serializer.data, "Invoices fetched successfully")
            
        except Exception as e:
            logger.error(f"Invoice list error: {str(e)}")
            return self.error_response(f"Failed to fetch invoices {e}", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
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

            folder_name = f"{client.name.replace(' ', '_')}"

           
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

                short_uid = "-".join(str(request.user.id).split('-')[:2])# first block of UUID
                # validated_data['invoice_number'] = f"INV-{request.user.id}-{year}-{counter_obj.counter:04d}"
                validated_data['invoice_number'] = f"INV-{short_uid}-{year}-{counter_obj.counter:04d}"


                invoice = Invoice.objects.create(**validated_data)
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

     #added 9th october
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

stripe.api_key = settings.STRIPE_SECRET_KEY

def payment_success_view(request):
    session_id = request.GET.get('session_id')
    invoice_id = request.GET.get('invoice_id')#claude-2nd

    if not session_id:
        return HttpResponse("<h3>Session ID missing.</h3>", status=400)
    
    try:

        invoice = Invoice.objects.get(invoice_id=invoice_id)#claude-2nd

        if not invoice.is_paid:#means “if the invoice is not already paid” — so it updates it to paid only once (to avoid re-saving or overwriting an already-paid invoice).
            invoice.is_paid = True
            invoice.payment_status = 'paid'
            invoice.paid_date = timezone.now().date()
            invoice.save()

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
                invoice.is_paid = True
                invoice.payment_status = 'paid'
                invoice.paid_date = timezone.now().date()
                invoice.save()
                logger.info(f"Invoice {invoice_id} marked paid")
            except Invoice.DoesNotExist:
                logger.error(f"Invoice {invoice_id} not found")
    
    return HttpResponse(status=200)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_invoice_from_quote(request, quote_id):
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

            )

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

clientapp
models.py 
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.db.models import Sum
from authapp.models import User

import os  # Added for creating filesystem folders
from django.conf import settings  # Added for MEDIA_ROOT

class Client(models.Model):

    SOURCE_CHOICES = [
        ('manual', 'Manual Entry'),
        ('imported', 'Imported from Contacts'),
    ]
    
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default='manual')
    
    user = models.ForeignKey(# This is required by default
        User,
        on_delete=models.CASCADE,
        related_name='clients'
    )
    name = models.CharField(_('name'), max_length=255)# This is required by default

    email = models.EmailField(_('email'), blank=True, null=True)
    phone_number = models.CharField(_('phone number'), max_length=20)
    image = models.ImageField(
        _('image'),
        upload_to='client_images/',
        
        blank=True,
        null=True
    )

    address = models.TextField(_('address'), blank=True, null=True)

    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    @property
    def quotes_folder(self):
        return os.path.join(self.folder_path, "quotes")

    @property
    def invoices_folder(self):
        return os.path.join(self.folder_path, "invoices")

    # ---------- Save override ----------
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)

        if is_new:
            # Root folder
            abs_root = os.path.join(settings.MEDIA_ROOT, self.folder_path)

            # Subfolders
            abs_quotes = os.path.join(abs_root, "quotes")
            abs_invoices = os.path.join(abs_root, "invoices")
            abs_signatures_quotes = os.path.join(abs_root, "signatures", "quotes")
            abs_signatures_invoices = os.path.join(abs_root, "signatures", "invoices")

            # Create all dirs
            os.makedirs(abs_quotes, exist_ok=True)
            os.makedirs(abs_invoices, exist_ok=True)
            os.makedirs(abs_signatures_quotes, exist_ok=True)
            os.makedirs(abs_signatures_invoices, exist_ok=True)

            try:
                from django.apps import apps
                Folder = apps.get_model('quoteapp', 'Folder')
                # folder_name = f"{self.id}_{self.name.replace(' ', '_')}"
                folder_name = f"{self.name.replace(' ', '_')}"
                Folder.objects.get_or_create(
                    user=self.user,
                    folder_name=folder_name
                )
            except Exception as e:
                print(f"⚠️ DB Folder creation skipped: {e}")

    @property
    def folder_path(self):
        # Every client gets its own folder under MEDIA_ROOT/clients/
        return os.path.join("clients", f"{self.id}_{self.name.replace(' ', '_')}")
    #=================================================================================
    class Meta:
        verbose_name = _('client')
        verbose_name_plural = _('clients')
        ordering = ['name']
        db_table = 'clients'

    
    def __str__(self):
        return self.name

class ClientService(models.Model):
    """Represents individual services provided to a client"""

    #p: The Client model has a one-to-many relationship with ClientService (one client can have multiple services), as indicated by the related_name='services' in the ClientService model.

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='services'
    )

    quote = models.ForeignKey('quoteapp.Quote', 
        on_delete=models.CASCADE, 
        related_name='client_services'
    )

    notes = models.TextField(_('notes'), blank=True, null=True)

    @property
    def quote_sent_date(self):
        return self.quote.sent_at if self.quote_id else None

    @property
    def amount_earned(self):
        if not self.quote_id:
            return None
        invoice = self.quote.invoices.first()  # ✅ correct reverse relation
        return invoice.total if invoice else None
  

    @property
    def service_type(self):
        # Fix: Use first QuoteItem's description (or add 'description' to Quote model)
        first_item = self.quote.items.first() if self.quote else None
        return first_item.service_type if first_item else None

    @property
    def status(self):
        return self.quote.quote_status if self.quote else None  # Access status from the related Quote model through the relationship
    
    @property
    def service_location(self):
        return self.quote.effective_service_location # Access service_type from the related Quote model
    
    class Meta:
        verbose_name = _('client service')
        verbose_name_plural = _('client services')
        # ordering = ['-quote__sent_date']
        ordering = ['-id']  # ✅ Changed from ['-quote__sent_date'], because ❌quote_sent_date is a property, not a database field. This will cause errors. 

        db_table = 'client_services'

    def __str__(self):
     return f"{self.client.name} - {getattr(self.quote.items.first(), 'quote_description', 'NO description provided')}"



serializers.py 


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
    """Serializer for client creation and updates with validation"""

    class Meta:
        model = Client
        fields = [
            'id',
            'name',
            'email',
            'phone_number',
            'image',
            'address',
            'source'
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
        """Cross-field validation"""
        # Ensure at least one contact method is provided
        if not data.get('phone_number') and not data.get('email'):
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
        fields = ['quote_id', 'total', 'status', 'created_at','quote_sent_date']


class ClientInvoiceSummarySerializer(serializers.ModelSerializer):
    """Minimal invoice data for client details"""
    status = serializers.CharField(source='get_quote_status_display')

    class Meta:
        model = Invoice
        fields = ['invoice_id', 'invoice_number', 'total', 'status', 'created_at']


views.py 


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
    
    def list(self, request, *args, **kwargs):
        """
        List clients with advanced filtering and search
        Implements caching for frequently accessed lists
        """
        try:
            # Build cache key based on user and filters
            cache_key = f"client_list_{request.user.id}_{request.GET.urlencode()}"
            
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
                cache.delete_pattern(f"client_list_{request.user.id}_*")
                
                # Return detailed client data
                detail_serializer = ClientDetailSerializer(client)
                
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
                cache.delete_pattern(f"client_list_{request.user.id}_*")
                cache.delete(f"client_detail_{client.id}")
                
                # Return detailed client data
                detail_serializer = ClientDetailSerializer(client)
            
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
                cache.delete_pattern(f"client_list_{request.user.id}_*")
                
                # Return detailed client data
                detail_serializer = ClientDetailSerializer(client)
            
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
                'client': ClientDetailSerializer(client).data,
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
                cache.delete_pattern(f"client_list_{request.user.id}_*")
            
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

class ClientServiceViewSet(StandardResponseMixin, viewsets.ModelViewSet):
            """CRUD for ClientService linked to accepted quotes"""
            serializer_class = ClientServiceSerializer
            permission_classes = [IsAuthenticated]
            parser_classes = [MultiPartParser, JSONParser]
        
        
            def get_queryset(self):
                return ClientService.objects.filter(client__user=self.request.user)\
                    .select_related('client', 'quote').order_by('-quote__sent_at')  # Fix ordering
                    
                    
            def list(self, request, *args, **kwargs):

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

