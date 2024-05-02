from django.contrib import admin
from .models import QuestionLists

class QuestionListsAdmin(admin.ModelAdmin):
    # 관리자 페이지에서 표시할 필드 설정
    list_display = ('job_related_skills', 'problem_solving_ability', 'communication_skills', 'growth_potential', 'personality_traits', 'created_at', 'user',)
    
    # 필터 옵션 추가
    list_filter = ('user', 'created_at')
    
    # 검색 기능 추가
    search_fields = ('job_related_skills', 'problem_solving_ability', 'communication_skills', 'growth_potential', 'personality_traits')
    
    # 레코드 편집 시 표시할 필드
    fields = ('user', 'job_related_skills', 'problem_solving_ability', 'communication_skills', 'growth_potential', 'personality_traits', 'created_at')
    
    # created_at 필드가 자동으로 설정되도록 읽기 전용으로 설정
    readonly_fields = ('created_at',)

# QuestionLists 모델을 관리자 사이트에 등록
admin.site.register(QuestionLists, QuestionListsAdmin)
