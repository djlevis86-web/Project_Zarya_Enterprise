from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):

    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Администратор"
        MANAGER = "MANAGER", "Финансовый директор"
        GENERAL_DIRECTOR = "GENERAL_DIRECTOR", "Генеральный директор"
        USER = "USER", "Загрузчик документов"
        ANALYST = "ANALYST", "Полный просмотр"

    class Theme(models.TextChoices):
        DARK = "dark", "Zarya Corporate Dark"
        LIGHT = "light", "Zarya Corporate Light"

    email = models.EmailField(
        "e-mail",
        unique=True
    )

    role = models.CharField(
        "роль",
        max_length=20,
        choices=Role.choices,
        default=Role.USER
    )

    theme = models.CharField(
        "тема",
        max_length=20,
        choices=Theme.choices,
        default=Theme.DARK
    )

    @property
    def is_admin_role(self):
        return self.is_superuser or self.role == self.Role.ADMIN

    @property
    def is_finance_director_role(self):
        return self.role == self.Role.MANAGER

    @property
    def is_general_director_role(self):
        return self.role == self.Role.GENERAL_DIRECTOR

    @property
    def is_invoice_uploader_role(self):
        return self.role == self.Role.USER

    @property
    def is_read_only_finance_role(self):
        return self.role == self.Role.ANALYST

    def get_role_display_name(self):
        return self.get_role_display()
