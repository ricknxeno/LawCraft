from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import GameRoom, Article, Case, GameState
from .forms import ArticleForm, CaseForm
import qrcode
import qrcode.image
import base64
from io import BytesIO
from django.urls import reverse
from django.contrib.sites.shortcuts import get_current_site
import random
from django.db.models import Q
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.views.decorators.http import require_http_methods
import json

@login_required
def create_room(request):
    """
    Creates a new game room:
    1. Generates unique room ID
    2. Sets creator as first player
    3. Redirects to room detail page
    """
    if request.method == 'POST':
        room = GameRoom.objects.create(creator=request.user)
        room.players.add(request.user)
        return redirect('snake_ladder:room_detail', room_id=room.room_id)
    return render(request, 'create_room.html')

@login_required
def room_detail(request, room_id):
    """
    Shows room joining page with:
    1. Room details and player list
    2. QR code for easy joining
    3. Shareable room link
    """
    room = get_object_or_404(GameRoom, room_id=room_id)
    
    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    room_url = request.build_absolute_uri(reverse('snake_ladder:join_room', args=[room_id]))
    qr.add_data(room_url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    qr_code = b64encode(buffer.getvalue()).decode()
    
    context = {
        'room': room,
        'qr_code': qr_code,
        'room_url': room_url
    }
    return render(request, 'room_detail.html', context)

@login_required
def join_room(request, room_id):
    """
    Handles new player joining:
    1. Adds player to room if not already in
    2. Redirects to room detail page
    3. Triggers immediate update for all clients
    """
    room = get_object_or_404(GameRoom, room_id=room_id)
    
    # Don't allow joining if game has started
    if not room.is_active:
        return redirect('housie_consti:game_board', room_id=room_id)
    
    # Add player if not already in room
    if request.user not in room.players.all():
        room.players.add(request.user)
        room.save()  # Force a save to trigger update
        
        # Return JSON response for AJAX calls
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'Player {request.user.username} joined'
            })
    
    return redirect('housie_consti:room_detail', room_id=room_id)

@login_required
def game_board(request, room_id):
    room = get_object_or_404(GameRoom, room_id=room_id)
    if not room.game_started or request.user not in room.players.all():
        return redirect('housie_consti:room_detail', room_id=room_id)
    return render(request, 'housie_consti/game_board.html', {'room': room})

@login_required
def housie_basic(request, room_id):
    room = get_object_or_404(GameRoom, room_id=room_id)
    
    # Check if this player already has articles assigned
    if not room.article_selection:
        room.article_selection = {}
        room.save()
    
    player_id = str(request.user.id)
    
    if player_id not in room.article_selection:
        # Get all articles
        all_articles = list(Article.objects.all())
        
        # Get articles already assigned to other players
        used_articles = set()
        for player_articles in room.article_selection.values():
            used_articles.update(player_articles)
        
        # Filter out already used articles
        available_articles = [art.id for art in all_articles if art.id not in used_articles]
        
        # Randomly select 15 articles for this player
        if len(available_articles) >= 15:
            selected_articles = random.sample(available_articles, 15)
        else:
            # If not enough unique articles, use all available and fill rest with random articles
            selected_articles = available_articles + random.sample(
                [art.id for art in all_articles if art.id not in available_articles],
                15 - len(available_articles)
            )
        
        # Save the selection for this player
        room.article_selection[player_id] = selected_articles
        room.save()
    
    # Get the player's assigned articles
    player_article_ids = room.article_selection[player_id]
    housie_articles = Article.objects.filter(id__in=player_article_ids)
    
    # Sort articles to match the original selection order
    housie_articles = sorted(housie_articles, key=lambda x: player_article_ids.index(x.id))
    
    context = {
        'room': room,
        'housie_articles': housie_articles,
    }
    return render(request, 'housie_consti/housie_basic.html', context)

@login_required
def manage_content(request):
    articles = Article.objects.all()
    cases = Case.objects.all()
    return render(request, 'housie_consti/manage_content.html', {'articles': articles, 'cases': cases})

@login_required
def manage_articles(request):
    articles = Article.objects.all()
    return render(request, 'housie_consti/manage_articles.html', {'articles': articles})

@login_required
def manage_cases(request):
    cases = Case.objects.all()
    return render(request, 'housie_consti/manage_cases.html', {'cases': cases})

@login_required
def add_article(request):
    if request.method == 'POST':
        form = ArticleForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('housie_consti:manage_content')
    else:
        form = ArticleForm()
    return render(request, 'housie_consti/article_form.html', {'form': form})

@login_required
def edit_article(request, article_id):
    article = get_object_or_404(Article, id=article_id)
    if request.method == 'POST':
        form = ArticleForm(request.POST, instance=article)
        if form.is_valid():
            form.save()
            return redirect('housie_consti:manage_content')
    else:
        form = ArticleForm(instance=article)
    return render(request, 'housie_consti/article_form.html', {'form': form})

@login_required
def delete_article(request, article_id):
    article = get_object_or_404(Article, id=article_id)
    article.delete()
    return redirect('housie_consti:manage_content')

@login_required
def add_case(request):
    if request.method == 'POST':
        form = CaseForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('housie_consti:manage_content')
    else:
        form = CaseForm()
    return render(request, 'housie_consti/case_form.html', {'form': form})

