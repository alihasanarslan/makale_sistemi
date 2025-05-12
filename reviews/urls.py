from django.urls import path
from . import views

urlpatterns = [
    path('list/', views.review_list, name='review_list'),
    path('submit/<uuid:tracking_id>/', views.submit_review, name='submit_review'),
    path('status/<uuid:tracking_id>/', views.review_status, name='review_status'),
    path('send-to-author/<uuid:tracking_id>/', views.send_review_to_author, name='send_review_to_author'),
] 