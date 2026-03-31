import logging
from .models import Notification
from .onesignal_service import send_onesignal_notification

logger = logging.getLogger(__name__)


def notify_quote_accepted(quote):
    """
    Called when client accepts a quote.
    Notifies the business owner (quote.user).
    """
    user = quote.user
    title = "🎉 Quote Accepted!"
    body = f"Client {quote.client.name} accepted Quote #{quote.quote_number} (£{quote.total})"
    data = {
        "type": "quote_accepted",
        "quote_id": str(quote.quote_id),
        "quote_number": quote.quote_number,
        "client_name": quote.client.name,
        "total": str(quote.total),
    }

    # Save to DB
    Notification.objects.create(
        user=user,
        notification_type='quote_accepted',
        title=title,
        body=body,
        data=data
    )

    # Push via OneSignal
    send_onesignal_notification(user, title, body, data)
    logger.info(f"Quote accepted notification sent for quote {quote.quote_id}")


def notify_invoice_paid(invoice):
    """
    Called when client pays an invoice.
    Notifies the business owner (invoice.user).
    """
    user = invoice.user
    title = "💰 Payment Received!"
    body = f"£{invoice.total} received for Invoice #{invoice.invoice_number} from {invoice.client.name}"
    data = {
        "type": "invoice_paid",
        "invoice_id": str(invoice.invoice_id),
        "invoice_number": invoice.invoice_number,
        "client_name": invoice.client.name,
        "total": str(invoice.total),
    }

    # Save to DB
    Notification.objects.create(
        user=user,
        notification_type='invoice_paid',
        title=title,
        body=body,
        data=data
    )

    # Push via OneSignal
    send_onesignal_notification(user, title, body, data)
    logger.info(f"Invoice paid notification sent for invoice {invoice.invoice_id}")