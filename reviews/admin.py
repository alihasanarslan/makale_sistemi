from django.contrib import admin
from .models import Review, Message

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('paper', 'reviewer', 'status', 'assigned_at', 'updated_at')
    list_filter = ('status',)
    search_fields = ('paper__tracking_id', 'reviewer__email')

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('paper', 'sender_email', 'is_editor', 'created_at')
    list_filter = ('is_editor',)
    search_fields = ('paper__tracking_id', 'sender_email', 'content')