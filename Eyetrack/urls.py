from django.urls import path
from .views import start_gaze_tracking_view, stop_gaze_tracking_view

urlpatterns = [
    path('start/<int:user_id>/<int:interview_id>/', start_gaze_tracking_view, name='start_gaze_tracking'),
    path('stop/<int:user_id>/<int:interview_id>/', stop_gaze_tracking_view, name='stop-gaze-tracking'),
]



# start/{user_id}/{interview_id}
#stop/<int:user_id>/<int:interview_id>/