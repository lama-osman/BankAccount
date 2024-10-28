from datetime import timedelta  # Change this line
from django.utils import timezone
import requests
from rest_framework import viewsets, status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.decorators import action
from decimal import Decimal
from bank_accounts.serializers import TransactionSerializer
from core.models import BankAccount, Transaction, Loan
from loan.serializers import LoanSerializer
from drf_spectacular.utils import extend_schema_view, extend_schema


@extend_schema(tags=['Loan'])
class LoanViewSet(viewsets.GenericViewSet):
    """A ViewSet to manage loan requests and retrievals."""
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    queryset = BankAccount.objects.all()

    @extend_schema(
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'amount': {
                        'type': 'number',
                        'description': 'The amount of the loan requested',
                        'example': 10000
                    },
                    'repayment_period': {
                        'type': 'integer',
                        'description': 'The repayment period in months (maximum 72)',
                        'example': 12
                    },
                },
                'required': ['amount', 'repayment_period'],
            }
        },
        responses={
            201: {
                'application/json': {
                    'type': 'object',
                    'properties': {
                        'loan_id': {
                            'type': 'integer',
                            'description': 'The ID of the created loan',
                            'example': 1
                        },
                        'monthly_payment': {
                            'type': 'number',
                            'description': 'The monthly payment amount for the loan',
                            'example': 250.00
                        },
                        'start_date': {
                            'type': 'string',
                            'format': 'date-time',
                            'description': 'The start date of the loan repayment',
                            'example': '2024-01-01T00:00:00Z'
                        },
                        'end_date': {
                            'type': 'string',
                            'format': 'date-time',
                            'description': 'The end date of the loan repayment',
                            'example': '2026-01-01T00:00:00Z'
                        },
                    },
                }
            },
        },
        description="Request a loan with amount and repayment period"
    )
    @action(detail=True, methods=['post'], url_path='request-loan')
    def request_loan(self, request, pk=None):
        # Assuming 'pk' is the ID of the customer account
        customer_account = self.get_object()

        try:
            # Try to get the bank owner account
            bank_owner = BankAccount.objects.get(is_admin=True)
        except BankAccount.DoesNotExist:
            return Response({"detail": "Bank owner account does not exist."}, status=status.HTTP_404_NOT_FOUND)

        amount = Decimal(request.data.get('amount'))
        repayment_period = int(request.data.get('repayment_period', 72))

        if repayment_period > 72:
            return Response({"detail": "Max repayment period is 72 months."}, status=400)
        if bank_owner.balance < amount:
            return Response({"detail": "Insufficient funds in bank owner account."}, status=400)

        monthly_payment = amount / repayment_period
        end_date = timezone.now() + timedelta(days=30 * repayment_period)

        # Deduct the loan amount from the bank owner account
        bank_owner.balance -= amount
        bank_owner.save()

        # Update the customer's balance to reflect the loan amount given
        customer_account.balance += amount
        customer_account.save()  # Ensure to save the updated balance

        loan = Loan.objects.create(
            customer=customer_account,
            amount=amount,
            repayment_period=repayment_period,
            monthly_payment=monthly_payment,
            end_date=end_date,
        )

        return Response({
            "loan_id": loan.id,
            "monthly_payment": monthly_payment,
            "start_date": loan.start_date,
            "end_date": loan.end_date
        }, status=201)

    @extend_schema(
        responses={
            200: {
                'application/json': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'loan_id': {
                                'type': 'integer',
                                'description': 'The ID of the loan',
                                'example': 1
                            },
                            'amount': {
                                'type': 'number',
                                'description': 'The total amount of the loan',
                                'example': 10000
                            },
                            'repayment_period': {
                                'type': 'integer',
                                'description': 'The repayment period in months',
                                'example': 12
                            },
                            'monthly_payment': {
                                'type': 'number',
                                'description': 'The amount to be paid monthly',
                                'example': 250.00
                            },
                            'start_date': {
                                'type': 'string',
                                'format': 'date-time',
                                'description': 'The date when the loan repayment starts',
                                'example': '2024-01-01T00:00:00Z'
                            },
                            'end_date': {
                                'type': 'string',
                                'format': 'date-time',
                                'description': 'The date when the loan repayment ends',
                                'example': '2026-01-01T00:00:00Z'
                            },
                            'payment_dates': {
                                'type': 'array',
                                'items': {
                                    'type': 'string',
                                    'format': 'date-time',
                                    'description': 'The scheduled dates for loan payments',
                                    'example': '2024-02-01T00:00:00Z'
                                }
                            }
                        },
                    },
                }
            },
        },
        description="Retrieve loan information for a specific customer"
    )
    @action(detail=True, methods=['get'], url_path='get-customer-loan')
    def get_customer_loan(self, request, pk=None):
        customer_account = self.get_object()
        loans = Loan.objects.filter(customer=customer_account)
        loan_data = [{
            "loan_id": loan.id,
            "amount": loan.amount,
            "repayment_period": loan.repayment_period,
            "monthly_payment": loan.monthly_payment,
            "start_date": loan.start_date,
            "end_date": loan.end_date,
            "payment_dates": [(loan.start_date + timedelta(days=30 * i)).isoformat() for i in
                              range(loan.repayment_period)]
        } for loan in loans]

        return Response(loan_data, status=200)

class BankAdminViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'], url_path='loan-requests')
    def view_loan_requests(self, request):
        # Retrieve all pending loan requests
        pending_loans = Loan.objects.filter(status='pending')
        serializer = LoanSerializer(pending_loans, many=True)
        return Response(serializer.data, status=200)

    @action(detail=True, methods=['post'], url_path='approve-loan')
    def approve_loan(self, request, pk=None):
        loan = self.get_object()
        if loan.status == 'approved':
            return Response({"detail": "Loan is already approved."}, status=400)

        loan.status = 'approved'
        loan.save()
        # Any additional logic for loan approval
        return Response({"detail": "Loan approved successfully."}, status=200)