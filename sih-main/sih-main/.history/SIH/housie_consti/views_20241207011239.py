from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import GameRoom, Article, Case, GameState, PlayerPoints
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
from base64 import b64encode
import time
import google.generativeai as genai
from django.utils.html import mark_safe
from datetime import timedelta

def calculate_time_remaining(start_time, round_duration=30):
    """
    Calculate remaining time in seconds for the current round
    Args:
        start_time: datetime object when the round started
        round_duration: duration of round in seconds (default 30)
    Returns:
        int: remaining seconds, or 0 if time is up
    """
    if not start_time:
        return 0
        
    elapsed = timezone.now() - start_time
    remaining = round_duration - elapsed.total_seconds()
    
    return max(0, int(remaining))

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
        return redirect('housie_consti:room_detail', room_id=room.room_id)
    return render(request, 'housie_consti/create_room.html')

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
    room_url = request.build_absolute_uri(reverse('housie_consti:join_room', args=[room_id]))
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
    return render(request, 'housie_consti/room_detail.html', context)

@login_required
def join_room(request, room_id):
    room = get_object_or_404(GameRoom, room_id=room_id)
    
    if not room.is_active:
        return redirect('housie_consti:game_board', room_id=room_id)
    
    # Add player if not already in room
    if request.user not in room.players.all():
        room.players.add(request.user)
        # Ensure articles are assigned when player joins
        room.ensure_player_articles(request.user.id)
        room.save()
        
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
    
    if not room.game_started:
        return redirect('housie_consti:room_detail', room_id=room_id)
    
    # Ensure player has articles assigned
    room.ensure_player_articles(request.user.id)
    
    # Get player's articles with full article objects
    player_article_ids = room.article_selection.get(str(request.user.id), [])
    housie_articles = Article.objects.filter(id__in=player_article_ids)
    
    # Get initial case data
    current_case = room.get_current_case()
    
    context = {
        'room': room,
        'housie_articles': housie_articles,
        'current_case': current_case
    }
    
    print("Articles loaded:", len(housie_articles))  # Debug log
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
def edit_case(request, pk):
    case = get_object_or_404(Case, pk=pk)
    if request.method == 'POST':
        form = CaseForm(request.POST, instance=case)
        if form.is_valid():
            case = form.save()
            return redirect('case_detail', pk=case.pk)
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
    """API endpoint to get current game state including timer"""
    room = get_object_or_404(GameRoom, room_id=room_id)
    game_state = get_object_or_404(GameState, room=room)
    
    # Get current case
    current_case = room.get_current_case()
    
    # Get time remaining
    time_remaining = game_state.get_time_remaining()
    
    # Get player points
    player_points = {}
    for player in room.players.all():
        points_obj = PlayerPoints.objects.filter(room=room, player=player).first()
        player_points[player.username] = points_obj.points if points_obj else 0
    
    # Check for game completion
    game_completion = room.selected_cards.get('game_completion', {})
    
    return JsonResponse({
        'current_case': current_case,
        'time_remaining': time_remaining,
        'player_points': player_points,
        'game_completion': game_completion,
        'case_changed': game_state.current_case_index != room.current_case_index
    })

@login_required
def verify_selections(room, selected_indices, player):
    """Verify which selections are correct based on the current case"""
    game_state = GameState.objects.get(room=room)
    current_case = Case.objects.prefetch_related('articles').all()[game_state.current_case_index]
    
    correct_indices = set()
    player_id = str(player.id)
    
    if player_id in room.article_selection:
        player_articles = room.article_selection[player_id]
        correct_article_ids = set(current_case.articles.values_list('id', flat=True))
        
        for idx in selected_indices:
            if idx < len(player_articles):
                article_id = player_articles[idx]
                if article_id not in correct_article_ids:
                    # Record wrong selection
                    room.record_wrong_selection(player.id, article_id, current_case.id)
                else:
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
    pass  # Remove this entire function

@login_required
@require_http_methods(["GET"])
def get_recent_achievements(request, room_id):
    pass  # Remove this entire function

@login_required
def check_achievement(request, room_id):
    pass  # Remove this entire function

@login_required
def check_full_housie(request, room_id):
    pass  # Remove this entire function

@require_http_methods(["GET"])
def get_selected_cards(request, room_id):
    room = get_object_or_404(GameRoom, room_id=room_id)
    player_id = str(request.user.id)
    selected_cards = room.selected_cards.get(player_id, [])
    return JsonResponse({'selected_cards': selected_cards})

