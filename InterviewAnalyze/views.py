from django.shortcuts import get_object_or_404  # Django의 헬퍼 함수를 가져옵니다. 이 함수는 객체를 찾고, 없을 경우 404 오류를 반환합니다.
from rest_framework.views import APIView  # DRF의 APIView 클래스를 가져옵니다.
from rest_framework.response import Response  # DRF의 Response 클래스를 가져옵니다.
from rest_framework.permissions import IsAuthenticated  # 인증이 필요한 API를 설정하기 위해 가져옵니다.
from rest_framework.parsers import JSONParser  # JSON 데이터를 파싱하기 위해 JSONParser를 가져옵니다.
from .models import InterviewAnalysis, QuestionLists  # InterviewAnalysis 및 QuestionLists 모델을 가져옵니다.
import os  # OS 모듈을 가져옵니다.
from django.conf import settings  # Django 설정을 가져옵니다.
import logging  # 로깅 모듈을 가져옵니다.
import requests  # HTTP 요청을 위해 requests 모듈을 가져옵니다.

logger = logging.getLogger(__name__)  # 로거를 설정합니다.

class ResponseAPIView(APIView):
    parser_classes = [JSONParser]  # JSON 데이터를 파싱하기 위해 JSONParser를 사용합니다.
    permission_classes = [IsAuthenticated]  # 인증이 필요한 API로 설정합니다.

    def post(self, request, question_list_id):
        question_list = get_object_or_404(QuestionLists, id=question_list_id)  # 질문 목록을 찾고, 없을 경우 404 오류를 반환합니다.
        interview_response = InterviewAnalysis(question_list=question_list)  # 새로운 InterviewAnalysis 객체를 생성합니다.

        for i in range(1, 11):  # 10개의 스크립트를 처리한다고 가정합니다.
            script_key = f'script_{i}'
            if script_key not in request.data:
                continue  # 스크립트가 제공되지 않은 경우, 다음 스크립트로 넘어갑니다.

            script_text = request.data[script_key]  # 스크립트 텍스트를 가져옵니다.
            setattr(interview_response, f'response_{i}', script_text)  # 스크립트를 모델의 필드에 저장합니다.

        interview_response.save()  # 인터뷰 응답을 데이터베이스에 저장합니다.

        base_dir = settings.BASE_DIR  # 기본 디렉토리를 설정합니다.
        redundant_expressions_path = os.path.join(base_dir, 'InterviewAnalyze', 'redundant_expressions.txt')  # 잉여 표현 파일의 경로를 설정합니다.
        inappropriate_terms_path = os.path.join(base_dir, 'InterviewAnalyze', 'inappropriate_terms.txt')  # 부적절한 표현 파일의 경로를 설정합니다.

        try:
            with open(redundant_expressions_path, 'r') as file:
                redundant_expressions = file.read().splitlines()  # 잉여 표현 파일을 읽어옵니다.
            with open(inappropriate_terms_path, 'r') as file:
                inappropriate_terms = dict(line.strip().split(':') for line in file if ':' in line)  # 부적절한 표현 파일을 읽어옵니다.
        except FileNotFoundError as e:
            logger.error(f"File not found: {e}")  # 파일이 없을 경우 오류를 로깅합니다.
            return Response({"error": "Required file not found"}, status=500)  # 오류 응답을 반환합니다.

        response_data = []  # 응답 데이터를 저장할 리스트를 초기화합니다.
        all_responses = ""  # 전체 응답을 저장할 문자열을 초기화합니다.
        for i in range(1, 11):
            question_key = f'question_{i}'
            response_key = f'response_{i}'
            question_text = getattr(question_list, question_key, None)  # 질문 텍스트를 가져옵니다.
            response_text = getattr(interview_response, response_key, None)  # 응답 텍스트를 가져옵니다.

            if response_text:
                all_responses += f"{response_text}\n"  # 전체 응답에 추가합니다.

            found_redundant = [expr for expr in redundant_expressions if expr in response_text]  # 응답에서 잉여 표현을 찾습니다.
            corrections = {}
            corrected_text = response_text
            for term, replacement in inappropriate_terms.items():  # 부적절한 표현을 찾아 수정합니다.
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
            })  # 응답 데이터를 구성합니다.

        # GPT API 호출을 통해 총평 받기
        prompt = f"다음은 사용자의 면접 응답입니다:\n{all_responses}\n\n응답이 직무연관성, 문제해결력, 의사소통능력, 성장가능성, 인성과 관련하여 적절했는지 300자 내외로 총평을 작성해줘."
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                json={"model": "gpt-3.5-turbo-0125", "messages": [{"role": "user", "content": prompt}]},
                timeout=10
            )
            response.raise_for_status()
            gpt_feedback = response.json().get('choices')[0].get('message').get('content')
        except requests.exceptions.RequestException as e:
            logger.error(f"GPT API request failed: {e}")
            gpt_feedback = "총평을 가져오는 데 실패했습니다."

        return Response({
            'interview_id': interview_response.id,
            'responses': response_data,
            'gpt_feedback': gpt_feedback
        }, status=200)  # 응답 데이터를 반환합니다.