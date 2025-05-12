from django.urls import path
from . import views

urlpatterns = [
    path('upload/', views.upload_paper, name='upload_paper'),
    path('status/<uuid:tracking_id>/', views.paper_status, name='paper_status'),
    path('list/', views.paper_list, name='paper_list'),
    path('detail/<uuid:tracking_id>/', views.paper_detail, name='paper_detail'),
    path('anonymize/<uuid:tracking_id>/', views.anonymize_paper, name='anonymize_paper'),
    path('restore/<uuid:tracking_id>/', views.restore_original_paper, name='restore_original_paper'),
    path('assign/<uuid:tracking_id>/', views.assign_reviewer, name='assign_reviewer'),
    path('messages/<uuid:tracking_id>/', views.paper_messages, name='paper_messages'),
    path('sync-files/<uuid:tracking_id>/', views.sync_files, name='sync_files'),
    path('review-status/<uuid:tracking_id>/', views.review_status, name='review_status'),
    path('update-keywords/<uuid:tracking_id>/', views.update_keywords, name='update_keywords'),
    path('update-field/<uuid:tracking_id>/', views.update_field, name='update_field'),
]