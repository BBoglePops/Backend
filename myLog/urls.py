from django.urls import path
from .views import MyInterviewDetailView, MyInterviewListView

urlpatterns = [
    path('<int:user_id>/interviews/', MyInterviewListView.as_view(), name='my_interview_list'),
    path('<int:user_id>/<int:interview_id>/scripts/', MyInterviewDetailView.as_view(), name='my_interview_detail')
]

