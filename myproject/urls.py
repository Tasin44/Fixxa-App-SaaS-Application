"""
URL configuration for myproject project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include
from rest_framework_simplejwt.views import(
    TokenObtainPairView,
    TokenRefreshView,
)
from django.conf import settings
from django.conf.urls.static import static
from quoteapp.views import payment_success_view,payment_redirect_view # ADD THIS

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),  # JWT token endpoint
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),  # JWT refresh endpoint
    path('auth/',include('authapp.urls')),
    path('quoteapp/',include('quoteapp.urls')),
    path('businessapp/',include('businessapp.urls')),
    path('payment-success/', payment_success_view, name='payment_success'),  # ADD THIS
    path('clientapp/',include('clientapp.urls')),
    path('payment/<int:invoice_id>/', payment_redirect_view, name='payment_redirect'),
    path('notificationapp/',include('notificationapp.urls')),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)