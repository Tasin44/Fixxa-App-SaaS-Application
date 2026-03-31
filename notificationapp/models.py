# notification/models.py
from django.db import models
from authapp.models import User
from django.utils import timezone

class DeviceToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='device_tokens')
    token = models.CharField(max_length=255, unique=True)
    device_type = models.CharField(max_length=10, choices=[('ios', 'iOS'), ('android', 'Android')])
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'token']

class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('quote_accepted', 'Quote Accepted'),
        ('quote_rejected', 'Quote Rejected'),
        ('payment_completed', 'Payment Completed'),
        ('invoice_paid', 'Invoice Paid'),    
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=255)
    body = models.TextField()
    data = models.JSONField(default=dict)  # Extra data
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']