from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from django.views.generic import View

from .forms import AuthForm, RegistrationForm

INVALID_CREDENTIALS_ERROR = "Неверный логин или пароль! Повторите попытку."


def _first_error(form):
    """Return a human readable message for any validation error of ``form``."""
    for field_errors in form.errors.values():
        if field_errors:
            return str(field_errors[0])
    return None


class AuthView(View):
    """Авторизация"""

    @staticmethod
    def get(request):
        return render(request, "user/auth.html", {"form": AuthForm()})

    @staticmethod
    def post(request):
        form = AuthForm(request.POST)

        if form.is_valid():
            email = form.cleaned_data["email"].strip().lower()
            user = authenticate(
                request, username=email, password=form.cleaned_data["password"]
            )

            if user is not None:
                login(request, user)
                return redirect("dashboard:index")

        return render(
            request,
            "user/auth.html",
            {"form": form, "error": INVALID_CREDENTIALS_ERROR},
        )


class RegistrationView(View):
    """Регистрация"""

    @staticmethod
    def get(request):
        return render(request, "user/registration.html", {"form": RegistrationForm()})

    @staticmethod
    def post(request):
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            if user is None:
                return render(
                    request,
                    "user/registration.html",
                    {"form": form, "error": INVALID_CREDENTIALS_ERROR},
                )
            login(request, user)
            return redirect("dashboard:index")

        return render(
            request,
            "user/registration.html",
            {"form": form, "error": _first_error(form)},
        )


class LogoutView(View):
    """Выход"""

    @staticmethod
    def get(request):
        logout(request)
        return redirect("dashboard:index")

    post = get
