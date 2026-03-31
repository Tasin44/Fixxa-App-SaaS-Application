from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    FolderViewSet,
    QuoteViewSet,
    InvoiceViewSet,
    create_invoice_from_quote,
    payment_success_view,
    stripe_webhook,
    ImageScanUploadView,
    NewQuoteCreateView, NewInvoiceCreateView
    
)
# AI-powered views
from .ai_views import (
    VoiceQuoteCreateView,
    VoiceInvoiceCreateView,
    DocumentQuoteCreateView,
    DocumentInvoiceCreateView,
    AIChatQueryView,
    VoiceQuoteUploadPDFView,    # ← add this
    VoiceInvoiceUploadPDFView   # ← add this
)

router = DefaultRouter()
router.register(r'folders', FolderViewSet, basename='folder')
router.register(r'quotes', QuoteViewSet, basename='quote')
router.register(r'invoices', InvoiceViewSet, basename='invoice')

urlpatterns = [


    # path('quotes/<uuid:quote_id>/create-invoice/', create_invoice_from_quote, name='create-invoice-from-quote'),
    path('quotes/<int:quote_id>/create-invoice/', create_invoice_from_quote, name='create-invoice-from-quote'),
    path('quotes/webhook/stripe/', stripe_webhook, name='stripe-webhook'),
    path('quotes/payment-success/', payment_success_view, name='payment_success'),
    path('scan-upload/', ImageScanUploadView.as_view(), name='scan-upload'),
    # path('quotes/payment/<int:invoice_id>/', payment_redirect_view, name='payment_redirect'),

    #-----------------------------------------------------------------------------------------------
    path('quotes/new-create/', NewQuoteCreateView.as_view(), name='new-quote-create'),
    # path('invoices/new-create/', NewInvoiceCreateView.as_view(), name='new-invoice-create'),
    path('invoices/new-create/', NewInvoiceCreateView.as_view(), name='new-invoice-create'),
    #----------------------------------------------------------------------------------------------
    # ===========================================================================================
    # AI-POWERED ENDPOINTS
    # ===========================================================================================
    # Voice-based quote/invoice creation
    path('ai/voice/quote/', VoiceQuoteCreateView.as_view(), name='ai-voice-quote'),
    path('ai/voice/invoice/', VoiceInvoiceCreateView.as_view(), name='ai-voice-invoice'),
    
    # Document-based quote/invoice creation  
    path('ai/document/quote/', DocumentQuoteCreateView.as_view(), name='ai-document-quote'),
    path('ai/document/invoice/', DocumentInvoiceCreateView.as_view(), name='ai-document-invoice'),
    
    # AI chat for reports and queries
    path('ai/chat/', AIChatQueryView.as_view(), name='ai-chat'),
    path('ai/voice/quote/<int:pk>/upload-pdf/', VoiceQuoteUploadPDFView.as_view(), name='ai-voice-quote-upload-pdf'),
    path('ai/voice/invoice/<int:pk>/upload-pdf/', VoiceInvoiceUploadPDFView.as_view(), name='ai-voice-invoice-upload-pdf'),
    # ===========================================================================================
    path('', include(router.urls)),


]


