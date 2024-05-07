from rest_framework import serializers
from .models import InterviewAnalysis

class InterviewResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterviewAnalysis
        fields = '__all__'
