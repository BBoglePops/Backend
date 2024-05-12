from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import FileUploadParser
from .models import InterviewAnalysis, QuestionLists
from google.cloud import speech
from google.cloud.speech import RecognitionConfig, RecognitionAudio
import os
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class ResponseAPIView(APIView):
    # 파일 업로드를 위해 FileUploadParser 설정
    parser_classes = [FileUploadParser]
    # 사용자 인증이 필요한 API 설정
    permission_classes = [IsAuthenticated]

    def post(self, request, question_list_id):
        # 질문 목록 ID를 기반으로 해당 객체를 찾고, 없을 경우 404 오류 반환
        question_list = get_object_or_404(QuestionLists, id=question_list_id)
        interview_response = InterviewAnalysis(question_list=question_list)

        # Google Cloud의 Speech-to-Text API를 활용해 음성 인식 클라이언트 설정
        client = speech.SpeechClient()
        config = RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.MP3,
            sample_rate_hertz=16000,
            language_code="ko-KR"
        )

        # 파일들을 순회하며 음성을 텍스트로 변환
        for i in range(1, 11):  # 10개의 파일을 처리한다고 가정
            file_key = f'audio_{i}'
            if file_key not in request.FILES:
                continue  # 파일이 제공되지 않은 경우, 다음 파일로 넘어감

            audio_file = request.FILES[file_key]
            audio = RecognitionAudio(content=audio_file.read())
            response = client.recognize(config=config, audio=audio)
            transcript = ' '.join([result.alternatives[0].transcript for result in response.results])
            setattr(interview_response, f'response_{i}', transcript)

        # 인터뷰 응답을 데이터베이스에 저장
        interview_response.save()

        # 설정 파일에서 잉여 표현 및 부적절한 표현에 대한 파일 로드
        base_dir = settings.BASE_DIR
        redundant_expressions_path = os.path.join(base_dir, 'InterviewAnalyze', 'redundant_expressions.txt')
        inappropriate_terms_path = os.path.join(base_dir, 'InterviewAnalyze', 'inappropriate_terms.txt')

        try:
            with open(redundant_expressions_path, 'r') as file:
                redundant_expressions = file.read().splitlines()
            with open(inappropriate_terms_path, 'r') as file:
                inappropriate_terms = dict(line.strip().split(':') for line in file if ':' in line)
        except FileNotFoundError as e:
            logger.error(f"File not found: {e}")
            return Response({"error": "Required file not found"}, status=500)

        # 응답 데이터 구성 및 반환
        response_data = []
        for i in range(1, 11):
            question_key = f'question_{i}'
            response_key = f'response_{i}'
            question_text = getattr(question_list, question_key, None)
            response_text = getattr(interview_response, response_key, None)

            found_redundant = [expr for expr in redundant_expressions if expr in response_text]
            corrections = {}
            corrected_text = response_text
            for term, replacement in inappropriate_terms.items():
                if term in response_text:
                    corrections[term] = replacement
                    corrected_text = corrected_text.replace(term, replacement)

            response_data.append({
                'question': question_text,
                'response': response_text,
                'redundancies': found_redundant,
                'inappropriateness': list(corrections.keys()),
                'corrections': corrections,
                'corrected_response': corrected_text
            })

        return Response({
            'interview_id': interview_response.id,
            'responses': response_data
        }, status=200)
