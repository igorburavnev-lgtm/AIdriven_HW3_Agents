from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from django.views.generic import View

from .forms import AuthForm, RegistrationForm

INVALID_CREDENTIALS_ERROR = "Неверный логин или пароль! Повторите попытку."


def _form_error_message(form) -> str | None:
    """Return the first validation message of ``form`` whatever field it belongs to."""
    for errors in form.errors.values():
        if errors:
            return str(errors[0])
    return None


class AuthView(View):
    """Авторизация"""

    @staticmethod
    def get(request):
        # AuthForm (the class) used to be passed instead of an instance, so the
        # template rendered field objects and the inputs never appeared.
        return render(request, "user/auth.html", {"form": AuthForm()})

    @staticmethod
    def post(request):
        form = AuthForm(request.POST)

        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data["email"].strip().lower(),
                password=form.cleaned_data["password"],
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
        return render(
            request, "user/registration.html", {"form": RegistrationForm()}
        )

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

        # The original read form.errors["__all__"], which raised KeyError (-> 500)
        # whenever the problem was attached to a single field.
        return render(
            request,
            "user/registration.html",
            {"form": form, "error": _form_error_message(form)},
        )


class LogoutView(View):
    """Выход"""

    @staticmethod
    def get(request):
        logout(request)
        return redirect("dashboard:index")

    post = get
