from django.db import models
from authapp.models import User
# Create your models here.
from django.utils.translation import gettext_lazy as _

class BusinessProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='business_profile',
        primary_key=True
    )
    business_name = models.CharField(_('business name'), max_length=255)
    whatsapp_number = models.CharField(_('whatsapp number'), max_length=20)
    logo = models.ImageField(
        _('logo'),
        upload_to='business_logos/',
        null=True,
        blank=True
    )
    business_details = models.TextField(_('business details'), blank=True, null=True)
    # ✅ NEW - Stripe Connect
    stripe_account_id = models.CharField(max_length=255, blank=True, null=True)#Stripe connected account ID after onboarding
    stripe_connected = models.BooleanField(default=False)

    stripe_connection_date = models.DateTimeField(null=True, blank=True)
    stripe_details_submitted = models.BooleanField(default=False)  # optional
    
    # tax_id = models.CharField(_('tax ID'), max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)
    
    class Meta:
        verbose_name = _('business profile')
        verbose_name_plural = _('business profiles')
        ordering = ['business_name']
    

    def __str__(self):
        return f"{self.business_name} - {self.stripe_connected}"

'''
🔥ordering in Django’s Meta class

ordering = ['business_name']

    It tells Django: “When you get data from this model, sort it by this field by default.”

    Here, it means:
    → Every time you query BusinessProfile.objects.all(), Django will sort the results alphabetically by business_name.

Example without ordering

BusinessProfile.objects.all()
# Might give:  [Zeta Corp, Alpha Ltd, Beta Inc]

Example with ordering = ['business_name']

BusinessProfile.objects.all()
# Will give:  [Alpha Ltd, Beta Inc, Zeta Corp]

You can also reverse the order

ordering = ['-business_name']  # "-" means descending
# Result: [Zeta Corp, Beta Inc, Alpha Ltd]


'''



'''
class Subscription(models.Model):#Talk with app developer
    
    class SubscriptionPlan(models.TextChoices):#first 3 monts free, then pay monthyly or yearly (will change the AI(gpt,deep,grok) serializers, views based on this condition )
        FREE = 'free', _('Free')
        PREMIUM = 'premium', _('Premium')
    
    class SubscriptionStatus(models.TextChoices):
        ACTIVE = 'active', _('Active')
        EXPIRED = 'expired', _('Expired')
        CANCELLED = 'cancelled', _('Cancelled')
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscriptions')
    plan_name = models.CharField(max_length=255, choices=SubscriptionPlan.choices)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.ACTIVE
    )
    #------------------------------------------------------
    billing_cycle = models.CharField(
        _('billing cycle'),
        max_length=10,
        choices=[('monthly', _('Monthly')), ('annual', _('Annual'))],
        default='monthly'
    )
    payment_method = models.CharField(_('payment method'), max_length=50, blank=True, null=True)
    #-----------------------------------------------------------------
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('subscription')
        verbose_name_plural = _('subscriptions')
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['end_date']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.plan_name}"


'''
#deepseek












