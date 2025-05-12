from django.contrib import admin
from .models import User

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'is_editor', 'is_reviewer', 'created_at')
    list_filter = ('is_editor', 'is_reviewer')
    search_fields = ('email',)