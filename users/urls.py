from django.urls import path
from . import views

urlpatterns = [

    path('reviewers/list/', views.reviewer_list, name='reviewer_list'),
    path('reviewers/add/', views.add_reviewer, name='add_reviewer'),
    path('reviewers/delete/<int:reviewer_id>/', views.delete_reviewer, name='delete_reviewer'),
]