from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import InterviewAnalysis
from .serializers import InterviewResponseSerializer
from QuestionList.models import QuestionLists
from google.cloud import speech
from google.cloud.speech import RecognitionConfig, RecognitionAudio
import os
from django.conf import settings


class ResponseAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, question_list_id):
        question_list = get_object_or_404(QuestionLists, id=question_list_id)
        interview_response = InterviewAnalysis(question_list=question_list)

        client = speech.SpeechClient()
        config = RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.MP3,
            sample_rate_hertz=16000,
            language_code="ko-KR"
        )

        for i in range(1, 11):
            audio_filename = f'audio_{i}.mp3'
            audio_path = os.path.join(settings.MEDIA_ROOT, audio_filename)
            with open(audio_path, "rb") as audio_file:
                content = audio_file.read()

            audio = RecognitionAudio(content=content)
            response = client.recognize(config=config, audio=audio)
            transcript = ' '.join([result.alternatives[0].transcript for result in response.results])
            setattr(interview_response, f'response_{i}', transcript)

        interview_response.save()
        return Response(InterviewResponseSerializer(interview_response).data, status=201)
