# InterviewAnalysis/models.py

from django.db import models
from QuestionList.models import QuestionLists

class InterviewAnalysis(models.Model):
    question_list = models.ForeignKey(QuestionLists, on_delete=models.CASCADE)  # QuestionLists 참조
    response_1 = models.TextField(blank=True, null=True)
    response_2 = models.TextField(blank=True, null=True)
    response_3 = models.TextField(blank=True, null=True)
    response_4 = models.TextField(blank=True, null=True)
    response_5 = models.TextField(blank=True, null=True)
    response_6 = models.TextField(blank=True, null=True)
    response_7 = models.TextField(blank=True, null=True)
    response_8 = models.TextField(blank=True, null=True)
    response_9 = models.TextField(blank=True, null=True)
    response_10 = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    redundant_expressions = models.TextField(blank=True, null=True)
    inappropriate_terms = models.TextField(blank=True, null=True)


    def __str__(self):
        return f'Responses for {self.question_list.id}'