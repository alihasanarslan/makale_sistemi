"""
URL configuration for makale_sistemi project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
# makale_sistemi/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from core import views as core_views


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', core_views.index, name='index'),
    path('editor/', core_views.admin_page, name='admin'),  # Editör paneli
    path('hakem/', core_views.reviewer_page, name='reviewer'),  # Hakem paneli
    path('paper-status/', core_views.paper_status_page, name='paper_status'),  # Makale durumu
    path('upload/', core_views.paper_upload_page, name='paper_upload'),  # Makale yükleme
    path('api/', include('core.urls')),
    path('api/papers/', include('papers.urls')),
    path('api/reviews/', include('reviews.urls')),
    path('api/users/', include('users.urls')),  # users URL'lerini api/users/ altına taşıyın
    path('', RedirectView.as_view(url='/api/', permanent=True)),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)