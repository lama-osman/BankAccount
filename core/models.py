"""
Models for our system
"""
from django.contrib.auth.hashers import make_password
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db.models.signals import post_migrate
from decimal import Decimal

from django.dispatch import receiver

from bank_api import settings
from datetime import timedelta


class UserManager(BaseUserManager):
    """ Manager for the Users in the system"""
    print('UserManager class at models ..')
    def create_user(self, email, password=None, **extra_field):
        """Creates a user in the system"""
        if not email:
            raise ValueError("Must provide an email")
        email = self.normalize_email(email)

        user = self.model(email=email, **extra_field)
        user.set_password(password)
        user.save(using=self._db)
        print('the user : {0}'.format(user))

        return user

    def create_superuser(self, email, password="12345"):
        """Creates a superuser"""
        user = self.create_user(email, password)

        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)

        return user

class User(AbstractBaseUser, PermissionsMixin):
    """User in the system"""


    email = models.EmailField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = 'email'


class BankAccount(models.Model):
    ACCOUNT_TYPES = [
        ('individual', 'Individual'),
        ('shared', 'Shared'),
    ]

    CURRENCIES = [
        ('USD', 'US Dollar'),
        ('EUR', 'Euro'),
        ('JRD', 'Jordanian Dinar'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('suspended', 'Suspended'),
    ]

    account_number = models.CharField(max_length=20, unique=True)
    password = models.CharField(max_length=128)  # Ensure to hash password securely
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
       )
    date_opened = models.DateTimeField(auto_now_add=True)
    balance = models.DecimalField(max_digits=12, decimal_places=2 ,default=100)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    account_type = models.CharField(max_length=10, choices=ACCOUNT_TYPES , default='individual')
    currency = models.CharField(max_length=3, choices=CURRENCIES, default='USD')
    overdraft_limit = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_admin = models.BooleanField(default=False)

    def __str__(self):
        return (
            f"Account Number: {self.account_number}, "
            f"User: {self.user.id if self.user else 'None'}, "
            f"Date Opened: {self.date_opened}, "
            f"Balance: {self.balance}, "
            f"Status: {self.status}, "
            f"Account Type: {self.account_type}, "
            f"Currency: {self.currency}, "
            f"Overdraft Limit: {self.overdraft_limit}"
        )

    @classmethod
    def setup_admin_account(cls):
        admin_user = User.objects.create_superuser(email='admin@example.com', password='admin_password')
        # Check if an admin account already exists
        if not cls.objects.filter(is_admin=True).exists():
            cls.objects.create(
                account_number="11111",
                user=admin_user,  # Link the created user here
                password=make_password("11111"),  # Hash the password
                balance=Decimal('100000000.00'),
                status='active',
                account_type='individual',
                currency='USD',
                is_admin=True
            )
            print('created admin')


@receiver(post_migrate)
def create_admin_account(sender, **kwargs):
    if sender.name == 'core':  # Check if the sender is your core app
        print("Running post-migrate signal...")  # Debugging line
        BankAccount.setup_admin_account()


class Transaction(models.Model):
    account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, related_name='transactions')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=10, choices=[('deposit', 'Deposit'), ('withdrawal', 'Withdrawal')])
    timestamp = models.DateTimeField(auto_now_add=True)

class Loan(models.Model):
    customer = models.ForeignKey(BankAccount, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    repayment_period = models.PositiveIntegerField()  # in months
    monthly_payment = models.DecimalField(max_digits=10, decimal_places=2)
    start_date = models.DateField(auto_now_add=True)
    end_date = models.DateField()
    status = models.CharField(max_length=10, choices=[('pending', 'Pending'), ('approved', 'Approved')],
                              default='pending')

    def calculate_monthly_payment(self):
        return self.amount / self.repayment_period