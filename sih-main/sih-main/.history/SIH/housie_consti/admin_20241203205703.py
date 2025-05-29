from django.contrib import admin
from .models import Article, Case, GameRoom, GameState

class ArticleAdmin(admin.ModelAdmin):
    list_display = ('title',)
    search_fields = ('title',)

class CaseAdmin(admin.ModelAdmin):
    list_display = ('article', 'description', 'created_at')
    search_fields = ('description',)
    list_filter = ('article',)

class GameRoomAdmin(admin.ModelAdmin):
    list_display = ('room_id', 'creator', 'created_at', 'is_active', 'game_started', 'display_article_selection', 'display_selected_cards')
    list_filter = ('is_active', 'game_started', 'created_at')
    search_fields = ('creator__username', 'room_id')
    readonly_fields = ('room_id', 'created_at')

    def display_article_selection(self, obj):
        return obj.article_selection

    def display_selected_cards(self, obj):
        return obj.selected_cards

    display_article_selection.short_description = 'Article Selection'
    display_selected_cards.short_description = 'Selected Cards'

class GameStateAdmin(admin.ModelAdmin):
    list_display = ('room', 'current_case_index', 'round_start_time', 'is_active')
    list_filter = ('is_active',)
    readonly_fields = ('round_start_time',)

admin.site.register(Article, ArticleAdmin)
admin.site.register(Case, CaseAdmin)
admin.site.register(GameRoom, GameRoomAdmin)
admin.site.register(GameState, GameStateAdmin)
