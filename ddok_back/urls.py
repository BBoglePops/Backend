from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('interview_questions/', include('QuestionList.urls')),
    path('users/', include('Users.urls')),
]
