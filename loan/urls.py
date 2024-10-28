from django.urls import path, include
from rest_framework.routers import DefaultRouter
from loan.views import LoanViewSet

# Create a router and register the BankAccountViewSet and TransactionViewSet
router = DefaultRouter()

router.register(r'loans', LoanViewSet, basename='loan-ops')  # Add basename here


urlpatterns = [
    path('api/', include(router.urls)),  # Include the router URLs
]