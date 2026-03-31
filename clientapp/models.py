from django.db import models
from django.utils.translation import gettext_lazy as _
from django.db.models import Sum
from authapp.models import User
# REMOVE THIS LINE:❌reason circular import
# from quoteapp.models import Quote
import os  # Added for creating filesystem folders
from django.conf import settings  # Added for MEDIA_ROOT


# A client can take multiple service in a single day
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

    #unique true will make the email unique in db
    # email = models.EmailField(_('email'), blank=True, null=True,unique=True)#Remove unique=True from email (rely on serializer for per-user uniqueness; prevents cross-user conflicts).

    email = models.EmailField(_('email'), blank=True, null=True)
    phone_number = models.CharField(_('phone number'), max_length=20)
    image = models.ImageField(
        _('image'),
        upload_to='client_images/',
        
        blank=True,
        null=True
    )

    address = models.TextField(_('address'), blank=True, null=True)
    # success = models.BooleanField(default=False)
    # first_service_date = models.DateField(_('first service date'))  # When client first got service
    # notes = models.TextF
    # ield(_('notes'), blank=True, null=True)
    # last_contacted = models.DateTimeField(_('last contacted'), null=True, blank=True)
    
    #=============================================================================================
    #newly added
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)


    #will add it at the work with hubspot
    # hubspot_contact_id = models.CharField(max_length=50, null=True, blank=True)  # Store HubSpot contact ID
    #=============================================================================================

    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    '''
    #Removing them because -
    #❌The annotations(.annotate() in views.py) in get_queryset() already provide these values more efficiently.

    @property
    def total_services(self):
        """Returns total number of services provided to this client"""
        return self.services.count()#here used the related name "services" from ClientService

    @property
    def total_earnings(self):
        """Returns total earnings from this client across all services"""
        return self.services.aggregate(total=Sum('amount'))['total'] or 0 #here used the related name "services" from ClientService
    
    @property
    def latest_service_date(self):
        """Returns the date of the most recent service"""
        latest_service = self.services.first()  # Already ordered by -quote_accepted_date #here used the related name "services" from ClientService
        return latest_service.quote_accepted_date if latest_service else None    
    '''

    
    #============================================================================
    '''
    #added:18th aug
    def save(self, *args, **kwargs):
        is_new = self.pk is None  # Check if this is a new client
        super().save(*args, **kwargs)
        if is_new:
            # Automatically create a filesystem folder for the client
            folder_path = os.path.join(settings.MEDIA_ROOT, 'client_folders', self.name)
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
            # Also create a DB Folder for organizing quotes
            from quoteapp.models import Folder  # Import here to avoid circular import
            Folder.objects.get_or_create(user=self.user, folder_name=self.name)
    '''

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

            '''
            # Optional DB folder for app organization
            try:
                from quoteapp.models import Folder
                Folder.objects.get_or_create(
                    user=self.user,
                    folder_name=self.name
                )
            except Exception as e:
                print(f"⚠️ DB Folder creation skipped: {e}")
            '''

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
        # indexes = [
        #     models.Index(fields=['user', 'name']),  # For user's client list
        #     # models.Index(fields=['user', 'first_service_date']),  # For date-based queries
        #     models.Index(fields=['email']),  # For email lookups
        #     models.Index(fields=['phone_number']),  # For phone lookups
        # ]
    
    def __str__(self):
        return self.name

'''
Fetch service_taken_date from Quote?
No, you shouldn't - because:

service_taken_date is when the service was actually performed

Quote's dates (created_at, sent_at) are when the proposal was made

These represent different business events (proposal vs service delivery)


Quote contains proposed service details
ClientService records actual execution of that service
'''


'''
do u think the class ClientService(models.Model): is redundant?
No ❌, your ClientService model is not redundant — it’s acting as a bridge/junction between:

-Client
-Quote
-Invoice

and it gives you a single place to:

Track service-level info (notes, status, amount_earned, quote_sent_date, etc.)

Query client’s service history in one table (client.services.all())

Build dashboards like “total earnings per client” or “latest service date” efficiently.

👉 If you remove it, you’d have to always join Quote + Invoice manually to get the same insights.

So:

If your app needs a service history table → ✅ keep it.

If you only ever query Quote and Invoice directly → then yes, it’s technically redundant.

'''

