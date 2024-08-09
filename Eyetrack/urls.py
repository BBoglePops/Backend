# urls.py

from django.conf import settings
from django.conf.urls.static import static
from django.urls import path
from .views import start_gaze_tracking_view, stop_gaze_tracking_view, generate_signed_url
urlpatterns = [
    path('start/<int:user_id>/<int:interview_id>/', start_gaze_tracking_view, name='start_gaze_tracking'),
    path('stop/<int:user_id>/<int:interview_id>/', stop_gaze_tracking_view, name='stop-gaze-tracking'),
    # path('upload/', VideoUploadView.as_view(), name='file-upload'),
    path('generate-signed-url/<int:user_id>/<int:interview_id>/', generate_signed_url, name='generate-signed-url'),
    # path('get-session-status/<int:user_id>/<int:interview_id>', get_session_status, name='get_session_status')
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
