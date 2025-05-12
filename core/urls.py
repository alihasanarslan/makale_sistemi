from django.urls import path
from . import views

urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    path('makale-yukle/', views.PaperUploadView.as_view(), name='paper_upload'),
    path('makale-durum/', views.PaperStatusView.as_view(), name='paper_status'),
    path('yonetici/', views.AdminView.as_view(), name='admin'),
    path('hakem/', views.ReviewerView.as_view(), name='reviewer'),
]
