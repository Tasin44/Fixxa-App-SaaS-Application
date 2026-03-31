from django.urls import path
from .views import (
    SignupView, VerifyOTPView, ResendOTPView, LoginView,
    LogoutView, ForgotPasswordView, ResetPasswordView,GenerateReferralCodeView, ReferralStatsView
)

urlpatterns = [
    path('signup/', SignupView.as_view(), name='signup'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('resend-otp/', ResendOTPView.as_view(), name='resend-otp'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    path('referral/generate/', GenerateReferralCodeView.as_view(), name='generate-referral'),
    path('referral/stats/', ReferralStatsView.as_view(), name='referral-stats'),
]

