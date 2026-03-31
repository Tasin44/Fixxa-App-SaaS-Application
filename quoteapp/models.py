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

'''
    Quote: A preliminary estimate. It must show the final price including VAT(20%) but does not have a payment link. It's for approval.
    Invoice: The final bill, generated after the quote is accepted. It must have the same total as the quote and includes the payment link.
'''

'''
Folder structure result
When you create a new Client, you’ll get:

media/client_documents/5/12_John_Doe/
    ├── quotes/
    │     └── Q-12345.pdf
    ├── invoices/
    │     └── INV-67890.pdf
    └── signatures/
          ├── quotes/
          │     └── Q-12345_signature.png
          └── invoices/
                └── INV-67890_signature.png

'''


'''
def scanned_image_upload_path(instance, filename):
    """Save scanned images in existing client folders (quotes/invoices)."""
    folder_name = "Scanned photos"
    return get_client_upload_path(instance, folder_name, filename)
'''
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

    '''
    client = instance.client
    safe_name = f"{client.id}_{client.name.replace(' ', '_')}"
    return os.path.join(
        "client_documents",
        str(client.user.id),
        safe_name,
        "quotes",
        filename
    )
    '''

def invoice_pdf_upload_path(instance, filename):
    """Store invoice PDFs in client-specific folder"""
    return get_client_upload_path(instance, "invoices", filename)

    '''
    client = instance.quote.client if instance.quote else None
    if not client:
        # fallback if invoice is not linked to a quote
        return os.path.join("orphan_invoices", filename)

    safe_name = f"{client.id}_{client.name.replace(' ', '_')}"
    return os.path.join(
        "client_documents",
        str(client.user.id),
        safe_name,
        "invoices",
        filename
    )
    '''

def quote_signature_upload_path(instance, filename):
    """Store quote signatures inside client folder"""
    return get_client_upload_path(instance, os.path.join("signatures", "quotes"), filename)


    '''
    client = instance.client
    safe_name = f"{client.id}_{client.name.replace(' ', '_')}"
    return os.path.join(
        "client_documents",
        str(client.user.id),
        safe_name,
        "signatures",
        "quotes",
        filename
    )
    '''

