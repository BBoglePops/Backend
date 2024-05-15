from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from .models import QuestionLists, ProblemSolvingQuestion, CommunicationSkillQuestion, GrowthPotentialQuestion, PersonalityTraitQuestion
import random
import requests
import logging

logger = logging.getLogger(__name__)

class ChatGPTView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # 사용자 입력 필드를 가져옴
        user_input_field = request.data.get('input_field', '')
        user_input_job = request.data.get('input_job', '')
        selected_categories = request.data.get('selected_categories', [])

        # 입력 필드와 직무가 비어있는지 확인
        if not user_input_field or not user_input_job:
            return Response({"error": "분야와 직무 입력은 필수입니다."}, status=status.HTTP_400_BAD_REQUEST)

        # OpenAI API 요청을 위한 입력값 수정
        modified_input = f"{user_input_field}분야의 {user_input_job}직무와 관련된 면접 질문 10가지 리스트업해줘 질문 번호 없이 질문 텍스트만 뽑아줘 한국어로"
        try:
            # OpenAI API 호출
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                json={"model": "gpt-3.5-turbo-0125", "messages": [{"role": "user", "content": modified_input}]},
                timeout=10
            )
            response.raise_for_status()
            # 응답에서 질문 목록을 가져옴
            job_related_questions = response.json().get('choices')[0].get('message').get('content').splitlines()
            job_related_questions = [q.strip() for q in job_related_questions if q.strip()]
        except requests.exceptions.RequestException as e:
            return Response({"error": f"서버 오류: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 처음 10개의 질문만 선택
        all_questions = job_related_questions[:10]

        # 각 카테고리에 대한 모델 정의
        category_models = {
            'problem_solving': ProblemSolvingQuestion,
            'communication_skills': CommunicationSkillQuestion,
            'growth_potential': GrowthPotentialQuestion,
            'personality_traits': PersonalityTraitQuestion
        }

        # 선택된 카테고리의 질문 추가
        for category in selected_categories:
            if category in category_models:
                model = category_models[category]
                questions = list(model.objects.all().values_list('question', flat=True))
                random_questions = random.sample(questions, min(len(questions), 2))
                all_questions.extend(random_questions)

        # 전체 질문을 섞고 10개의 질문만 선택
        all_questions = random.sample(all_questions, 10)

        # 질문 리스트 인스턴스 생성
        question_list = QuestionLists(user=request.user)
        # 질문을 question_1 ~ question_10 속성에 할당
        for i, question in enumerate(all_questions, 1):
            setattr(question_list, f'question_{i}', question)
        question_list.save()

        # 질문을 정렬된 순서로 반환
        sorted_questions = [getattr(question_list, f'question_{i}') for i in range(1, 11)]

        return Response({"id": question_list.id, "questions": sorted_questions}, status=status.HTTP_201_CREATED)
