from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import get_user_model

User = get_user_model()


def make_username_from_email(email, instance=None):
    base = email.split("@")[0].strip().lower() or "user"
    base = "".join(
        char
        for char in base
        if char.isalnum() or char in "._-"
    )[:120] or "user"

    username = base
    counter = 1

    queryset = User.objects.all()

    if instance and instance.pk:
        queryset = queryset.exclude(pk=instance.pk)

    while queryset.filter(username=username).exists():
        counter += 1
        suffix = f"-{counter}"
        username = f"{base[:120 - len(suffix)]}{suffix}"

    return username


def apply_role_flags(user):
    if user.role == User.Role.ADMIN:
        user.is_staff = True
        user.is_superuser = True

    elif user.role == User.Role.MANAGER:
        user.is_staff = True
        user.is_superuser = False

    else:
        user.is_staff = False
        user.is_superuser = False

    return user


class LoginForm(AuthenticationForm):

    username = forms.EmailField(
        label="E-mail",
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "Введите e-mail",
                "autocomplete": "email",
            }
        )
    )

    password = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Введите пароль",
                "autocomplete": "current-password",
            }
        )
    )


class UserSettingsForm(forms.ModelForm):

    class Meta:

        model = User

        fields = [
            "first_name",
            "last_name",
            "email",
            "theme",
        ]

        widgets = {
            "first_name": forms.TextInput(
                attrs={
                    "class": "form-control"
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "class": "form-control"
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control"
                }
            ),
            "theme": forms.Select(
                attrs={
                    "class": "form-control"
                }
            ),
        }


class ProfileForm(UserSettingsForm):
    pass


class UserAdminCreateForm(forms.ModelForm):

    password1 = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "autocomplete": "new-password",
            }
        )
    )

    password2 = forms.CharField(
        label="Повтор пароля",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "autocomplete": "new-password",
            }
        )
    )

    class Meta:

        model = User

        fields = [
            "email",
            "first_name",
            "last_name",
            "role",
            "is_active",
            "theme",
        ]

        widgets = {
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "user@example.ru",
                }
            ),
            "first_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Имя",
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Фамилия",
                }
            ),
            "role": forms.Select(
                attrs={
                    "class": "form-control"
                }
            ),
            "is_active": forms.CheckboxInput(),
            "theme": forms.Select(
                attrs={
                    "class": "form-control"
                }
            ),
        }

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "Пользователь с таким e-mail уже существует."
            )

        return email

    def clean(self):
        cleaned_data = super().clean()

        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            self.add_error(
                "password2",
                "Пароли не совпадают."
            )

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)

        user.email = user.email.strip().lower()
        user.username = make_username_from_email(user.email)
        user.set_password(
            self.cleaned_data["password1"]
        )

        apply_role_flags(user)

        if commit:
            user.save()

        return user


class UserAdminEditForm(forms.ModelForm):

    password1 = forms.CharField(
        label="Новый пароль",
        required=False,
        help_text="Оставьте пустым, если пароль менять не нужно.",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "autocomplete": "new-password",
            }
        )
    )

    password2 = forms.CharField(
        label="Повтор нового пароля",
        required=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "autocomplete": "new-password",
            }
        )
    )

    class Meta:

        model = User

        fields = [
            "email",
            "first_name",
            "last_name",
            "role",
            "is_active",
            "theme",
        ]

        widgets = {
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control",
                }
            ),
            "first_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                }
            ),
            "role": forms.Select(
                attrs={
                    "class": "form-control"
                }
            ),
            "is_active": forms.CheckboxInput(),
            "theme": forms.Select(
                attrs={
                    "class": "form-control"
                }
            ),
        }

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        queryset = User.objects.filter(
            email__iexact=email
        )

        if self.instance.pk:
            queryset = queryset.exclude(
                pk=self.instance.pk
            )

        if queryset.exists():
            raise forms.ValidationError(
                "Пользователь с таким e-mail уже существует."
            )

        return email

    def clean(self):
        cleaned_data = super().clean()

        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 or password2:
            if password1 != password2:
                self.add_error(
                    "password2",
                    "Пароли не совпадают."
                )

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)

        user.email = user.email.strip().lower()
        user.username = make_username_from_email(
            user.email,
            instance=user
        )

        password1 = self.cleaned_data.get("password1")

        if password1:
            user.set_password(password1)

        apply_role_flags(user)

        if commit:
            user.save()

        return user
