from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from account.forms import UserAdminForm, CustomUserCreationForm
from account.models import (
    User,
    UserProfile,
)


class CustomUserAdmin(UserAdmin):
    list_display = (
        'email', 'username', 'last_login', 'date_joined', 'partner',
    )
    list_filter = (
        'is_superuser', 'is_staff', 'is_active', 'groups', 'workspaces',
    )
    search_fields = ('email', 'username',)
    exclude = ('date_joined', 'last_login')
    raw_id_fields = ('partner',)

    add_form = CustomUserCreationForm
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'email'),
        }),
        ('Personal Info', {
            'classes': ('wide',),
            'fields': ('first_name', 'last_name'),
        }),
    )

    form = UserAdminForm
    fieldsets = (
        (
            None, {
                'fields': ('username', 'password')
            }
        ),
        (
            'Personal info', {
                'fields': ('first_name', 'last_name', 'email')
            }
        ),
        (
            'Organization info', {
                'fields': ('partner', 'organization')
            }
        ),
        (
            'Application Permissions', {
                'fields': ('groups', 'workspaces', 'imo_clusters',)
            }
        ),
        (
            'Django Permissions', {
                'fields': ('is_active', 'is_staff', 'is_superuser', 'user_permissions')
            }
        ),
    )

    filter_horizontal = ('groups', 'user_permissions', 'workspaces', 'imo_clusters')


admin.site.register(User, CustomUserAdmin)
admin.site.register(UserProfile)