def invoice_signature_upload_path(instance, filename):
    """Store invoice signatures inside client folder"""
    return get_client_upload_path(instance, os.path.join("signatures", "invoices"), filename)

    '''
    client = instance.quote.client if instance.quote else None
    if not client:
        return os.path.join("orphan_signatures", "invoices", filename)

    safe_name = f"{client.id}_{client.name.replace(' ', '_')}"
    return os.path.join(
        "client_documents",
        str(client.user.id),
        safe_name,
        "signatures",
        "invoices",
        filename
    )
    '''

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

    '''
    class ServiceType(models.TextChoices):
        PLUMBING = 'plumbing', _('Plumbing')
        ELECTRICAL = 'electrical', _('Electrical')
        CARPENTRY = 'carpentry', _('Carpentry')
        HVAC = 'hvac', _('HVAC')
        CLEANING = 'cleaning', _('Cleaning')
        LANDSCAPING = 'landscaping', _('Landscaping')
        PAINTING = 'painting', _('Painting')
        APPLIANCE = 'appliance', _('Appliance Repair')
        OTHER = 'other', _('Other')
    '''

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
    # expiry_date = models.DateField(null=True, blank=True)#3,4,7 days
    # signature = models.ImageField(
    #     _('signature'),
    #     upload_to='signatures/'
    # )
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

    #=============================================================================================
    #newly added,will uncomment it at the time of doing hubspot
    # hubspot_deal_id = models.CharField(max_length=50, null=True, blank=True)  # Store HubSpot deal ID
    #=============================================================================================
    
    '''
    #moved them to the ServiceDocumentBase class
    @property
    def client_contact_info(self):
        """Returns client contact information"""
        return {
            'name': self.client.name,
            'email': self.client.email,
            'phone': self.client.phone_number,
            'address': self.client.address
        }

    @property##added:18th aug claude
    def effective_service_location(self):
        """Returns service location or client address if not specified"""
        return self.service_location or self.client.address
    '''

    
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


    '''
    def save(self, *args, **kwargs):
        """Recalculate totals only if relevant fields change"""
        if any(k in kwargs for k in ['subtotal', 'discount_amount', 'discount_type', 'vat_rate']):
            self.calculate_totals()
        super().save(*args, **kwargs)
    '''

    # CHANGED: Added PDF generation logic in save method
    '''
    def save(self, *args, **kwargs):
            if not self.quote_number:
                self.quote_number = self.generate_quote_number()
            """Recalculate totals and handle PDF generation state"""
            if 'pdf_file' in kwargs or (hasattr(self, 'pdf_file') and self.pdf_file and not self.pdf_generated_at):
                self.pdf_generated_at = timezone.now()
                self.can_edit = False  # Lock edits after PDF
                # ✅ Save FIRST to get primary key
            super().save(*args, **kwargs)

            self.calculate_totals()  # Recalculate totals before saving
            # super().save(*args, **kwargs)
            # ✅ Save again only if totals changed
            if self.pk:  # Only if already saved
                Quote.objects.filter(pk=self.pk).update(
                    subtotal=self.subtotal,
                    total=self.total
                )
    
    '''
    def save(self, *args, **kwargs):
      
        # Generate quote number ONLY if creating new quote (no pk yet)
        # DON'T generate quote_number here anymore
        # It's now generated in the view's transaction  
        # # if not self.quote_number:
        '''
        if not self.pk and not self.quote_number:
            self.quote_number = self.generate_quote_number()
        '''

        
        if 'pdf_file' in kwargs or (hasattr(self, 'pdf_file') and self.pdf_file and not self.pdf_generated_at):
            self.pdf_generated_at = timezone.now()
            self.can_edit = False
        
        # ❌ REMOVE THIS LINE
        # self.calculate_totals()
        '''
        ❓❓❓ for the calculate_totals() here I got this error : 
        "Failed to create quote 'Quote' instance needs to have a primary key value before this relationship can be used."
        
        ans: 
        When you call self.calculate_totals() inside save(),
        Django hasn’t yet assigned a primary key (self.pk),
        so self.items.all() fails — because it’s looking for related QuoteItems that can’t exist yet.


        🧠 Why it happens

        Here’s the chain of events:

        You call:

        quote = Quote.objects.create(**validated_data)

        Inside your model’s save(), you call self.calculate_totals().

        But this quote has no items yet (you create them after saving).

        calculate_totals() tries to do something like:

        for item in self.items.all():
            ...

        Django goes: ❌ “Wait, this quote doesn’t have an ID yet — I can’t query related items.”
        '''
        super().save(*args, **kwargs)

    '''
    def generate_quote_number(self):
        """Generate unique quote number"""
        from django.utils import timezone
        year = timezone.now().year
        count = Quote.objects.filter(user=self.user, created_at__year=year).count() + 1
        return f"QT-{year}-{count:04d}"
    '''

    '''
    def generate_quote_number(self):
        """Generate unique quote number"""
        from django.utils import timezone
        from django.db.models import Max
        import re
        
        year = timezone.now().year
        
        # Find the highest quote number for this user and year
        last_quote = Quote.objects.filter(
            user=self.user,
            quote_number__startswith=f"QT-{year}-"
        ).aggregate(Max('quote_number'))
        
        last_number = last_quote['quote_number__max']
        
        if last_number:
            # Extract the number from QT-2025-0001 format
            match = re.search(r'-(\d+)$', last_number)
            if match:
                next_num = int(match.group(1)) + 1
            else:
                next_num = 1
        else:
            next_num = 1
        
        return f"QT-{year}-{next_num:04d}"
    '''
    @transaction.atomic
    def generate_quote_number(self):
        year = timezone.now().year

        counter_obj, created = QuoteCounter.objects.select_for_update().get_or_create(
            user=self.user,
            year=year
        )

        counter_obj.counter += 1
        counter_obj.save()

        return f"QT-{year}-{counter_obj.counter:02d}"
    
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
    # tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)

    #Removing the tax based calculation
    '''  
    def save(self, *args, **kwargs):
        pre_tax = self.service_duration * self.rate
        tax_amount = pre_tax * (self.tax_rate / 100)
        self.amount = pre_tax + tax_amount
        super().save(*args, **kwargs)
        if hasattr(self, 'quote'):
            self.quote.calculate_totals()
            self.quote.save()
    
    '''
    def save(self, *args, **kwargs):
        # New calculation: quantity * unit_price = amount
        # self.amount = self.quantity * self.unit_price
        # REMOVE the automatic amount calculation
        # The amount field will be calculated in the quote's calculate_totals method
        super().save(*args, **kwargs)
        # if hasattr(self, 'quote'):
        #     self.quote.calculate_totals()
        #     self.quote.save()

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
    # quote = models.ForeignKey(Quote, on_delete=models.SET_NULL, null=True, blank=True)
    # user = models.ForeignKey(User, on_delete=models.CASCADE)
    #-------------------------------------------------------------
    
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

    # signature = models.ImageField(  # Added signature for invoice
    #     _('signature'),
    #     upload_to='signatures/',
    # )  
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

#-------------------------------------------------------------------------------------------
    bank_name = models.CharField(max_length=255, blank=True, null=True)
    account_name = models.CharField(max_length=255, blank=True, null=True)
    sort_code = models.CharField(max_length=20, blank=True, null=True)
    account_no = models.CharField(max_length=50, blank=True, null=True)
