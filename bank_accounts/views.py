from drf_spectacular.types import OpenApiTypes
from rest_framework import viewsets, status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from decimal import Decimal
from core.models import BankAccount, Transaction, Loan
from bank_accounts import serializers
from drf_spectacular.utils import extend_schema
import requests
from rest_framework.exceptions import ValidationError


def get_conversion_rate(base_currency, target_currency):
    """Fetches the conversion rate between base_currency and target_currency."""
    api_url = "https://api.freecurrencyapi.com/v1/latest"
    api_key = "fca_live_owToHH5dpVpyTdG25Hws3z65pDtC3cdPGnA6F2J9"

    try:
        response = requests.get(f"{api_url}?apikey={api_key}&base_currency={base_currency}")
        response.raise_for_status()
        data = response.json()

        # Return the rate for the target currency
        conversion_rate = data.get('data', {}).get(target_currency)
        if not conversion_rate:
            raise ValueError(f"Conversion rate for {target_currency} not found.")
        return conversion_rate

    except requests.RequestException as e:
        raise ValueError(f"Error fetching conversion rate: {e}")


@extend_schema(tags=['Bank Account'])
class BankAccountViewSet(viewsets.ModelViewSet):
    """A ViewSet for managing Bank Accounts."""

    serializer_class = serializers.BankAccountSerializer
    queryset = BankAccount.objects.all()

    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        """Retrieve bank accounts for the authenticated user."""
        return self.queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        """Create a new bank account and associate with the authenticated user."""
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        """Delete a specific bank account, handling balance requirements and related dependencies."""
        account = self.get_object()

        # Step 1: Check if the balance is less than 0
        if account.balance < 0:
            amount_to_deposit = abs(account.balance)
            return Response(
                {
                    "detail": f"Account balance is negative. Please deposit {amount_to_deposit} to bring the balance to zero."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Step 2: Check if the balance is greater than 0
        elif account.balance > 0:
            amount_to_withdraw = account.balance
            return Response(
                {
                    "detail": f"Account balance is positive. Please withdraw {amount_to_withdraw} to bring the balance to zero before deletion."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Step 3: Check for any active loans
        active_loans = Loan.objects.filter(customer=account, status='active')
        if active_loans.exists():
            return Response({
                "detail": "Account has active loans. Please repay all loans before account deletion."
            }, status=status.HTTP_400_BAD_REQUEST)

        # Step 4: Delete all associated transactions as balance is now 0
        account.transactions.all().delete()

        # Step 5: Delete the bank account
        account.delete()
        return Response({"detail": "Bank account deleted successfully."}, status=status.HTTP_204_NO_CONTENT)


    @action(detail=True, methods=['PATCH'], url_path='suspend')
    def suspend_account(self, request, pk=None):
        """Suspend a bank account."""
        account = self.get_object()

        if account.status == 'suspended':
            return Response({"detail": "Account is already suspended."}, status=status.HTTP_400_BAD_REQUEST)

        account.status = 'suspended'
        account.save()

        return Response({"detail": "Account suspended successfully."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['GET'], url_path='transactions')
    def get_transactions(self, request, pk=None):
        """Retrieve all transactions for a specific bank account."""
        account = self.get_object()
        transactions = account.transactions.all()  # Get transactions related to the account
        serializer = serializers.TransactionSerializer(transactions, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(tags=['Transactions'])
class TransactionViewSet(viewsets.GenericViewSet):
    """A ViewSet to handle transactions like deposit, withdraw, and transfer."""

    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    queryset = BankAccount.objects.all()

    def convert_amount(self, amount, from_currency, to_currency):
        """Converts the amount from one currency to another."""
        conversion_rate = get_conversion_rate(from_currency, to_currency)
        return amount * Decimal(conversion_rate)

    @extend_schema(
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'amount': {'type': 'number'},  # Use JSON-compatible type
                    'currency': {
                        'type': 'string',
                        'description': 'Currency code (e.g., USD, EUR, JPY). Default is USD',
                    },
                },
                'required': ['amount'],  # 'currency' is optional
            }
        },
        responses={
            200: {'type': 'object', 'properties': {'detail': {'type': 'string'}, 'new_balance': {'type': 'number'}}}},
    )
    @action(detail=True, methods=['patch'], url_path='deposit')
    def deposit(self, request, pk=None):
        account = self.get_object()

        # Safeguard against request data not being as expected
        if not isinstance(request.data, dict):
            return Response({"detail": "Invalid request format."}, status=400)

        # Safely get amount and handle potential conversion issues
        try:
            amount = Decimal(request.data.get('amount', 0))
            currency = request.data.get('currency', 'USD')  # Default to USD if not provided

        except (ValueError, TypeError):
            return Response({"detail": "Invalid amount format."}, status=400)

        if amount <= 0:
            return Response({"detail": "Invalid deposit amount."}, status=400)

        if account.status != 'active':
            return Response({"detail": "Account is not active."}, status=400)

        if account.currency != currency:
            amount = self.convert_amount(amount, currency, account.currency)

        # Update the account balance
        account.balance += amount
        account.save()

        # Create a transaction record with the correct account reference
        Transaction.objects.create(
            account=account,  # Ensure you're passing the correct account instance
            user=request.user,
            amount=amount,
            transaction_type='deposit'
        )

        return Response({"detail": "Deposit successful", "new_balance": str(account.balance)}, status=200)

    @extend_schema(
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'amount': {'type': 'number'},  # Use JSON-compatible type
                    'currency': {
                        'type': 'string',
                        'description': 'Currency code (e.g., USD, EUR, JPY). Default is USD',
                    },
                },
                'required': ['amount'],  # 'currency' is optional
            }
        },
        responses={
            200: {'type': 'object', 'properties': {'detail': {'type': 'string'}, 'new_balance': {'type': 'number'}}}},
    )
    @action(detail=True, methods=['patch'], url_path='withdraw')
    def withdraw(self, request, pk=None):
        account = self.get_object()

        # Safeguard against request data not being as expected
        if not isinstance(request.data, dict):
            return Response({"detail": "Invalid request format."}, status=400)

        # Safely get amount and handle potential conversion issues
        try:
            amount = Decimal(request.data.get('amount', 0))
            currency = request.data.get('currency', 'USD')  # Default to USD if not provided

        except (ValueError, TypeError):
            return Response({"detail": "Invalid amount format."}, status=400)
            # Perform currency conversion if account currency differs from withdrawal currency

        if account.currency != currency:
             amount = self.convert_amount(amount, currency, account.currency)

        fee = Decimal('5.00')  # Assuming a fixed transaction fee

        # Check if the account is active and if there are sufficient funds
        if account.status != 'active':
            return Response({"detail": "Account is not active."}, status=400)

        if account.balance < (amount + fee):
            return Response({"detail": "Insufficient balance."}, status=400)

        # Update the account balance
        account.balance -= (amount + fee)
        account.save()

        # Create a transaction record for the withdrawal
        Transaction.objects.create(
            account=account,
            user=request.user,
            amount=amount,
            transaction_type='withdrawal'
        )

        return Response({"detail": "Withdrawal successful", "new_balance": str(account.balance)}, status=200)

    @extend_schema(
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'target_account_number': {
                        'type': 'string',
                        'description': 'The account number of the target bank account',
                    },
                    'amount': {'type': 'number'},  # Use JSON-compatible type
                    'currency': {
                        'type': 'string',
                        'description': 'Currency code (e.g., USD, EUR, JPY). Default is USD',
                    },
                },
                'required': ['target_account_number', 'amount'],  # 'currency' is optional
            }
        },
        responses={200: {'type': 'object', 'properties': {'detail': {'type': 'string'}}}},
    )
    @action(detail=True, methods=['patch'], url_path='transfer')
    def transfer(self, request, pk=None):
        source_account = self.get_object()

        # Safeguard against request data not being as expected
        if not isinstance(request.data, dict):
            return Response({"detail": "Invalid request format."}, status=400)

        # Safely get target account number and amount
        target_account_number = request.data.get('target_account_number')
        try:
            amount = Decimal(request.data.get('amount', 0))
            currency = request.data.get('currency', 'USD')  # Default to USD if not provided

        except (ValueError, TypeError):
            return Response({"detail": "Invalid amount format."}, status=400)

        if source_account.currency != currency:
            amount = self.convert_amount(amount, currency, source_account.currency)

        fee = Decimal('5.00')  # Transaction fee

        # Check if source account is active and if there are sufficient funds
        if source_account.status != 'active':
            return Response({"detail": "Source account is not active."}, status=400)

        if source_account.balance < (amount + fee):
            return Response({"detail": "Insufficient balance in source account."}, status=400)

        # Validate target account
        try:
            target_account = BankAccount.objects.get(account_number=target_account_number)
            if target_account.status != 'active':
                return Response({"detail": "Target account is inactive."}, status=400)
        except BankAccount.DoesNotExist:
            return Response({"detail": "Target account not found."}, status=404)

        # Perform the transfer
        source_account.balance -= (amount + fee)
        target_account.balance += amount
        source_account.save()
        target_account.save()

        # Record transactions for both accounts
        Transaction.objects.create(
            account=source_account,
            user=request.user,
            amount=amount,
            transaction_type='transfer-out'
        )
        Transaction.objects.create(
            account=target_account,
            user=target_account.user,
            amount=amount,
            transaction_type='transfer-in'
        )

        return Response({"detail": "Transfer successful"}, status=200)


    @action(detail=True, methods=['get'], url_path='balance')
    def get_balance(self, request, pk=None):
        """Get the balance of a specific bank account."""
        account = self.get_object()

        if account.status != 'active':
            return Response({"detail": "Account is not active."}, status=status.HTTP_400_BAD_REQUEST)

        # Return the current balance
        return Response({"balance": str(account.balance)}, status=status.HTTP_200_OK)

