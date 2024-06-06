from django.shortcuts import render
from django.http import JsonResponse
from .main import GazeTrackingSession
from .models import GazeTrackingResult
import cv2
import pandas as pd
import base64
import io
from PIL import Image
import numpy as np
import os
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status
from .serializers import VideoSerializer
from django.conf import settings

permission_classes = [IsAuthenticated]
gaze_sessions = {}

def start_gaze_tracking_view(request, user_id, interview_id):
    key = f"{user_id}_{interview_id}"
    if key not in gaze_sessions:
        gaze_sessions[key] = GazeTrackingSession()
    
    gaze_session = gaze_sessions[key]
    video_path = gaze_session.video_path
    gaze_session.start_eye_tracking(video_path)
    return JsonResponse({"message": "Gaze tracking started"}, status=200)

def apply_gradient(center, radius, color, image, text=None):
    overlay = image.copy()
    cv2.circle(overlay, center, radius, color, -1)
    cv2.addWeighted(overlay, 0.5, image, 0.5, 0, image)
    if text is not None:
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 30
        font_color = (255, 255, 255)
        thickness = 10
        text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
        text_x = center[0] - text_size[0] // 2
        text_y = center[1] + text_size[1] // 2
        cv2.putText(image, text, (text_x, text_y), font, font_scale, font_color, thickness)

def assign_colors_and_numbers(section_counts):
    colors = [
        (38, 38, 255), (59, 94, 255), (55, 134, 255),
        (51, 173, 255), (26, 210, 255), (0, 255, 255)
    ]
    sorted_sections = sorted(section_counts.items(), key=lambda item: item[1], reverse=True)
    color_map = {}
    number_map = {}
    for i, (section, _) in enumerate(sorted_sections):
        color_map[section] = colors[i % len(colors)]
        number_map[section] = str(i + 1)
    return color_map, number_map

def get_feedback(section_counts):
    max_section = max(section_counts, key=section_counts.get)
    feedback = ""
    if max_section in ['B', 'E']:
        feedback = "면접관을 잘 응시하고 있습니다!"
    elif max_section in ['A', 'D']:
        feedback = "면접관의 왼쪽을 많이 응시합니다. 면접관을 응시하려고 노력해보세요."
    elif max_section in ['C', 'F']:
        feedback = "면접관의 오른쪽을 많이 응시합니다. 면접관을 응시하려고 노력해보세요."
    return feedback

def draw_heatmap(image, section_counts):
    if image is not None:
        height, width, _ = image.shape
        section_centers = {
            "A": (int(width / 6), int(height / 4)),
            "B": (int(width / 2), int(height / 4)),
            "C": (int(5 * width / 6), int(height / 4)),
            "D": (int(width / 6), int(3 * height / 4)),
            "E": (int(width / 2), int(3 * height / 4)),
            "F": (int(5 * width / 6), int(3 * height / 4))
        }

        color_map, number_map = assign_colors_and_numbers(section_counts)
        for section, count in section_counts.items():
            if count > 0 and section in section_centers:
                center = section_centers[section]
                color = color_map[section]
                number = number_map[section]
                radius = 700
                apply_gradient(center, radius, color, image, number)

def stop_gaze_tracking_view(request, user_id, interview_id):
    key = f"{user_id}_{interview_id}"
    if key not in gaze_sessions:
        return JsonResponse({"message": "Session not found"}, status=404)

    csv_filename = gaze_sessions[key].stop_eye_tracking()
    section_data = pd.read_csv(csv_filename)
    section_counts = dict(zip(section_data["Section"], section_data["Count"]))

    image_path = "C:/KJE/IME_graduation/Backend-main/Backend-main/Eyetrack/0518/image.png"
    original_image = cv2.imread(image_path)

    if original_image is None:
        return JsonResponse({"message": "Image not found"}, status=404)

    heatmap_image = original_image.copy()
    draw_heatmap(heatmap_image, section_counts)

    _, buffer = cv2.imencode('.png', heatmap_image)
    encoded_image_string = base64.b64encode(buffer).decode('utf-8')

    feedback = get_feedback(section_counts)

    gaze_tracking_result = GazeTrackingResult.objects.create(
        user_id=user_id,
        interview_id=interview_id,
        encoded_image=encoded_image_string,
        feedback=feedback
    )
    
    video_path = gaze_sessions[key].video_path
    if os.path.exists(video_path):
        os.remove(video_path)

    del gaze_sessions[key]

    return JsonResponse({
        "message": "Gaze tracking stopped",
        "image_data": gaze_tracking_result.encoded_image,
        "feedback": feedback
    }, status=200)

class VideoUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        file_serializer = VideoSerializer(data=request.data)
        if file_serializer.is_valid():
            video = file_serializer.save()
            user_id = request.data.get('user_id')
            interview_id = request.data.get('interview_id')
            video_path = video.file.path

            key = f"{user_id}_{interview_id}"
            gaze_sessions[key] = GazeTrackingSession()
            gaze_sessions[key].video_path = video_path

            return JsonResponse({"message": "Video uploaded successfully"}, status=201)
        else:
            return JsonResponse(file_serializer.errors, status=400)
