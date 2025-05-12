from django.contrib import admin
from .models import Paper, AnonymizedPaper, PaperLog

class PaperLogInline(admin.TabularInline):
    model = PaperLog
    extra = 0
    readonly_fields = ('action', 'timestamp', 'details')

@admin.register(Paper)
class PaperAdmin(admin.ModelAdmin):
    list_display = ('tracking_id', 'email', 'title', 'status', 'submitted_at')
    list_filter = ('status',)
    search_fields = ('tracking_id', 'email', 'title')
    readonly_fields = ('tracking_id',)
    inlines = [PaperLogInline]

@admin.register(AnonymizedPaper)
class AnonymizedPaperAdmin(admin.ModelAdmin):
    list_display = ('paper', 'anonymized_at')
    search_fields = ('paper__tracking_id', 'paper__email')