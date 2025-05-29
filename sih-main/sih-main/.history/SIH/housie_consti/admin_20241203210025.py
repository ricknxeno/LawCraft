from django.contrib import admin
from .models import Article, Case, GameRoom, GameState
from django.utils.html import format_html
from django.contrib.auth.models import User

class ArticleAdmin(admin.ModelAdmin):
    list_display = ('title',)
    search_fields = ('title',)

class CaseAdmin(admin.ModelAdmin):
    list_display = ('article', 'description', 'created_at')
    search_fields = ('description',)
    list_filter = ('article',)

class GameRoomAdmin(admin.ModelAdmin):
    list_display = ('room_id', 'creator', 'created_at', 'is_active', 'game_started')
    list_filter = ('is_active', 'game_started', 'created_at')
    search_fields = ('creator__username', 'room_id')
    readonly_fields = ('room_id', 'created_at', 'display_article_selection', 'display_selected_cards')

    def display_article_selection(self, obj):
        html = '<table><tr><th>Player</th><th>Assigned Articles</th></tr>'
        for player_id, articles in obj.article_selection.items():
            try:
                player = User.objects.get(id=int(player_id))
                articles_list = Article.objects.filter(id__in=articles)
                articles_str = '<br>'.join([f"{art.title}" for art in articles_list])
                html += f'<tr><td>{player.username}</td><td>{articles_str}</td></tr>'
            except Exception as e:
                html += f'<tr><td>Player {player_id}</td><td>Error: {str(e)}</td></tr>'
        html += '</table>'
        return format_html(html)

    def display_selected_cards(self, obj):
        html = '<table><tr><th>Player</th><th>Selected Articles</th></tr>'
        for player_id, selected in obj.selected_cards.items():
            try:
                player = User.objects.get(id=int(player_id))
                selected_list = Article.objects.filter(id__in=selected)
                selected_str = '<br>'.join([f"{art.title}" for art in selected_list])
                html += f'<tr><td>{player.username}</td><td>{selected_str}</td></tr>'
            except Exception as e:
                html += f'<tr><td>Player {player_id}</td><td>Error: {str(e)}</td></tr>'
        html += '</table>'
        return format_html(html)

    display_article_selection.short_description = 'Player Article Assignments'
    display_selected_cards.short_description = 'Player Selected Articles'

class GameStateAdmin(admin.ModelAdmin):
    list_display = ('room', 'current_case_index', 'round_start_time', 'is_active')
    list_filter = ('is_active',)
    readonly_fields = ('round_start_time',)

admin.site.register(Article, ArticleAdmin)
admin.site.register(Case, CaseAdmin)
admin.site.register(GameRoom, GameRoomAdmin)
admin.site.register(GameState, GameStateAdmin)
