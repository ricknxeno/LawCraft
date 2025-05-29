from django.urls import path
from . import views

app_name = 'flip_card'

urlpatterns = [
    path('', views.start_page, name='start_page'),
    path('levels/', views.levels_page, name='levels_page'),
    path('levels/<int:part>/<str:type>/', views.filtered_levels_page, name='filtered_levels_page'),
    path('game/', views.flip_card_game, name='flip_card_game'),
    path('complete-level/', views.complete_level, name='complete_level'),
    path('start/<int:part>/<str:type>/', views.start_page, name='filtered_start_page'),
]