@login_required
def edit_case(request, case_id):
    case = get_object_or_404(Case, id=case_id)
    if request.method == 'POST':
        form = CaseForm(request.POST, instance=case)
        if form.is_valid():
            form.save()
            return redirect('housie_consti:manage_content')
    else:
        form = CaseForm(instance=case)
    return render(request, 'housie_consti/case_form.html', {'form': form})

@login_required
def delete_case(request, case_id):
    case = get_object_or_404(Case, id=case_id)
    case.delete()
    return redirect('housie_consti:manage_content')

@login_required
def get_game_state(request, room_id):
    room = get_object_or_404(GameRoom, room_id=room_id)
    game_state = GameState.objects.get_or_create(room=room)[0]
    
    # Get all cases with complete article information
    all_cases = list(Case.objects.select_related('article').values(
        'id', 
        'title', 
        'year', 
        'description',
        'article__id',        # Add article ID
        'article__title',     # Add article title
    ))
    
    # Calculate time remaining
    elapsed_time = (timezone.now() - game_state.round_start_time).total_seconds()
    time_remaining = max(0, 15 - int(elapsed_time))
    
    current_case = all_cases[game_state.current_case_index]
    
    # If time's up, move to next case
    if time_remaining == 0 and game_state.is_active:
        game_state.current_case_index = (game_state.current_case_index + 1) % len(all_cases)
        game_state.round_start_time = timezone.now()
        game_state.save()
        time_remaining = 15
        current_case = all_cases[game_state.current_case_index]
    
    return JsonResponse({
        'current_case_index': game_state.current_case_index,
        'time_remaining': time_remaining,
        'current_case': current_case,
        'all_cases': all_cases  # Send all cases data
    })

@login_required
def verify_selections(room, selected_indices, player):
    """Verify which selections are correct based on the current case"""
    game_state = GameState.objects.get(room=room)
    current_case = Case.objects.select_related('article').all()[game_state.current_case_index]
    
    correct_indices = set()
    player_id = str(player.id)
    
    if player_id in room.article_selection:
        player_articles = room.article_selection[player_id]
        
        for idx in selected_indices:
            if idx < len(player_articles):
                article_id = player_articles[idx]
                if article_id == current_case.article.id:
                    correct_indices.add(idx)
    
    return correct_indices

@login_required
def check_points(request, room_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=400)
    
    room = get_object_or_404(GameRoom, room_id=room_id)
    selected_cells = request.POST.getlist('selected_cells[]')
    
    with transaction.atomic():
        player_points, created = PlayerPoints.objects.get_or_create(
            room=room,
            player=request.user
        )
        
        # Convert selected_cells to a set of indices
        selected_indices = set(int(cell) for cell in selected_cells)
        correct_selections = verify_selections(room, selected_indices, request.user)
        
        # Rest of the check_points function remains the same...

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def check_achievements(request, room_id):
    room = get_object_or_404(GameRoom, room_id=room_id)
    selected_cells = request.POST.get('selected_cells', '').split(',')
    first_row_complete = request.POST.get('first_row_complete') == 'true'
    
    points_earned = 0
    player_id = str(request.user.id)
    
    print(f"Checking achievements for player {player_id}")  # Debug log
    print(f"Current points: {room.player_points}")  # Debug log
    
    # Check for FIRST_FIVE achievement
    if len(selected_cells) >= 5:
        awarded, points = room.award_points(player_id, 'FIRST_FIVE')
        if awarded:
            points_earned += points
            print(f"Awarded FIRST_FIVE: {points} points")  # Debug log
    
    # Check for FIRST_ROW achievement
    if first_row_complete:
        awarded, points = room.award_points(player_id, 'FIRST_ROW')
        if awarded:
            points_earned += points
            print(f"Awarded FIRST_ROW: {points} points")  # Debug log
    
    print(f"Updated points: {room.player_points}")  # Debug log
    
    return JsonResponse({
        'success': True,
        'points_earned': points_earned,
        'player_name': request.user.username,
        'total_points': room.player_points.get(player_id, 0)
    })

@login_required
@require_http_methods(["GET"])
def get_recent_achievements(request, room_id):
    room = get_object_or_404(GameRoom, room_id=room_id)
    
    return JsonResponse({
        'success': True,
        'player_points': room.player_points,
        'achievements': [
            {
                'player_name': User.objects.get(id=int(player_id)).username,
                'achievement': achievement,
                'points': room.player_points.get(str(player_id), 0)
            }
            for achievement, player_id in room.points_awarded.items()
        ]
    })

@require_http_methods(["GET"])
def get_selected_cards(request, room_id):
    room = get_object_or_404(GameRoom, room_id=room_id)
    player_id = str(request.user.id)
    selected_cards = room.selected_cards.get(player_id, [])
    return JsonResponse({'selected_cards': selected_cards})

@require_http_methods(["POST"])
def mark_card_selected(request, room_id):
    room = get_object_or_404(GameRoom, room_id=room_id)
    data = json.loads(request.body)
    article_id = data.get('article_id')
    
    if article_id:
        room.mark_card_selected(request.user.id, article_id)
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)
