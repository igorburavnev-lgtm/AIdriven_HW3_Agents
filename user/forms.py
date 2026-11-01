from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

User = get_user_model()

PASSWORDS_MISMATCH_ERROR = "Введенные пароли не совпадают"
DUPLICATE_EMAIL_ERROR = (
    "Данный e-mail уже зарегистрирован! Введите другой e-mail или"
    " воспользуйтесь формой авторизации."
)


class RegistrationForm(forms.Form):
    """Форма регистрации пользователей"""

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={"class": "form-control my-3 p-4", "placeholder": "Email"}
        ),
    )
    password1 = forms.CharField(
        required=True,
        widget=forms.PasswordInput(
            attrs={"class": "form-control my-3 p-4", "placeholder": "Пароль"}
        ),
    )
    password2 = forms.CharField(
        required=True,
        widget=forms.PasswordInput(
            attrs={"class": "form-control my-3 p-4", "placeholder": "Повторите пароль"}
        ),
    )

    def clean(self):
        cleaned_data = super().clean()
        # .get() instead of [...] : when the e-mail field itself is invalid the
        # key is absent and the original code crashed with KeyError.
        email = (cleaned_data.get("email") or "").strip().lower()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            raise ValidationError(PASSWORDS_MISMATCH_ERROR)

        if email:
            if User.objects.filter(email__iexact=email).exists():
                raise ValidationError(DUPLICATE_EMAIL_ERROR)
            if password1:
                # The form is a plain forms.Form, so AUTH_PASSWORD_VALIDATORS
                # would otherwise never run.
                validate_password(password1)

        # Keep the normalised value: the login view lowercases the e-mail, so a
        # mixed-case registration used to produce an account nobody could log in to.
        cleaned_data["email"] = email
        return cleaned_data

    def save(self):
        email = self.cleaned_data["email"]
        password = self.cleaned_data["password1"]
        User.objects.create_user(username=email, email=email, password=password)
        return authenticate(username=email, password=password)


class AuthForm(forms.Form):
    """Форма авторизации пользователей"""

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={"class": "form-control my-3 p-4", "placeholder": "Email"}
        ),
    )
    password = forms.CharField(
        required=True,
        widget=forms.PasswordInput(
            attrs={"class": "form-control my-3 p-4", "placeholder": "Пароль"}
        ),
    )
