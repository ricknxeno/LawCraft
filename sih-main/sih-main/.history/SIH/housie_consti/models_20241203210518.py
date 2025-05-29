from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required

class GameRoom(models.Model):
    room_id = models.UUIDField(default=uuid.uuid4, unique=True)
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_housie_rooms')
    players = models.ManyToManyField(User, related_name='joined_housie_rooms')
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    game_started = models.BooleanField(default=False)
    case_order = models.JSONField(null=True, blank=True)
    article_selection = models.JSONField(null=True, blank=True, default=dict)
    # points_awarded = models.JSONField(default=dict)
    # player_points = models.JSONField(default=dict)
    
    points_awarded = models.JSONField(null=True, blank=True, default=dict)
    player_points = models.JSONField(null=True, blank=True, default=dict)
    selected_cards = models.JSONField(default=dict)
    
    def __str__(self):
        return f"Housie Room by {self.creator.username}"

    def award_points(self, player_id, achievement_type):
        ACHIEVEMENTS = {
            'FIRST_FIVE': {
                'points': 15,
                'name': 'First to get 5 matches'
            },
            'FIRST_ROW': {
                'points': 25,
                'name': 'First to complete a row'
            }
        }
        
        player_id = str(player_id)  # Convert to string for JSON compatibility
        
        # Initialize points if not exists
        if player_id not in self.player_points:
            self.player_points[player_id] = 0
            
        # Check if achievement already awarded
        if achievement_type not in self.points_awarded:
            # Award points
            self.points_awarded[achievement_type] = player_id
            self.player_points[player_id] += ACHIEVEMENTS[achievement_type]['points']
            self.save()
            
            # Return both success status and current points
            return True, self.player_points[player_id]
        
        return False, self.player_points.get(player_id, 0)

    def assign_articles_to_player(self, player_id, articles):
        """Assigns a list of articles to a player."""
        player_id = str(player_id)
        self.article_selection[player_id] = articles
        self.save()

    def mark_card_selected(self, player_id, article_id):
        """Marks an article as selected by a player."""
        player_id = str(player_id)
        if player_id not in self.selected_cards:
            self.selected_cards[player_id] = []
        
        if article_id not in self.selected_cards[player_id]:
            self.selected_cards[player_id].append(article_id)
            self.save()

class Article(models.Model):
    title = models.CharField(max_length=255, default='')
    content = models.TextField(default='')

    def __str__(self):
        return self.title

class Case(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='cases')
    title = models.CharField(max_length=255, default='')
    articles_involved = models.CharField(max_length=100, default='')
    description = models.TextField(default='')
    year = models.IntegerField(default=2024)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.title} ({self.year})"

    class Meta:
        ordering = ['-year']
        
class GameState(models.Model):
    room = models.OneToOneField(GameRoom, on_delete=models.CASCADE)
    current_case_index = models.IntegerField(default=0)
    round_start_time = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Game State for Room {self.room.room_id}"

@login_required
def get_game_state(request, room_id):
    room = get_object_or_404(GameRoom, room_id=room_id)
    game_state = GameState.objects.get_or_create(room=room)[0]
    
    # Calculate exact time remaining
    elapsed_time = (timezone.now() - game_state.round_start_time).total_seconds()
    time_remaining = max(0, 15 - int(elapsed_time))
    
    # If time's up, move to next case
    if time_remaining == 0 and game_state.is_active:
        game_state.current_case_index = (game_state.current_case_index + 1) % Case.objects.count()
        game_state.round_start_time = timezone.now()
        game_state.save()
        time_remaining = 15
    
    return JsonResponse({
        'current_case_index': game_state.current_case_index,
        'time_remaining': time_remaining,
        'server_time': timezone.now().timestamp()
    })