from django.urls import path
from .views import start_gaze_tracking_view, stop_gaze_tracking_view, VideoUploadView

urlpatterns = [
    path('start/<int:user_id>/<int:interview_id>/<int:question_id>/', start_gaze_tracking_view, name='start_gaze_tracking'),
    path('stop/<int:user_id>/<int:interview_id>/<int:question_id>/', stop_gaze_tracking_view, name='stop-gaze-tracking'),

    # 프론트로부터 받아오는 Video 업로드 url
    path('upload/', VideoUploadView.as_view(), name='file-upload'),
]



# start/{user_id}/{interview_id}
#stop/<int:user_id>/<int:interview_id>/