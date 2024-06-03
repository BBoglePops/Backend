from rest_framework import serializers
from .models import Video

class GazeStatusSerializer(serializers.Serializer):
    status = serializers.CharField(max_length=200)


# 프론트에서 받아오는 Video 처리
class VideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Video
        fields = ['id', 'file', 'uploaded_at']

