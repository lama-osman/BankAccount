# serializers.py

from rest_framework import serializers
from core.models import Loan

class LoanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Loan
        fields = [
            'id',
            'customer',
            'amount',
            'repayment_period',
            'monthly_payment',
            'start_date',
            'end_date',
            'status',  # Ensure status is in Loan model to handle pending/approved status
        ]
        read_only_fields = ['id', 'monthly_payment', 'start_date', 'end_date']  # Set any read-only fields here
