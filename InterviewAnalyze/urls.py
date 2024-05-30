from django.urls import path
from .views import ResponseAPIView

urlpatterns = [
    path('responses/<int:question_list_id>/', ResponseAPIView.as_view(), name='interview_responses'),
    # path('responses/<int:question_list_id>/analyze/', AnalyzeResponseAPIView.as_view(), name='analyze_responses'),
]
