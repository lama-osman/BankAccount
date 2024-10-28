"""
Views for the user API
"""
from drf_spectacular.utils import extend_schema
from rest_framework import generics, authentication, permissions, status
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.settings import api_settings
from rest_framework.exceptions import ValidationError
from bank_accounts.views import BankAccountViewSet
from core.models import BankAccount, Loan
from user.serializers import UserSerializer, AuthTokenSerializer
from rest_framework.response import Response
from django.core.mail import send_mail
from bank_api import settings

@extend_schema(tags=['User'])
class CreateUserView(generics.CreateAPIView):
    """ Endpoint for creating a new user in our system"""
    serializer_class = UserSerializer

    def create(self, request, *args, **kwargs):
        """Override the create method to send a welcome email after user creation."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.save()
        # Send the welcome email
        self.send_welcome_email(user.email)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def send_welcome_email(self, email):
        """Send a welcome email to the new user."""
        subject = 'Welcome to Our Service'
        message = 'Thank you for signing up! We are excited to have you on board.'
        from_email = settings.DEFAULT_FROM_EMAIL

        try:
            send_mail(subject, message, from_email, [email])
        except Exception as e:
            print(f"Failed to send email: {e}")


@extend_schema(tags=['User'])
class CreateTokenView(ObtainAuthToken):
    """Create a new token for the user"""
    serializer_class = AuthTokenSerializer
    renderer_classes = api_settings.DEFAULT_RENDERER_CLASSES

@extend_schema(tags=['User'])
class ManageUserView(generics.RetrieveUpdateAPIView):
    """Manage the authenticated user"""
    serializer_class = UserSerializer
    authentication_classes = (authentication.TokenAuthentication,)
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self):
        """Retrieve and return the authenticated user"""
        return self.request.user

    def delete(self, request, *args, **kwargs):
        """Delete the authenticated user and associated bank accounts, bypassing loan and balance checks."""
        user = self.get_object()
        bank_accounts = BankAccount.objects.filter(user=user)

        # Delete all bank accounts and associated transactions
        for account in bank_accounts:
            account.transactions.all().delete()
            account.delete()

        # Delete the user
        user.delete()
        return Response({"detail": "User account and associated bank accounts deleted successfully."},
                        status=status.HTTP_204_NO_CONTENT)

