from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'role', 'total_earnings', 'is_verified', 'date_joined']
    list_filter = ['role', 'is_verified']
    fieldsets = UserAdmin.fieldsets + (('Platform', {'fields': ('role', 'avatar', 'bio', 'total_earnings', 'is_verified')}),)
