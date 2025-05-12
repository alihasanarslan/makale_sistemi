"""core-views.py"""
from django.shortcuts import render
from django.views.generic import TemplateView


class IndexView(TemplateView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Ana sayfa için gerekli context verilerini buraya ekleyebilirsiniz
        return context
    template_name = "core/index.html"

class PaperUploadView(TemplateView):
    template_name = "core/paper_upload.html"

class PaperStatusView(TemplateView):
    template_name = "core/paper_status.html"

class AdminView(TemplateView):
    template_name = "core/admin.html"

class ReviewerView(TemplateView):
    template_name = "core/reviewer.html"

def index(request):
    """Ana sayfa görünümü"""
    return render(request, 'core/index.html')

def admin_page(request):
    """Editör paneli görünümü"""
    return render(request, 'core/admin.html')

def reviewer_page(request):
    """Hakem paneli görünümü"""
    return render(request, 'core/reviewer.html')

def paper_status_page(request):
    """Makale durumu görünümü"""
    return render(request, 'core/paper_status.html')

def paper_upload_page(request):
    """Makale yükleme görünümü"""
    return render(request, 'core/paper_upload.html')

