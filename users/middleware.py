from django.core.exceptions import PermissionDenied

from .models import User


class FinanceRoleMutationGuardMiddleware:
    """Block unsafe invoice mutations for finance read roles."""

    SAFE_METHODS = frozenset({
        "GET",
        "HEAD",
        "OPTIONS",
    })
    INVOICE_PATH_PREFIX = "/invoices/"
    GENERAL_DIRECTOR_ALLOWED_URL_NAMES = frozenset({
        "approve_invoice",
    })

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(
        self,
        request,
        view_func,
        view_args,
        view_kwargs,
    ):
        user = getattr(request, "user", None)

        if not user or not user.is_authenticated:
            return None

        if request.method in self.SAFE_METHODS:
            return None

        if not request.path_info.startswith(
            self.INVOICE_PATH_PREFIX
        ):
            return None

        role = getattr(user, "role", None)

        if role == User.Role.ANALYST:
            raise PermissionDenied(
                "Роль полного просмотра не может изменять данные."
            )

        if role == User.Role.GENERAL_DIRECTOR:
            resolver_match = getattr(
                request,
                "resolver_match",
                None,
            )
            url_name = (
                resolver_match.url_name
                if resolver_match
                else ""
            )

            if (
                url_name
                not in self.GENERAL_DIRECTOR_ALLOWED_URL_NAMES
            ):
                raise PermissionDenied(
                    "Генеральный директор может только утверждать "
                    "документы к оплате."
                )

        return None
