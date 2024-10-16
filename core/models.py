"""
Models for our system
"""

from django.db import models

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin

from bank_api import settings



class UserManager(BaseUserManager):
    """ Manager for the Users in the system"""

    def create_user(self, userId, email, password="12345", **extra_fields):
        """Creates and saves a new user"""
        if not userId:
            raise ValueError("Must provide a userId")
        if not email:
            raise ValueError("Must provide an email address")

        email = self.normalize_email(email)
        user = self.model(userId=userId, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, userId, email, password="12345"):
        """Creates a superuser"""
        user = self.create_user(userId=userId, email=email, password=password)
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)

        return user


class User(AbstractBaseUser, PermissionsMixin):
    """User in the system"""

    email = models.EmailField(max_length=255)
    userId = models.CharField(max_length=255,unique=True,default='default_user_id')
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = 'userId'
    REQUIRED_FIELDS = ['email']