class ClientService(models.Model):
    """Represents individual services provided to a client"""

    #p: The Client model has a one-to-many relationship with ClientService (one client can have multiple services), as indicated by the related_name='services' in the ClientService model.

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='services'
    )
    #this below line causing circular import error
    # quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name='client_services') 

    # TO THIS (using string reference):
    quote = models.ForeignKey('quoteapp.Quote', 
        on_delete=models.CASCADE, 
        related_name='client_services'
    )

    # invoice = models.ForeignKey('quoteapp.Invoice', 
    #     on_delete=models.CASCADE, 
    #     related_name='client_payments'
    # )

    
    # total_services = models.IntegerField(default=0)
    '''
    #Is it possible to count total_services without creating the total_services field?
    Ans:
    Yes,You can calculate it dynamically by counting related service records:
    # For a given client instance
        client = Client.objects.get(id=1)
        total_services = client.services.count()
    '''
    # total_earnings = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    '''
    client = Client.objects.get(id=1)
    total_earnings = client.services.aggregate(total=Sum('amount'))['total'] or 0

    '''

    notes = models.TextField(_('notes'), blank=True, null=True)

    @property
    def quote_sent_date(self):
        return self.quote.sent_at if self.quote_id else None
    '''
    #
    @property
    def amount_earned(self):
        # Assuming each quote has only one invoice
        invoice = getattr(self.quote, 'invoice', None)#❌wrong related name
        return invoice.total if invoice else None
    
    #but if I use like invoice = getattr(self.quote, 'invoices', None), then it's also an error because:
    This will return the reverse manager object, not the invoice itself.
    That means invoice here is not an Invoice instance — it’s a RelatedManager (like a QuerySet handler).

    invoice = getattr(self.quote, 'invoices', None)
    print(invoice)
    # <django.db.models.fields.related_descriptors.create_reverse_many_to_one_manager.<locals>.RelatedManager object ...>

    '''

    
    @property
    def amount_earned(self):
        if not self.quote_id:
            return None
        invoice = self.quote.invoices.first()  # ✅ correct reverse relation
        return invoice.total if invoice else None
    
    '''
    Here,related names
        services → ClientService,

        quote → Quote,

        invoices → Invoice

        total → actual db numeric field on invoice

    '''

    @property
    def service_type(self):
        # Fix: Use first QuoteItem's description (or add 'description' to Quote model)
        first_item = self.quote.items.first() if self.quote else None
        return first_item.service_type if first_item else None
    '''
    @property
    def service_type(self):
         return self.quote.service_type if self.quote_id else None  # Access service_type from the related Quote model through the relationship
    '''

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
        # indexes = [
        #     models.Index(fields=['client_id']),  # For client's service list
        #     '''
        #     # models.Index(fields=['service_type']),  # ❌Will get error:"django.core.exceptions.FieldDoesNotExist: ClientService has no field named 'service_type'. The app cache isn't ready yet, so if this is an auto-created related field, it won't be available yet.   "
        #     # models.Index(fields=['service_status']),  #❌ For filtering by status,but will get error like "django.core.exceptions.FieldDoesNotExist: ClientService has no field named 'service_status'. The app cache isn't ready yet, so if this is an auto-created related field, it won't be available yet.     "

        #     #models.Index(fields=['quote_sent_date']),  ❌ quote_sent_date is a property, not a database field. This will cause errors. 

        #     #models.Index(fields=['client', 'quote_sent_date']),

        #     '''

        # ]

    def __str__(self):
     return f"{self.client.name} - {getattr(self.quote.items.first(), 'quote_description', 'NO description provided')}"
    
    #✅✅✅Easy version of it which is also correct:

    '''
    def __str__(self):
        first_item = self.quote.items.first() if self.quote else None #items is the related name
        description = first_item.quote_description if first_item else 'NO description provided'
        return f"{self.client.name} - {description}"
    '''

    
    # ❌Error str
    '''
   # If I do so:
    def __str__(self):
        return f"{self.client.name} - {self.quote.quote_description if self.quote else 'NO description provided'}"

     ❌Error : Failed to create client: Quote has no field named 'quote_description'",

    Why the error happens:

        The Quote model itself does NOT have a field quote_description.
        quote_description exists on QuoteItem, which is a related model (quote.items).
        So trying to access self.quote.quote_description is invalid; Django raises:
    '''



'''
1. Is it good to merge the Client and ClientService models into one class(model)?

When I can merge:

(i)If each client is associated with only one service,combining the models reduces complexity by eliminating the need for a separate table and foreign key management.

(ii)Retrieving client and service data would require fewer database queries, as all information would be in one table.

When I can't merge:

(i)a single client to have multiple services (e.g., a client could have taken plumbing on one date and electrical work on another).

(ii)If a client has multiple services, fields like name, email, phone_number, and address would be duplicated for each service record in a merged model, violating database normalization principles and increasing storage requirements.

(iii)If you later need to track additional service-specific details (e.g., multiple service dates, different service providers, or service-specific notes), a single table would become unwieldy.
'''



'''
Removing service_type from Client:

No Default Service Type for the Client: If you remove the service_type from the Client model and put service_name in ClientService, you can allow the user to freely input the name of the service when adding it. This could be useful in cases where services aren't just standard types (like "plumbing" or "electrical") but may change based on the specific job.

But the problem is 
Since the user will have to manually input the service name, they may enter inconsistent or misspelled service names, leading to data integrity issues.



'''



'''
If I use service_type in both Client and ClientService is redundant. 
If a client can have multiple services (as your design allows with ClientService), the service_type in Client doesn’t make sense—use it only in ClientService to categorize each service.
'''


## Removed:18th september ContactImport model as it's not necessary; Flutter handles contact import, backend just creates clients via API if not existing.

'''
class ContactImport(models.Model):#Talk with app developer
    class ImportSource(models.TextChoices):
        PHONE_CONTACTS = 'phone_contacts', _('Phone Contacts')
        MANUAL = 'manual', _('Manual Entry')
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='contact_imports'
    )
    source = models.CharField(
        max_length=20,
        choices=ImportSource.choices
    )
    imported_count = models.PositiveIntegerField(default=0)
    successful_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    error_log = models.TextField(blank=True, null=True)
    import_date = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'contact_imports'
        verbose_name = _('contact import')
        verbose_name_plural = _('contact imports')
        ordering = ['-import_date']
    
    def __str__(self):
        return f"{self.user.email} - {self.source}"
'''








