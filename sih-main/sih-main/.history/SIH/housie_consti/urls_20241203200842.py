from django.urls import path
from . import views

app_name = 'housie_consti'

urlpatterns = [
    path('', views.create_room, name='create_room'),
    path('join/<uuid:room_id>/', views.join_room, name='join_room'),
    path('room/<uuid:room_id>/', views.room_detail, name='room_detail'),
    path('game/<uuid:room_id>/', views.game_board, name='game_board'),
    path('housie-basic/<uuid:room_id>/', views.housie_basic, name='housie_basic'),
    path('game-state/<uuid:room_id>/', views.get_game_state, name='game_state'),
    path('manage/', views.manage_content, name='manage_content'),
    path('manage/articles/', views.manage_articles, name='manage_articles'),
    path('manage/cases/', views.manage_cases, name='manage_cases'),
    path('add/article/', views.add_article, name='add_article'),
    path('edit/article/<int:article_id>/', views.edit_article, name='edit_article'),
    path('delete/article/<int:article_id>/', views.delete_article, name='delete_article'),
    path('add/case/', views.add_case, name='add_case'),
    path('edit/case/<int:case_id>/', views.edit_case, name='edit_case'),
    path('delete/case/<int:case_id>/', views.delete_case, name='delete_case'),
    path('check-achievements/<uuid:room_id>/', views.check_achievements, name='check_achievements'),
    path('get-recent-achievements/<uuid:room_id>/', views.get_recent_achievements, name='get_recent_achievements'),
    path('get-selected-cards/<uuid:room_id>/', views.get_selected_cards, name='get_selected_cards'),
    path('mark-card-selected/<uuid:room_id>/', views.mark_card_selected, name='mark_card_selected'),
]
