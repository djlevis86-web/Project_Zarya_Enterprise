from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User
from .permissions import user_is_admin

admin.site.register(User, UserAdmin)

def project_admin_site_has_permission(request):
    return user_is_admin(request.user)


admin.site.has_permission = project_admin_site_has_permission
