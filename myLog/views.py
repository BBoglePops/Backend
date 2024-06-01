from django.shortcuts import render

# Create your views here.
from django.http import Http404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from InterviewAnalyze.models import InterviewAnalysis
from django.contrib.auth.models import User
from Eyetrack.models import GazeTrackingResult

class MyInterviewDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id, interview_id):
        if request.user.id != user_id:
            return Response({"error": "You are not authorized to view this interview."}, status=403)

        try:
            interview = InterviewAnalysis.objects.get(id=interview_id, user_id=user_id)
        except InterviewAnalysis.DoesNotExist:
            raise Http404("No InterviewAnalysis found matching the criteria.")

        response_data = {
            "id": interview.id,
            "question_list_id": interview.question_list.id,
            "responses": [{
                "response": getattr(interview, f'response_{i}', ''),
                "redundancies": getattr(interview, f'redundancies_{i}', ''),
                "inappropriateness": getattr(interview, f'inappropriateness_{i}', ''),
                "corrections": getattr(interview, f'corrections_{i}', ''),
                "corrected_response": getattr(interview, f'corrected_response_{i}', '')
            } for i in range(1, 11)],
            "overall_feedback": interview.overall_feedback,
            "created_at": interview.created_at
        }

        return Response(response_data, status=200)


class MyInterviewListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        if request.user.id != user_id:
            return Response({"error": "You are not authorized to view these interviews."}, status=403)

        interviews = InterviewAnalysis.objects.filter(user_id=user_id).order_by('-created_at')
        response_data = [{
            "id": interview.id,
            "created_at": interview.created_at
        } for interview in interviews]

        return Response(response_data, status=200)

class GazeTrackingResultView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id, interview_id):
        if request.user.id != user_id:
            return Response({"error": "You are not authorized to view this gaze tracking result."}, status=403)

        try:
            gaze_tracking_result = GazeTrackingResult.objects.get(user_id=user_id, interview_id=interview_id)
        except GazeTrackingResult.DoesNotExist:
            raise Http404("No GazeTrackingResult found matching the criteria.")

        response_data = {
            "id": interview_id,
            "image_data": gaze_tracking_result.encoded_image,
            "feedback": gaze_tracking_result.feedback
        }

        return Response(response_data, status=200)