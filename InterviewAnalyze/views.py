from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import JSONParser
from .models import InterviewAnalysis, QuestionLists
import os
from django.conf import settings
import logging
import requests

logger = logging.getLogger(__name__)

class ResponseAPIView(APIView):
    parser_classes = [JSONParser]
    permission_classes = [IsAuthenticated]

    def post(self, request, question_list_id):
        question_list = get_object_or_404(QuestionLists, id=question_list_id)
        interview_response = InterviewAnalysis(question_list=question_list)

        # 로그인한 사용자를 user 필드에 할당
        interview_response.user = request.user

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

        response_data = []
        all_responses = ""
        for i in range(1, 11):
            script_key = f'script_{i}'
            response_key = f'response_{i}'
            question_key = f'question_{i}'
            script_text = request.data.get(script_key, "")
            question_text = getattr(question_list, question_key, "")

            # 잉여 표현과 부적절한 표현을 분석
            found_redundant = [expr for expr in redundant_expressions if expr in script_text]
            corrections = {}
            corrected_text = script_text
            for term, replacement in inappropriate_terms.items():
                if term in script_text:
                    corrections[term] = replacement
                    corrected_text = corrected_text.replace(term, replacement)

            setattr(interview_response, f'response_{i}', script_text)
            setattr(interview_response, f'redundancies_{i}', ', '.join(found_redundant))
            setattr(interview_response, f'inappropriateness_{i}', ', '.join(corrections.keys()))
            setattr(interview_response, f'corrections_{i}', str(corrections))
            setattr(interview_response, f'corrected_response_{i}', corrected_text)

            response_data.append({
                'question': question_text,
                'response': script_text,
                'redundancies': found_redundant,
                'inappropriateness': list(corrections.keys()),
                'corrections': corrections,
                'corrected_response': corrected_text,
            })

            if script_text:
                all_responses += f"{script_text}\n"

        interview_response.save()

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
            interview_response.overall_feedback = gpt_feedback  # 총평을 overall_feedback 필드에 저장
        except requests.exceptions.RequestException as e:
            logger.error(f"GPT API request failed: {e}")
            gpt_feedback = "총평을 가져오는 데 실패했습니다."
            interview_response.overall_feedback = gpt_feedback  # 실패 메시지를 저장

        interview_response.save()  # 변경 사항 저장

        return Response({
            'interview_id': interview_response.id,
            'responses': response_data,
            'gpt_feedback': gpt_feedback
        }, status=200)