@require_http_methods(["POST"])
@login_required
def mark_card_selected(request, room_id):
    try:
        room = get_object_or_404(GameRoom, room_id=room_id)
        data = json.loads(request.body)
        article_id = data.get('article_id')
        player_id = str(request.user.id)
        
        if not article_id:
            return JsonResponse({
                'success': False,
                'error': 'Missing article_id'
            }, status=400)

        # Initialize selected_cards if it doesn't exist
        if not room.selected_cards:
            room.selected_cards = {}
            
        # Initialize player's selected cards if not exists
        if player_id not in room.selected_cards:
            room.selected_cards[player_id] = []
            
        # Add the article_id if not already selected
        if article_id not in room.selected_cards[player_id]:
            room.selected_cards[player_id].append(article_id)
            room.save()
            
            # Check for achievements after marking card
            achievements = []
            selected_count = len(room.selected_cards[player_id])
            
            # Initialize points if not already done
            if not room.player_points:
                room.player_points = {}
            if not room.points_awarded:
                room.points_awarded = {}

            # Check for first 5 cards achievement
            if selected_count >= 5 and 'first_five' not in room.points_awarded:
                room.points_awarded['first_five'] = player_id
                room.player_points[player_id] = room.player_points.get(player_id, 0) + 15
                achievements.append({
                    'type': 'first_five',
                    'points': 15
                })

            # Check for full housie (all 15 cards)
            if selected_count == 15 and 'full_housie' not in room.points_awarded:
                room.points_awarded['full_housie'] = player_id
                room.player_points[player_id] = room.player_points.get(player_id, 0) + 45
                achievements.append({
                    'type': 'full_housie',
                    'points': 45
                })
                room.full_housie_achieved = True

            room.save()

            return JsonResponse({
                'success': True,
                'selected_cards': room.selected_cards[player_id],
                'achievements': achievements,
                'player_points': room.player_points.get(player_id, 0)
            })
            
        return JsonResponse({
            'success': True,
            'selected_cards': room.selected_cards[player_id],
            'message': 'Card was already selected'
        })
        
    except Exception as e:
        print(f"Error in mark_card_selected: {str(e)}")  # For debugging
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
def room_state(request, room_id):
    """API endpoint to get current room state"""
    try:
        room = get_object_or_404(GameRoom, room_id=room_id)
        
        # Get current timestamp for client-side comparison
        current_time = time.time()
        
        # Get list of players with their status
        players = [{
            'username': player.username,
            'is_creator': player == room.creator
        } for player in room.players.all()]
        
        # Check if game is ready to start (e.g., minimum players joined)
        game_ready = room.players.count() >= 2  # Adjust minimum player count as needed
        
        response_data = {
            'players': players,
            'game_started': room.game_started,
            'game_ready': game_ready,
            'timestamp': current_time
        }
        
        # If game has started, include redirect URL
        if room.game_started:
            response_data['redirect_url'] = reverse('housie_consti:housie_basic', args=[room_id])
        
        return JsonResponse(response_data)
        
    except Exception as e:
        print(f"Error in room_state: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def start_game(request, room_id):
    """API endpoint to start the game"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
        
    try:
        room = get_object_or_404(GameRoom, room_id=room_id)
        
        if request.user != room.creator:
            return JsonResponse({'error': 'Only creator can start game'}, status=403)
            
        if not room.is_active:
            return JsonResponse({'error': 'Game already started'}, status=400)
            
        # Check if room has exactly 2 players
        if room.players.count() != 2:
            return JsonResponse({'error': 'Need exactly 2 players to start'}, status=400)
            
        # Initialize game with case order and start time
        room.start_game()  # This sets up case_order, round_start_time, and game_started
        room.is_active = False
        room.save()
        
        # Initialize game state if needed
        GameState.objects.get_or_create(room=room)
            
        return JsonResponse({
            'success': True,
            'redirect_url': reverse('housie_consti:housie_basic', args=[room_id])
        })
        
    except Exception as e:
        print(f"Error starting game: {str(e)}")  # Debug logging
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def check_selected_cards(request, room_id):
    room = get_object_or_404(GameRoom, room_id=room_id)
    player = request.user
    player_id = str(player.id)

    # Get the selected cards for the current player
    selected_cards = room.selected_cards.get(player_id, [])
    num_selected = len(selected_cards)

    # Initialize points if not already done
    if not room.player_points:
        room.player_points = {}
    if not room.points_awarded:
        room.points_awarded = {'first_five': False, 'full_housie': False}

    achievements = []

    # Check for first 5 cards achievement
    if num_selected >= 5 and not room.points_awarded.get('first_five'):
        room.player_points[player_id] = room.player_points.get(player_id, 0) + 15
        room.points_awarded['first_five'] = True
        achievements.append({
            'type': 'first_five',
            'player': player.username,
            'points': 15
        })

    # Check for full housie (all 15 cards)
    if num_selected == 15 and not room.points_awarded.get('full_housie'):
        room.player_points[player_id] = room.player_points.get(player_id, 0) + 45
        room.points_awarded['full_housie'] = True
        achievements.append({
            'type': 'full_housie',
            'player': player.username,
            'points': 45
        })

    room.save()

    return JsonResponse({
        'success': True,
        'achievements': achievements,
        'player_points': room.player_points.get(player_id, 0)
    })

@login_required
def leaderboard(request, room_id):
    try:
        room = get_object_or_404(GameRoom, room_id=room_id)
        players_data = []
        
        # Get all players in the room
        for player in room.players.all():
            player_id = str(player.id)
            
            # Get selected cards and times for this player
            selected_cards = room.selected_cards.get(player_id, [])
            selection_times = room.selection_times.get(player_id, {})
            
            # Calculate stats
            correct_answers = len(selected_cards)
            points = correct_answers * 10  # 10 points per correct answer
            
            # Calculate average response time
            times = [float(t) for t in selection_times.values() if t]
            avg_time = sum(times) / len(times) if times else 0
            
            # Add player data
            players_data.append({
                'username': player.username,  # Make sure username is included
                'points': points,
                'correct_answers': correct_answers,
                'avg_response_time': f"{avg_time:.1f}"
            })
        
        # Sort by points in descending order
        players_data = sorted(players_data, key=lambda x: x['points'], reverse=True)
        
        context = {
            'room': room,
            'players_data': players_data,
            'total_players': room.players.count(),
            'game_duration': (timezone.now() - room.created_at).total_seconds() / 60,
            'total_articles': 15
        }
        
        return render(request, 'housie_consti/leaderboard.html', context)
        
    except Exception as e:
        print(f"Error in leaderboard view: {e}")  # For debugging
        context = {
            'room': room,
            'players_data': [],
            'total_players': 0,
            'game_duration': 0,
            'total_articles': 15,
            'error_message': str(e)
        }
        return render(request, 'housie_consti/leaderboard.html', context)

@login_required
def handle_wrong_selection(request, room_id):
    """API endpoint to record wrong selections"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
        
    try:
        data = json.loads(request.body)
        article_id = data.get('article_id')
        case_id = data.get('case_id')
        
        room = get_object_or_404(GameRoom, room_id=room_id)
        room.record_wrong_selection(request.user.id, article_id, case_id)
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def record_selection_time(request, room_id):
    """API endpoint to record selection times"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
        
    try:
        data = json.loads(request.body)
        article_id = data.get('article_id')
        case_id = data.get('case_id')
        time_taken = data.get('time_taken')
        
        room = get_object_or_404(GameRoom, room_id=room_id)
        room.record_selection_time(request.user.id, article_id, case_id, time_taken)
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def check_selection(request, room_id):
    """API endpoint to check if a selection is correct"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
        
    try:
        data = json.loads(request.body)
        article_id = data.get('article_id')
        case_id = data.get('case_id')
        
        if not article_id or not case_id:
            return JsonResponse({
                'error': 'Missing article_id or case_id'
            }, status=400)

        room = get_object_or_404(GameRoom, room_id=room_id)
        case = get_object_or_404(Case, id=case_id)
        
        # Check if the selected article is among the case's correct articles
        is_correct = case.articles.filter(id=article_id).exists()
        
        # Record wrong selection if incorrect
        if not is_correct:
            room.record_wrong_selection(request.user.id, article_id, case_id)
        
        return JsonResponse({
            'correct': is_correct,
            'success': True
        })
        
    except Exception as e:
        print(f"Error in check_selection: {str(e)}")
        return JsonResponse({
            'error': str(e),
            'success': False
        }, status=500)

@login_required
def game_analysis(request, room_id):
    room = get_object_or_404(GameRoom, room_id=room_id)
    
    # Configure Gemini
    genai.configure(api_key='AIzaSyBIZIZoovhNdzrqzh4u71OOfFMiBRi52tk')
    model = genai.GenerativeModel('gemini-pro')
    
    # Initialize analysis data
    analysis = {
        'players': {},
        'room_stats': {
            'total_players': room.players.count(),
            'game_duration': (timezone.now() - room.created_at).total_seconds() / 60,
        }
    }
    
    # Analyze each player's performance
    for player in room.players.all():
        player_id = str(player.id)
        wrong_selections = room.wrong_selections.get(player_id, [])
        
        # Generate AI reports for wrong selections
        ai_reports = []
        for wrong_selection in wrong_selections:
            try:
                case = Case.objects.get(id=wrong_selection['case_id'])
                selected_article = Article.objects.get(id=wrong_selection['article_id'])
                correct_articles = case.articles.all()
                
                # Generate AI analysis
                correct_articles_text = ", ".join([art.title for art in correct_articles])
                prompt = f"""
                Analyze this incorrect match in a Supreme Court case study:
                Case: {case.title}
                Selected Article: {selected_article.title}
                Correct Articles: {correct_articles_text}
                
                Please provide:
                1. Brief case description (5 lines)
                2. Why the selected article was incorrect
                3. Why any of the correct articles would have been the right choice
                """
                
                response = model.generate_content(prompt)
                if response.text:
                    ai_reports.append({
                        'case_title': case.title,
                        'selected_article': selected_article.title,
                        'correct_articles': correct_articles_text,
                        'analysis': mark_safe(response.text.replace('\n', '<br>'))
                    })
            except Exception as e:
                print(f"Error generating report: {str(e)}")
                continue
        
        # Add analysis data without points/achievements
        analysis['players'][player.username] = {
            'total_selections': len(room.selected_cards.get(player_id, [])),
            'wrong_selections': len(wrong_selections),
            'accuracy': round(((len(room.selected_cards.get(player_id, [])) - len(wrong_selections)) / 
                            max(len(room.selected_cards.get(player_id, [])), 1)) * 100, 2),
            'avg_response_time': round(
                sum(float(t.get('time_taken', 0)) for t in room.selection_times.get(player_id, [])) / 
                max(len(room.selection_times.get(player_id, [])), 1), 2),
            'ai_reports': ai_reports
        }

    return render(request, 'housie_consti/game_analysis.html', {
        'room': room,
        'analysis': analysis
    })

@login_required
@require_POST
def select_article(request, room_id):
    try:
        data = json.loads(request.body)
        room = get_object_or_404(GameRoom, room_id=room_id)
        article_id = data.get('article_id')
        case_id = data.get('case_id')
        time_taken = data.get('time_taken', 15)
        
        # Get current case
        current_case = room.get_current_case()
        if not current_case:
            return JsonResponse({'success': False, 'error': 'No active case'})
            
        # Check if player already made a selection for this case
        player_id = str(request.user.id)
        current_case_selections = [
            selection for selection in room.selection_times.get(player_id, [])
            if selection.get('case_id') == current_case['id']
        ]
        
        if current_case_selections:
            return JsonResponse({'success': False, 'error': 'Already selected for this case'})
        
        # Mark the selection
        room.mark_card_selected(player_id, article_id)
        
        # Check if selection is correct
        is_correct = False
        if current_case and 'id' in current_case:
            case = Case.objects.get(id=current_case['id'])
            is_correct = case.articles.filter(id=article_id).exists()
            
            if not is_correct:
                room.record_wrong_selection(player_id, article_id, case.id)
        
        # Record selection time
        room.record_selection_time(player_id, article_id, case_id, time_taken)
        
        return JsonResponse({'success': is_correct})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def update_points(request, room_id):
    """Update points for a player"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=400)
    
    room = get_object_or_404(GameRoom, room_id=room_id)
    player = request.user
    
    try:
        # Get the player's selected cards
        player_id = str(player.id)
        selected_cards = room.selected_cards.get(player_id, [])
        num_selected = len(selected_cards)
        
        # Get or create player points
        player_points, created = PlayerPoints.objects.get_or_create(
            room=room,
            player=player,
            defaults={'points': 0}
        )
        
        # Update points based on number of selections
        if num_selected >= 5 and player_points.points == 0:  # First 5 cards
            player_points.points += 10
            player_points.save()
            
        return JsonResponse({
            'success': True,
            'points': player_points.points,
            'message': f'Points updated for {player.username}'
        })
        
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)

@login_required
@require_POST
def advance_case(request, room_id):
    try:
        room = get_object_or_404(GameRoom, room_id=room_id)
        game_state = get_object_or_404(GameState, room=room)
        
        if game_state.is_active and not room.is_game_completed():
            # Advance case and reset timer
            case_changed = game_state.advance_case()
            
            if case_changed:
                # Reset selection state for all players
                for player in room.players.all():
                    player_id = str(player.id)
                    if player_id in room.selected_cards:
                        room.selected_cards[player_id] = [
                            card_id for card_id in room.selected_cards[player_id] 
                            if card_id in room.selected_cards.get('permanent', [])
                        ]
                room.save()
                
                return JsonResponse({
                    'success': True,
                    'current_case': game_state.get_current_case(),
                    'time_remaining': 15,
                    'case_changed': True
                })
        
        return JsonResponse({
            'success': False,
            'error': 'Game completed or inactive'
        })
        
    except Exception as e:
        print(f"Error in advance_case: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
