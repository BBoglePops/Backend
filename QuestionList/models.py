from django.db import models
from django.conf import settings

class QuestionLists(models.Model):
    job_related_skills = models.CharField(max_length=255)  # 직무 관련 능력
    problem_solving_ability = models.CharField(max_length=255)  # 문제 해결 능력
    communication_skills = models.CharField(max_length=255)  # 의사소통 능력
    growth_potential = models.CharField(max_length=255)  # 성장 가능성 및 개인 발전 의지
    personality_traits = models.CharField(max_length=255)  # 인성
    created_at = models.DateTimeField(auto_now_add=True)  # 질문이 생성된 시간
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)  # 각 유저에 대한 질문 데이터 연결

