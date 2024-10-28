# bank_accounts/serializers.py

from rest_framework import serializers
from core.models import BankAccount, Transaction, Loan
from django.contrib.auth import get_user_model

class BankAccountSerializer(serializers.ModelSerializer):

    class Meta:
        model = BankAccount
        fields = [
            'account_number',   # This field will be writable
             # These fields will be read-only
            'user',
            'date_opened',
            'balance',
            'status',
            'account_type',
            'currency',
            'overdraft_limit',
        ]
        read_only_fields = [
             'user', 'date_opened', 'balance', 'status', 'account_type', 'currency', 'overdraft_limit'
        ]

    def create(self, validated_data):

        return super().create(validated_data)


class TransactionSerializer(serializers.ModelSerializer):
    account = serializers.PrimaryKeyRelatedField(read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    account_number = serializers.CharField(source='account.account_number', read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Transaction
        fields = ['account', 'user', 'account_number', 'user_name', 'amount', 'transaction_type', 'timestamp']


    def create(self, validated_data):
       return super().create(validated_data)

