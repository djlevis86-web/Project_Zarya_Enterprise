# Generated for Project Zarya user access policy.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0005_role_label_documents"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("ADMIN", "Администратор"),
                    ("MANAGER", "Финансовый директор"),
                    ("GENERAL_DIRECTOR", "Генеральный директор"),
                    ("USER", "Загрузчик документов"),
                    ("ANALYST", "Полный просмотр"),
                ],
                default="USER",
                max_length=20,
                verbose_name="роль",
            ),
        ),
    ]
