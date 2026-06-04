from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):

    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        MANAGER = "MANAGER", "Manager"
        USER = "USER", "User"
        ANALYST = "ANALYST", "Analyst"

    class Theme(models.TextChoices):
        DARK = "dark", "Zarya Corporate Dark"
        LIGHT = "light", "Zarya Corporate Light"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.USER
    )

    theme = models.CharField(
        max_length=20,
        choices=Theme.choices,
        default=Theme.DARK
    )