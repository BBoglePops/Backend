from django.urls import path
from .views import *

urlpatterns = [
    path('responses/<int:question_list_id>/', ResponseAPIView.as_view(), name='interview_responses'),
    # path('responses/<int:question_list_id>/analyze/', AnalyzeResponseAPIView.as_view(), name='analyze_responses'),
   
    path('voice/', VoiceAPIView.as_view(), name='voice'), 
    path('voice/<int:question_list_id>/', VoiceAPIView.as_view(), name='voice_with_question_list')
]
