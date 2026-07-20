from django.test import TestCase

from users.forms import (
    UserAdminCreateForm,
    UserAdminEditForm,
)
from users.models import User


STRONG_PASSWORD = "M7!vQ2#pL9@xR4$k"


class AdminPasswordValidationTests(TestCase):

    def _form_data(
        self,
        *,
        email,
        password1,
        password2,
    ):
        return {
            "email": email,
            "first_name": "Security",
            "last_name": "Tester",
            "role": User.Role.USER,
            "is_active": "on",
            "theme": User.Theme.DARK,
            "password1": password1,
            "password2": password2,
        }

    def test_create_form_rejects_weak_password(self):
        form = UserAdminCreateForm(
            data=self._form_data(
                email="weak-create@example.invalid",
                password1="1",
                password2="1",
            )
        )

        self.assertFalse(
            form.is_valid()
        )
        self.assertIn(
            "password1",
            form.errors,
        )
        self.assertTrue(
            form.errors["password1"]
        )

    def test_edit_form_rejects_weak_password(self):
        user = User(
            username="weak-edit",
            email="weak-edit@example.invalid",
            first_name="Security",
            last_name="Tester",
            role=User.Role.USER,
            is_active=True,
            theme=User.Theme.DARK,
        )

        form = UserAdminEditForm(
            instance=user,
            data=self._form_data(
                email=user.email,
                password1="1",
                password2="1",
            ),
        )

        self.assertFalse(
            form.is_valid()
        )
        self.assertIn(
            "password1",
            form.errors,
        )
        self.assertTrue(
            form.errors["password1"]
        )

    def test_create_form_accepts_strong_password(self):
        form = UserAdminCreateForm(
            data=self._form_data(
                email="strong-create@example.invalid",
                password1=STRONG_PASSWORD,
                password2=STRONG_PASSWORD,
            )
        )

        self.assertTrue(
            form.is_valid(),
            form.errors.as_json(),
        )

    def test_edit_form_accepts_strong_password(self):
        user = User(
            username="strong-edit",
            email="strong-edit@example.invalid",
            first_name="Security",
            last_name="Tester",
            role=User.Role.USER,
            is_active=True,
            theme=User.Theme.DARK,
        )

        form = UserAdminEditForm(
            instance=user,
            data=self._form_data(
                email=user.email,
                password1=STRONG_PASSWORD,
                password2=STRONG_PASSWORD,
            ),
        )

        self.assertTrue(
            form.is_valid(),
            form.errors.as_json(),
        )

    def test_edit_form_allows_empty_password(self):
        user = User(
            username="unchanged-password",
            email="unchanged-password@example.invalid",
            first_name="Security",
            last_name="Tester",
            role=User.Role.USER,
            is_active=True,
            theme=User.Theme.DARK,
        )

        form = UserAdminEditForm(
            instance=user,
            data=self._form_data(
                email=user.email,
                password1="",
                password2="",
            ),
        )

        self.assertTrue(
            form.is_valid(),
            form.errors.as_json(),
        )

    def test_create_form_rejects_password_similar_to_new_first_name(
        self,
    ):
        password = "Security2026!"

        form = UserAdminCreateForm(
            data=self._form_data(
                email="similar-create@example.invalid",
                password1=password,
                password2=password,
            )
        )

        self.assertFalse(
            form.is_valid()
        )
        self.assertIn(
            "password1",
            form.errors,
        )
        self.assertTrue(
            form.errors["password1"]
        )

    def test_edit_form_rejects_password_similar_to_changed_first_name(
        self,
    ):
        user = User(
            username="before-change",
            email="before-change@example.invalid",
            first_name="Before",
            last_name="Change",
            role=User.Role.USER,
            is_active=True,
            theme=User.Theme.DARK,
        )

        password = "Security2026!"

        form = UserAdminEditForm(
            instance=user,
            data=self._form_data(
                email=user.email,
                password1=password,
                password2=password,
            ),
        )

        self.assertFalse(
            form.is_valid()
        )
        self.assertIn(
            "password1",
            form.errors,
        )
        self.assertTrue(
            form.errors["password1"]
        )

    def test_password_mismatch_keeps_existing_error(self):
        form = UserAdminCreateForm(
            data=self._form_data(
                email="mismatch@example.invalid",
                password1=STRONG_PASSWORD,
                password2=f"{STRONG_PASSWORD}-other",
            )
        )

        self.assertFalse(
            form.is_valid()
        )
        self.assertIn(
            "password2",
            form.errors,
        )
        self.assertIn(
            "Пароли не совпадают.",
            form.errors["password2"],
        )