#------------------------------------------------------------------------------------------
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    '''
    The Client model is connected to the Quote model via a ForeignKey (client in Quote), 
    and the Invoice model is connected to the Quote model via a ForeignKey (quote in Invoice). This creates an indirect relationship where Invoice can access Client fields through 
    the Quote instance (e.g., self.quote.client.name). 
    You don't need a direct ForeignKey from Invoice to Client, and using properties 
    like 
        @property 
        def client_name(self): 
            return self.quote.client.name 
    if self.quote else None is the right approach to fetch those fields dynamically.
    
    '''
    '''   
    
    @property
    def client_name(self):
        return self.quote.client.name if self.quote else None

    @property
    def client_email(self):
        return self.quote.client.email if self.quote else None

    @property
    def client_phone(self):
        return self.quote.client.phone_number if self.quote else None

    @property
    def client_address(self):
        return self.quote.client.address if self.quote else None
    '''
    

    '''
    #moved to the ServiceDocumentBase class
    @property
    def client_details(self):
        """Single property for all client info, reducing redundancy"""
        return {'name': self.quote.client.name, 'email': self.quote.client.email, 'phone': self.quote.client.phone_number, 'address': self.quote.client.address} if self.quote else {}
    '''

    
    # @property
    # def service_type(self):  # Renamed to service_type for consistency (as you suggested)
    #     return self.quote.service_type if self.quote else None

    
    '''
    @property
    def service_description(self):
        # Safely get the first QuoteItem if it exists
        first_item = getattr(self.quote, 'items', None)
        if first_item:
            first_item = first_item.first()
        # Return the quote_description if first_item exists, else None
        return getattr(first_item, 'quote_description', None)
    
    '''

    '''
    #❌❌❌Error : NoneType' object has no attribute 'service_location
    # Why it happens
    #     Invoice was created without a quote
    #     But PDF template/logic assumes a quote always exists

    @property
    def effective_service_location(self):
        """Returns service location or client address if not specified"""
        return self.quote.service_location or self.client.address
    '''
    @property
    def effective_service_location(self):
        """Return service location from quote if exists, else client address, else N/A"""
        if self.quote and getattr(self.quote, 'service_location', None):
            return self.quote.service_location
        elif hasattr(self, 'client') and getattr(self.client, 'address', None):
            return self.client.address
        return 'N/A'
    '''
    #it is also correct, just without quantize(Decimal('0.01')

    def calculate_amounts(self):
        """Calculate totals based on InvoiceItem amounts with service charge + material cost"""
        items = self.items.all()
        
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
            else:  # fixed
                discount_value = self.discount_amount
        
        # Calculate VAT and total
        # vat_amount = self.subtotal * (self.vat_rate / Decimal('100.00'))
        # self.total = max(self.subtotal + vat_amount - discount_value, Decimal('0.00'))
        subtotal_after_discount = self.subtotal - discount_value
        vat_amount = subtotal_after_discount * (self.vat_rate / Decimal('100.00'))
        self.total = max(subtotal_after_discount + vat_amount, Decimal('0.00'))
    
    '''

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
    '''
    def save(self, *args, **kwargs):
        """Override save to calculate amounts and update status"""
        self.calculate_amounts()
        
        
        if self.is_paid and self.status != 'paid':
            self.status = 'paid'
            if not self.paid_date:
                from django.utils import timezone
                self.paid_date = timezone.now().date()
        elif not self.is_paid and self.status == 'paid':
            self.status = 'sent'
            self.paid_date = None
            
        super().save(*args, **kwargs)
    '''

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
    '''
    def generate_invoice_number(self):
        """Generate unique invoice number"""
        from django.utils import timezone
        year = timezone.now().year
        count = Invoice.objects.filter(user=self.user, created_at__year=year).count() + 1

        return f"INV-{year}-{count:04d}"
    '''


    
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

    '''
    Why NOT use property  for quote_descripton :

    -Multiple items problem: Invoice has many items, property can only return ONE description
    -No quote dependency: What if invoice created manually (no quote)? Property returns None
    -Data loss risk: If quote deleted, you lose all descriptions
    -Performance: Extra database query every time you access it
    -Can't filter/search: Can't do InvoiceItem.objects.filter(quote_description__icontains="Radio")
    '''

    quantity = models.IntegerField(validators=[MinValueValidator(1)],default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], default=0.00)
    # amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    
    service_duration = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)],default=1)
    service_type = models.CharField(_('service name'), max_length=255, default='General Service')
    service_rate = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)],default=0)
    duration_unit = models.CharField(max_length=10, choices=QuoteItem.DURATION_UNIT_CHOICES, default='hours')


    '''
    def save(self, *args, **kwargs):
        # REMOVE the automatic amount calculation
        # The amount field will be calculated in the invoice's calculate_amounts method
        super().save(*args, **kwargs)
        if hasattr(self, 'invoice'):
            self.invoice.calculate_amounts()
            self.invoice.save()
    '''
    def save(self, *args, **kwargs):
        # freeze_totals = kwargs.pop('freeze_totals', False)
        super().save(*args, **kwargs)
        # if not freeze_totals and hasattr(self, 'invoice'):
        #     self.invoice.calculate_amounts()
        #     self.invoice.save()

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


