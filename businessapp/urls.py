

from django.urls import path
from .views import stripe_connect_onboard, stripe_status,dashboard_view,stripe_onboard_complete,BusinessProfileCreateUpdateView

urlpatterns = [
    path('stripe/connect/', stripe_connect_onboard, name='stripe_connect'),
    path('stripe/status/', stripe_status, name='stripe_status'),
    path('stripe/onboard-complete/', stripe_onboard_complete, name='stripe_onboard_complete'),
    path('dashboard/', dashboard_view, name='dashboard'),
    # path('stripe/connect-existing/', connect_existing_stripe_account, name='connect_existing_stripe_account'),  # ✅ new
    path('profile/', BusinessProfileCreateUpdateView.as_view(), name='business_profile'),
]

















