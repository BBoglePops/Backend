from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import InterviewAnalysis
from QuestionList.models import QuestionLists
from google.cloud import speech
from google.cloud.speech import RecognitionConfig, RecognitionAudio
import os
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class ResponseAPIView(APIView):
    # 사용자 인증을 필요로 하는 API 보안 설정
    permission_classes = [IsAuthenticated]

    def post(self, request, question_list_id):
        # 주어진 question_list_id로 QuestionLists 객체 조회, 없으면 404 에러 반환
        question_list = get_object_or_404(QuestionLists, id=question_list_id)
        # InterviewAnalysis 모델 인스턴스 생성 및 질문 목록과 연결
        interview_response = InterviewAnalysis(question_list=question_list)

        # Google Cloud의 Speech-to-Text API를 활용해 음성 인식 클라이언트 설정
        client = speech.SpeechClient()
        config = RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.MP3,
            sample_rate_hertz=16000,
            language_code="ko-KR"
        )

        # 10개의 오디오 파일을 순회하며 텍스트로 변환
        for i in range(1, 11):
            audio_filename = f'audio_{i}.mp3'
            audio_path = os.path.join(settings.MEDIA_ROOT, audio_filename)
            with open(audio_path, "rb") as audio_file:
                content = audio_file.read()

            audio = RecognitionAudio(content=content)
            response = client.recognize(config=config, audio=audio)
            transcript = ' '.join([result.alternatives[0].transcript for result in response.results])
            setattr(interview_response, f'response_{i}', transcript)

        # 데이터베이스에 응답 데이터 저장
        interview_response.save()

        # 설정 파일에서 잉여 표현 및 부적절한 표현에 대한 파일 경로 설정
        base_dir = settings.BASE_DIR
        redundant_expressions_path = os.path.join(base_dir, 'InterviewAnalyze', 'redundant_expressions.txt')
        inappropriate_terms_path = os.path.join(base_dir, 'InterviewAnalyze', 'inappropriate_terms.txt')

        # 파일을 로드하고, 없을 경우 로깅 후 에러 응답 반환
        try:
            with open(redundant_expressions_path, 'r') as file:
                redundant_expressions = file.read().splitlines()
            with open(inappropriate_terms_path, 'r') as file:
                inappropriate_terms = dict(line.strip().split(':') for line in file if ':' in line)
        except FileNotFoundError as e:
            logger.error(f"File not found: {e}")
            return Response({"error": "Required file not found"}, status=500)

        # 응답 데이터 구성: 각 응답에 대한 질문, 응답, 잉여 표현 검사, 부적절한 표현과 교정 내용 포함
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

        # 최종 JSON 형태로 클라이언트에 응답 반환
        return Response({
            'interview_id': interview_response.id,
            'responses': response_data
        }, status=200)
