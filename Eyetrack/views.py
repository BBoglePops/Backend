from django.conf import settings
from django.http import JsonResponse
from google.cloud import storage
from google.cloud.storage.blob import Blob
from google.cloud.exceptions import GoogleCloudError
import cv2
import os
import logging
import pandas as pd
import base64
import datetime
from .models import *

logger = logging.getLogger(__name__)
gaze_sessions = {}

def convert_to_gs_uri(url):
    """
    Convert a Google Cloud Storage URL to a gsutil URI.
    """
    if url.startswith('https://storage.googleapis.com/'):
        return url.replace('https://storage.googleapis.com/', 'gs://')
    elif url.startswith('https://storage.cloud.google.com/'):
        return url.replace('https://storage.cloud.google.com/', 'gs://')
    else:
        raise ValueError("Unsupported URL format")

def download_video_from_gcs(video_url, local_path):
    """
    Download a video from Google Cloud Storage to a local path.
    """
    try:
        gs_uri = convert_to_gs_uri(video_url)
        bucket_name, blob_name = gs_uri[5:].split('/', 1)  # Remove 'gs://'
        logger.info(f"Bucket: {bucket_name}, Blob: {blob_name}")
        
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.download_to_filename(local_path)
        logger.info("Download completed")
    except Exception as e:
        logger.error(f"Error downloading video from GCS: {str(e)}")
        raise

def generate_signed_url(bucket_name, blob_name, expiration=86400):
    """
    Generate a signed URL for a Google Cloud Storage blob.
    """
    client = storage.Client()
    try:
        bucket = client.bucket(bucket_name)
        blob = Blob(blob_name, bucket)
        url = blob.generate_signed_url(
            expiration=datetime.timedelta(seconds=expiration),
            method='PUT'
        )
        logger.info(f"Signed URL generated for {blob_name}: {url}")
        return url
    except GoogleCloudError as e:
        logger.error(f"Failed to generate signed URL: {e}")
        raise

