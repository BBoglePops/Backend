from django.shortcuts import render
import requests
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import re
from rest_framework.permissions import IsAuthenticated  # REST framework의 인증 클래스 임포트
from .models import QuestionLists  # 모델 임포트

class ChatGPTView(APIView):
    permission_classes = [IsAuthenticated]  # 인증된 사용자만 접근 허용

    def post(self, request):
        # 요청에서 필요한 데이터를 추출
        user_input_field = request.data.get('input_field', '')
        user_input_job = request.data.get('input_job', '')

        # 입력값 검증: 분야와 직무 입력이 모두 필요
        if not user_input_field or not user_input_job:
            return Response({"error": "분야와 직무 입력은 필수입니다."}, status=status.HTTP_400_BAD_REQUEST)

        # 사용자 입력을 기반으로 수정된 질문 문자열 생성
        modified_input = f"{user_input_field}분야의 {user_input_job}직무와 관련된 면접 질문 10가지 리스트업해줘 한국어로"

        # OpenAI API 호출
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                json={
                    "model": "gpt-3.5-turbo-0125",
                    "messages": [{"role": "user", "content": modified_input}]
                },
                timeout=10  # 10초 후 타임아웃
            )
            response.raise_for_status()  # 오류 응답이 있을 경우 예외 발생
        except requests.exceptions.RequestException as e:
            return Response({"error": f"서버 오류: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 응답으로 받은 텍스트에서 질문 추출
        questions_text = response.json().get('choices')[0].get('message').get('content')
        questions_list = re.split(r'\d+\.', questions_text)  # 숫자 점(.)을 기준으로 문자열 분할
        questions_list = [q.strip() for q in questions_list if q.strip()]  # 공백 제거 및 빈 문자열 필터링

        # 각 질문을 데이터베이스에 저장
        for question in questions_list:
            QuestionLists.objects.create(
                job_related_skills=question,  # 직무 관련 능력 필드에 질문 저장
                user=request.user  # 요청을 보낸 사용자와 연결
            )

        # 성공 응답 반환
        return Response({"message": "질문이 성공적으로 저장되었습니다."}, status=status.HTTP_201_CREATED)
