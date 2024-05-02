from django.shortcuts import render
import requests
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import re  # 정규 표현식 라이브러리 추가

class ChatGPTView(APIView):
    def post(self, request):
        user_input_field = request.data.get('input_field', '')
        user_input_job = request.data.get('input_job', '')

        # 입력 검증
        if not user_input_field or not user_input_job:
            return Response({"error": "분야와 직무 입력은 필수입니다."}, status=status.HTTP_400_BAD_REQUEST)

        modified_input = f"{user_input_field}분야의 {user_input_job}직무와 관련된 면접 질문 10가지 리스트업해줘 한국어로"
        
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                json={
                    "model": "gpt-3.5-turbo-0125",  # 사용하고 싶은 모델명
                    "messages": [{"role": "user", "content": modified_input}]
                },
                timeout=10  # 10초 내에 응답이 없는 경우 타임아웃
            )
            response.raise_for_status()  # 응답 코드가 4xx/5xx인 경우 예외 발생
        except requests.exceptions.HTTPError as e:
            return Response({"error": f"OpenAI 서버 에러: {str(e)}"}, status=response.status_code)
        except requests.exceptions.ConnectionError:
            return Response({"error": "OpenAI 서버에 연결할 수 없습니다."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except requests.exceptions.Timeout:
            return Response({"error": "OpenAI 서버 응답 시간 초과."}, status=status.HTTP_504_GATEWAY_TIMEOUT)
        except requests.exceptions.RequestException as e:
            return Response({"error": f"요청 오류: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


        # 성공적인 응답 처리
        return Response(response.json(), status=status.HTTP_200_OK)