def start_gaze_tracking_view(request, user_id, interview_id):
    key = f"{user_id}_{interview_id}"
    if key not in gaze_sessions:
        logger.warning(f"Session not found for key: {key}")
        return JsonResponse({"message": "Session not found", "log_message": f"Session not found for key: {key}"}, status=404)

    session_info = gaze_sessions.get(key)
    if not session_info:
        logger.warning(f"Session data missing for key: {key}")
        return JsonResponse({"message": "Session data is missing"}, status=404)

    video_url = session_info.get('video_url')
    if not video_url:
        logger.warning(f"Video URL not found for session key: {key}")
        return JsonResponse({"message": "Video URL not found"}, status=404)

    gaze_session = session_info.get('session')
    local_video_path = os.path.join(settings.MEDIA_ROOT, f"{user_id}_{interview_id}.webm")

    try:
        download_video_from_gcs(video_url, local_video_path)
        gaze_session.start_eye_tracking(local_video_path)
    except Exception as e:
        logger.error(f"Error processing video for session key {key}: {str(e)}")
        return JsonResponse({"message": f"Error processing video: {str(e)}"}, status=500)

    try:
        cap = cv2.VideoCapture(local_video_path)
        if not cap.isOpened():
            logger.error(f"Failed to open video file: {local_video_path}")
            return JsonResponse({"message": "Cannot open video file"}, status=500)
        while cap.isOpened():
            ret, frame = cap.read()
            if ret:
                cv2.imshow('Gaze Tracking Video', frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            else:
                break
        cap.release()
        cv2.destroyAllWindows()
    except Exception as e:
        logger.error(f"Error displaying video: {str(e)}")
        return JsonResponse({"message": f"Error displaying video: {str(e)}"}, status=500)

    logger.info(f"Gaze tracking started for session key: {key}")
    return JsonResponse({"message": "Gaze tracking started"}, status=200)

def stop_gaze_tracking_view(request, user_id, interview_id):
    key = f"{user_id}_{interview_id}"
    if key not in gaze_sessions:
        logger.warning(f"Session not found for key: {key}")
        return JsonResponse({"message": "Session not found", "status": "error"}, status=404)

    session_info = gaze_sessions[key]
    gaze_session = session_info['session']
    try:
        csv_filename = gaze_session.stop_eye_tracking()
        section_data = pd.read_csv(csv_filename)
        section_counts = dict(zip(section_data["Section"], section_data["Count"]))
        
        image_path = os.path.join(settings.BASE_DIR, "Eyetrack", "0518", "image.png")
        original_image = cv2.imread(image_path)
        if original_image is None:
            logger.error(f"Image not found at {image_path}")
            return JsonResponse({"message": "Image not found", "status": "error"}, status=404)
        
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

        local_video_path = os.path.join(settings.MEDIA_ROOT, f"{user_id}_{interview_id}.webm")
        if os.path.exists(local_video_path):
            os.remove(local_video_path)
        
        del gaze_sessions[key]
        logger.info(f"Gaze tracking stopped and session deleted for key: {key}")
        return JsonResponse({
            "message": "Gaze tracking stopped",
            "image_data": gaze_tracking_result.encoded_image,
            "feedback": feedback,
            "status": "success"
        }, status=200)
    
    except Exception as e:
        logger.error(f"Error stopping gaze tracking for session key {key}: {str(e)}")
        return JsonResponse({"message": f"Error stopping gaze tracking: {str(e)}"}, status=500)

def get_feedback(section_counts):
    max_section = max(section_counts, key=section_counts.get)
    feedback = "Interviewer와의 눈맞춤이 잘 되고 있습니다."
    if max_section == 'A':
        feedback = "왼쪽에 너무 집중하고 있습니다. 면접관을 더 많이 봐주세요."
    elif max_section == 'C':
        feedback = "오른쪽에 너무 집중하고 있습니다. 면접관을 더 많이 봐주세요."
    return feedback

def apply_gradient(center, radius, color, image, text=None):
    overlay = image.copy()
    cv2.circle(overlay, center, radius, color, -1)
    cv2.addWeighted(overlay, 0.5, image, 0.5, 0, image)
    if text:
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1.0
        font_color = (255, 255, 255)
        thickness = 2
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

def draw_heatmap(image, section_counts):
    height, width, _ = image.shape
    section_centers = {
        "A": (int(width / 6), int(height / 2)),
        "B": (int(width / 2), int(height / 2)),
        "C": (int(5 * width / 6), int(height / 2))
    }
    color_map, number_map = assign_colors_and_numbers(section_counts)
    for section, count in section_counts.items():
        if count > 0 and section in section_centers:
            center = section_centers[section]
            color = color_map[section]
            number = number_map[section]
            radius = int(width / 12)
            apply_gradient(center, radius, color, image, number)





# from django.shortcuts import render
# from django.http import JsonResponse
# from .main import GazeTrackingSession
# from .models import GazeTrackingResult
# import cv2
# import pandas as pd
# import base64
# import io
# from PIL import Image
# import numpy as np
# import os
# import logging
# from rest_framework.permissions import IsAuthenticated
# from rest_framework.views import APIView
# from rest_framework.parsers import MultiPartParser, FormParser
# from rest_framework.response import Response
# from rest_framework import status
# from .serializers import VideoSerializer, SignedURLSerializer, GazeStatusSerializer
# from django.conf import settings
# from google.cloud import storage
# from google.cloud.storage.blob import Blob
# import datetime
# from rest_framework.parsers import JSONParser


# logger = logging.getLogger(__name__)
# permission_classes = [IsAuthenticated]
# gaze_sessions = {}


# # GCS 스토리지 Signed Url 생성
# def generate_signed_url(bucket_name, blob_name, expiration=3600):
#     """주어진 버킷과 Blob에 대한 signed URL을 생성하며, 특정 시간 후에 만료됩니다."""
#     # Google Cloud Storage 클라이언트 초기화
#     client = storage.Client()
#     # 지정된 버킷 가져오기
#     bucket = client.get_bucket(bucket_name)
#     # 파일에 대한 Blob 객체 생성
#     blob = Blob(blob_name, bucket)
#     # PUT 메소드와 content type을 포함하여 signed URL 생성
#     url = blob.generate_signed_url(
#         expiration=datetime.timedelta(seconds=expiration),
#         method='PUT',
        
#     )
#     return url

# # Eyetrack/views.py 수정
# class SignedURLView(APIView):
#     permission_classes = [IsAuthenticated]
#     parser_classes = [MultiPartParser, FormParser, JSONParser]

#     def post(self, request, user_id, interview_id, *args, **kwargs):
#         serializer = SignedURLSerializer(data=request.data)
#         if serializer.is_valid():
#             bucket_name = settings.GS_BUCKET_NAME
#             blob_name = f"videos/{user_id}/{interview_id}/input.webm"  # question_id 제거
#             signed_url = generate_signed_url(bucket_name, blob_name)
#             return JsonResponse({"signed_url": signed_url}, status=200)
#         else:
#             return JsonResponse(serializer.errors, status=400)

# def download_video_from_gcs(video_url, local_path):
#     try:
#         if video_url.startswith('https://storage.googleapis.com/'):
#             video_url = video_url.replace('https://storage.googleapis.com/', 'gs://')
#         elif not video_url.startswith('gs://'):
#             raise ValueError("Invalid video URL format")

#         # 버킷 이름과 객체 이름을 추출
#         gs_prefix = 'gs://'
#         bucket_name, blob_name = video_url[len(gs_prefix):].split('/', 1)

#         client = storage.Client()
#         bucket = client.bucket(bucket_name)
#         blob = bucket.blob(blob_name)
#         blob.download_to_filename(local_path)
#     except Exception as e:
#         logger.error(f"Error downloading video from GCS: {str(e)}")
#         raise

# def start_gaze_tracking_view(request, user_id, interview_id, question_id):
#     key = f"{user_id}_{interview_id}_{question_id}"
#     if key not in gaze_sessions:
#         return JsonResponse({"message": "Session not found","log_message": f"Session not found for key: {key}"}, status=404)
    
#     gaze_session = gaze_sessions[key]
#     video_url = gaze_session.video_url
#     if not video_url:
#         return JsonResponse({"message": "Video URL not found"}, status=404)
    
#     local_video_path = os.path.join(settings.MEDIA_ROOT, 'input.webm')

#     try:
#         download_video_from_gcs(video_url, local_video_path)
#     except Exception as e:
#         # GCS에서 파일 다운로드 중 오류 발생 시 500 에러 반환
#         return JsonResponse({"message": f"Error downloading video: {str(e)}"}, status=500)
    
#     try:
#         gaze_session.start_eye_tracking(local_video_path)
#     except Exception as e:
#         return JsonResponse({"message": f"Error processing video: {str(e)}"}, status=500)
    
#     try:
#         # Display the video frames using OpenCV
#         cap = cv2.VideoCapture(local_video_path)
#         if not cap.isOpened():
#             return JsonResponse({"message": "Cannot open video file"}, status=500)
#         while cap.isOpened():
#             ret, frame = cap.read()
#             if ret:
#                 cv2.imshow('Gaze Tracking Video', frame)
#                 if cv2.waitKey(1) & 0xFF == ord('q'):
#                     break
#             else:
#                 break
#         cap.release()
#         cv2.destroyAllWindows()
#     except Exception as e:
#         return JsonResponse({"message": f"Error displaying video: {str(e)}"}, status=500)

#     return JsonResponse({"message": "Gaze tracking started"}, status=200)

# def apply_gradient(center, radius, color, image, text=None):
#     overlay = image.copy()
#     cv2.circle(overlay, center, radius, color, -1)
#     cv2.addWeighted(overlay, 0.5, image, 0.5, 0, image)
#     if text is not None:
#         font = cv2.FONT_HERSHEY_SIMPLEX
#         font_scale = 30
#         font_color = (255, 255, 255)
#         thickness = 10
#         text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
#         text_x = center[0] - text_size[0] // 2
#         text_y = center[1] + text_size[1] // 2
#         cv2.putText(image, text, (text_x, text_y), font, font_scale, font_color, thickness)

# def assign_colors_and_numbers(section_counts):
#     colors = [
#         (38, 38, 255), (59, 94, 255), (55, 134, 255),
#         (51, 173, 255), (26, 210, 255), (0, 255, 255)
#     ]
#     sorted_sections = sorted(section_counts.items(), key=lambda item: item[1], reverse=True)
#     color_map = {}
#     number_map = {}
#     for i, (section, _) in enumerate(sorted_sections):
#         color_map[section] = colors[i % len(colors)]
#         number_map[section] = str(i + 1)
#     return color_map, number_map

# def get_feedback(section_counts):
#     max_section = max(section_counts, key=section_counts.get)
#     feedback = ""
#     if max_section in ['B', 'E']:
#         feedback = "면접관을 잘 응시하고 있습니다!"
#     elif max_section in ['A', 'D']:
#         feedback = "면접관의 왼쪽을 많이 응시합니다. 면접관을 응시하려고 노력해보세요."
#     elif max_section in ['C', 'F']:
#         feedback = "면접관의 오른쪽을 많이 응시합니다. 면접관을 응시하려고 노력해보세요."
#     return feedback

# def draw_heatmap(image, section_counts):
#     if image is not None:
#         height, width, _ = image.shape
#         section_centers = {
#             "A": (int(width / 6), int(height / 4)),
#             "B": (int(width / 2), int(height / 4)),
#             "C": (int(5 * width / 6), int(height / 4)),
#             "D": (int(width / 6), int(3 * height / 4)),
#             "E": (int(width / 2), int(3 * height / 4)),
#             "F": (int(5 * width / 6), int(3 * height / 4))
#         }

#         color_map, number_map = assign_colors_and_numbers(section_counts)
#         for section, count in section_counts.items():
#             if count > 0 and section in section_centers:
#                 center = section_centers[section]
#                 color = color_map[section]
#                 number = number_map[section]
#                 radius = 700
#                 apply_gradient(center, radius, color, image, number)

# def stop_gaze_tracking_view(request, user_id, interview_id, question_id):
#     key = f"{user_id}_{interview_id}_{question_id}"
#     if key not in gaze_sessions:
#         return JsonResponse({"message": "Session not found"}, status=404)

#     csv_filename = gaze_sessions[key].stop_eye_tracking()
#     section_data = pd.read_csv(csv_filename)
#     section_counts = dict(zip(section_data["Section"], section_data["Count"]))

#     image_path = os.path.join(settings.BASE_DIR, "Eyetrack", "0518", "image.png")
#     original_image = cv2.imread(image_path)

#     if original_image is None:
#         return JsonResponse({"message": "Image not found"}, status=404)

#     heatmap_image = original_image.copy()
#     draw_heatmap(heatmap_image, section_counts)

#     _, buffer = cv2.imencode('.png', heatmap_image)
#     encoded_image_string = base64.b64encode(buffer).decode('utf-8')

#     feedback = get_feedback(section_counts)

#     gaze_tracking_result = GazeTrackingResult.objects.create(
#         user_id=user_id,
#         interview_id=interview_id,
#         encoded_image=encoded_image_string,
#         feedback=feedback
#     )
    
#     local_video_path = os.path.join(settings.MEDIA_ROOT, 'input.webm')
#     if os.path.exists(local_video_path):
#         os.remove(local_video_path)

#     del gaze_sessions[key]

#     return JsonResponse({
#         "message": "Gaze tracking stopped",
#         "image_data": gaze_tracking_result.encoded_image,
#         "feedback": feedback
#     }, status=200)

# def upload_video_to_gcs(file_obj, bucket_name, destination_blob_name):
#     client = storage.Client()
#     bucket = client.bucket(bucket_name)
#     blob = bucket.blob(destination_blob_name)

#     # 파일 업로드
#     blob.upload_from_file(file_obj, content_type='video/webm')
#     #blob.patch()

#     return blob.public_url

# class VideoUploadView(APIView):
#     permission_classes = [IsAuthenticated]
#     parser_classes = (MultiPartParser, FormParser)

#     def post(self, request, *args, **kwargs):
#         file_serializer = VideoSerializer(data=request.data)
#         if file_serializer.is_valid():
#             video = file_serializer.save()
#             user_id = request.data.get('user_id')
#             interview_id = request.data.get('interviewId')
#             question_id = request.data.get('question_id')

#             # GCS에 파일 업로드
#             file_obj = video.file.open('rb') 
#             bucket_name = settings.GS_BUCKET_NAME
#             destination_blob_name = f"videos/{user_id}/{interview_id}/{question_id}/input.webm"
#             try:
#                 video_url = upload_video_to_gcs(file_obj, bucket_name, destination_blob_name)
#                 file_obj.close()
#             except Exception as e:
#                 logger.error(f"Error uploading video to GS: {str(e)}")
#                 return JsonResponse({"message": f"Error uploading video: {str(e)}"}, status=500)

#             key = f"{user_id}_{interview_id}_{question_id}"
#             gaze_sessions[key] = GazeTrackingSession()
#             gaze_sessions[key].video_url = video_url

#             # Log the session addition
#             logger.info(f"Session added for key: {key}")

#             return JsonResponse({"message": "Video uploaded successfully", "log_message": f"Session added for key: {key}"}, status=201)
#         else:
#             return JsonResponse(file_serializer.errors, status=400)
