# urls.py

from django.conf import settings
from django.conf.urls.static import static
from django.urls import path
from .views import start_gaze_tracking_view, stop_gaze_tracking_view, VideoUploadView

urlpatterns = [
    path('start/<int:user_id>/<int:interviewId>/<int:question_id>/', start_gaze_tracking_view, name='start_gaze_tracking'),
    path('stop/<int:user_id>/<int:interviewId>/<int:question_id>/', stop_gaze_tracking_view, name='stop-gaze-tracking'),

    # 프론트로부터 받아오는 Video 업로드 url
    path('upload/', VideoUploadView.as_view(), name='file-upload'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
