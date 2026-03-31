

from rest_framework import serializers
from .models import BusinessProfile

class BusinessProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessProfile
        fields = [
            'business_name', 'whatsapp_number', 'logo', 'business_details',
            'stripe_account_id', 'stripe_connected', 'stripe_connection_date',
            'stripe_details_submitted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'stripe_account_id', 'stripe_connected', 'stripe_connection_date']


class StripeConnectSerializer(serializers.ModelSerializer):  # Fixed: Use BusinessProfile, not User
    class Meta:
        model = BusinessProfile
        fields = ['stripe_account_id', 'stripe_connected', 'stripe_connection_date']
        read_only_fields = fields  # All read-only post-onboard


class BusinessProfileCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessProfile
        fields = ['business_name', 'whatsapp_number', 'logo']
    
    def validate_business_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Business name is required.")
        return value.strip()
    
    def validate_whatsapp_number(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("WhatsApp number is required.")
        return value.strip()
















































