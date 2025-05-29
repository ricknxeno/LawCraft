from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('', views.chat, name='chat'),
    path('get_response/', views.get_response, name='get_response'),
    path('text-to-speech/', views.text_to_speech, name='text_to_speech'),
] 