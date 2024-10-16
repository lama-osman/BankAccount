"""
Serializers for the User API
"""


from django.contrib.auth import get_user_model, authenticate

from rest_framework import serializers


class UserSerializer(serializers.ModelSerializer):
    """Serializer for the user model"""

    class Meta:
        model = get_user_model()
        fields = ('userId','email', 'password', 'name')
        extra_kwargs = {
            'password': {
                'write_only': True,
                'min_length': 5
            }
        }

    def create(self, validated_data):
        """ Creates and returns a new user with encrypted password"""
        return get_user_model().objects.create_user(**validated_data)


    def update(self, instance, validated_data):
        """Updates a user"""

        password = validated_data.pop('password', None)
        user = super().update(instance, validated_data)

        if password:
            user.set_password(password)
            user.save()

        return user

class AuthTokenSerializer(serializers.Serializer):

    userId = serializers.CharField()
    password = serializers.CharField(
        style= {'input_type': 'password'},
        trim_whitespace=False
    )

    def validate(self, attrs):
        """Validate and authenticate the credentials and the user"""

        userId = attrs.get('userId')
        password = attrs.get('password')

        user = authenticate(
            username=userId,
            password=password
        )

        if not user:
            msg = 'Unable to Authenticate User with Provided Credentials'
            raise serializers.ValidationError(msg, code='authorization')

        attrs['user'] = user
        return attrs

