# clientapp/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ClientViewSet,
    ClientServiceViewSet,
)

router = DefaultRouter()
router.register(r'clients', ClientViewSet, basename='client')
router.register(r'clientservice', ClientServiceViewSet, basename='clientservice')

urlpatterns = [
    # ViewSet routes (list, retrieve, create, update, delete, summary, bulk_check, etc.)
    path('', include(router.urls)),
]
