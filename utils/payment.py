

import stripe
from django.conf import settings
import logging

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY

def create_stripe_payment_link(invoice):
    try:
        if not invoice.user.business_profile.stripe_connected:
            return None
        
        account_id = invoice.user.business_profile.stripe_account_id
        amount_pence = int(float(invoice.total) * 100)
        
        '''
        # Calculate fees based on payment speed
        if invoice.payment_speed == 'standard':
            stripe_fee_percent = 1.5
            platform_fee_percent = 0.25
            fixed_fee_pence = 20# it's also called 20p, which will act as .20
        else:  # faster
            stripe_fee_percent = 2.5
            platform_fee_percent = 0.25
            fixed_fee_pence = 20 #it's also called 20p, which will act as .20
        '''
        invoice.payment_speed ='standard'
        stripe_fee_percent = 1.5
        platform_fee_percent = 0.25
        fixed_fee_pence = 20# it's also called 20p, which will act as .20
        
        # Calculate Fixxa fee (0.25%)
        fixxa_fee_pence = int((amount_pence * platform_fee_percent) / 100)
        
        # Total platform fee (Stripe handles its own, we just collect Fixxa)
        total_app_fee_pence = fixxa_fee_pence + fixed_fee_pence
        
        # Use Checkout.Session, NOT PaymentLink for connected accounts
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            #automatic_payment_methods={"enabled": True}, #I added this line for goggle pay and apple pay, if I face any issue, will remove it
            line_items=[{
                'price_data': {
                    'currency': 'gbp',
                    'product_data': {'name': f"Invoice {invoice.invoice_number}"},
                    'unit_amount': amount_pence,
                },
                'quantity': 1,
            }],
            mode='payment',


            #❌❌#success_url=f"{settings.BASE_URL}/payment-success?session_id={{CHECKOUT_SESSION_ID}}&invoice_id={invoice.invoice_id}",
            
            #Root Cause: The success_url in payment.py points to:
            #But your URL pattern is:
            #path('quotes/payment-success/', payment_success_view, name='payment_success'),
            # The URL is /quoteapp/quotes/payment-success/ but Stripe redirects to /payment-success — they don't match, causing a redirect loop (301) and then 502.

            # Fix the success_url in payment.py:
            
            success_url=f"{settings.BASE_URL}/quoteapp/quotes/payment-success/?session_id={{CHECKOUT_SESSION_ID}}&invoice_id={invoice.invoice_id}",
            cancel_url=f"{settings.BASE_URL}/payment-cancelled",
            metadata={
                "invoice_id": str(invoice.invoice_id),
                "invoice_number": invoice.invoice_number,
                "payment_speed": invoice.payment_speed,
            },
            # ✅ Connect to user's account with commission
            stripe_account=account_id,
            payment_intent_data={
                "application_fee_amount": total_app_fee_pence,  # Fixxa commission
            }
        )
        
        return session.url  # Return session URL, not payment link
        
    except Exception as e:
        logger.error(f"Session creation error: {e}")
        return None


def verify_payment_link(invoice):
    """
    Check if payment link is valid in Stripe
    """
    try:
        if not invoice.payment_link:
            return False
        
        # Extract payment link ID from URL
        # Format: https://buy.stripe.com/test_XXXXX
        link_id = invoice.payment_link.split('/')[-1]
        
        # Retrieve payment link from Stripe
        payment_link = stripe.PaymentLink.retrieve(link_id)
        
        return payment_link.active
    except Exception as e:
        logger.error(f"Error verifying payment link: {e}")
        return False