from django.urls import path, include
from rest_framework.routers import DefaultRouter
from bank_accounts.views import BankAccountViewSet, TransactionViewSet

# Create a router and register the BankAccountViewSet and TransactionViewSet
router = DefaultRouter()
router.register(r'bank_accounts', BankAccountViewSet, basename='bankaccount')
router.register(r'transactions', TransactionViewSet, basename='transaction-ops')


urlpatterns = [
    path('api/', include(router.urls)),  # Include the router URLs
]