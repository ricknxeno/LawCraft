from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from .models import Cell, GameRoom, PlayerPosition, CellHistory, User, PlayerOverallPoints
from plat.models import PlayerPlatPoints
import qrcode
import qrcode.image.svg
from io import BytesIO
from base64 import b64encode
import time
from django.http import JsonResponse
import google.generativeai as genai
import json
import random
from django.db.models import Count, Avg, Sum
from django.db.models import Q
from datetime import datetime
import os
from django.utils.timezone import now
import math

def generate_dice_roll():
    """
    Creates a fair dice roll (1-6) using microsecond timestamp
    Prevents cheating by using server-side generation
    Returns both roll value and timestamp for verification
    """
    timestamp = int(time.time() * 1000000)
    dice_roll = ((timestamp % 6) + 1)  # 1 to 6
    return dice_roll, timestamp

@login_required
def game_board(request, room_id):
    """
    Main game view that handles:
    1. Showing winner page if game is complete
    2. Generating 10x10 snake & ladder board
    3. Managing player positions and turns
    4. Processing dice rolls and player movements
    5. Showing educational content for current cell
    6. Updating game state after each move
    """
    room = get_object_or_404(GameRoom, room_id=room_id)
    
    # If game is over, sync points with platform
    if room.winner:
        try:
            # Get player's platform points
            player_points = PlayerPlatPoints.objects.get(player=request.user)
            # Update snake ladder points from game points
            game_points = room.points.get(str(request.user.id), 0)
            
            print(f"[DEBUG] Syncing game points to platform - User: {request.user.username}, Points: {game_points}")
            
            # Update platform points for snake ladder
            player_points.update_points(game_points, 'SNAKE_LADDER')
            
        except PlayerPlatPoints.DoesNotExist:
            print(f"[DEBUG] No platform points found for user: {request.user.username}")
    
    # If game is just starting
    if not room.current_content_part:  # Check if content type not set yet
        try:
            # Get player's current progress from platform points
            player_points = PlayerPlatPoints.objects.get(player=request.user)
            
            # Check if coming from a specific checkpoint
            checkpoint_part = request.GET.get('checkpoint_part')
            checkpoint_type = request.GET.get('checkpoint_type')
            
            print(f"[DEBUG] Checkpoint parameters received - Part: {checkpoint_part}, Type: {checkpoint_type}")
            
            if checkpoint_part and checkpoint_type and player_points.can_unlock_checkpoint(
                int(checkpoint_part), checkpoint_type
            ):
                print(f"[DEBUG] Loading content from selected checkpoint: Part {checkpoint_part} {checkpoint_type}")
                # Set content type based on selected checkpoint
                room.set_game_content_type(
                    part=int(checkpoint_part),
                    type=checkpoint_type
                )
            else:
                print(f"[DEBUG] Loading content from current progress: Part {player_points.current_part} {player_points.current_type}")
                # Set content type based on player's current progress
                room.set_game_content_type(
                    part=player_points.current_part,
                    type=player_points.current_type
                )
                
        except PlayerPlatPoints.DoesNotExist:
            print(f"[DEBUG] No platform progress found for {request.user.username}, defaulting to Part 5 JUD")
            room.set_game_content_type(part=5, type='JUD')
    
    dice_roll = None  # Initialize dice_roll at the start
    
    if request.user not in room.players.all():
        return redirect('snake_ladder:join_room', room_id=room_id)
    
    if request.method == 'POST' and request.POST.get('roll'):
        if room.current_turn == request.user:
            dice_roll, timestamp = generate_dice_roll()
            player_position = PlayerPosition.objects.get(room=room, player=request.user)
            new_position = player_position.position + dice_roll
            
            # Update position and check for winner
            is_winner = False
            if new_position == 100:
                is_winner = True
                new_position = 100
            elif new_position > 100:
                new_position = player_position.position
            
            # Update position and history
            player_position.position = new_position
            player_position.save()
            
            current_cell = Cell.objects.get(number=new_position)
            CellHistory.objects.create(
                player=request.user,
                room=room,
                cell=current_cell,
                dice_roll=dice_roll
            )
            
            # Update room state if winner
            if is_winner:
                room.winner = request.user
                room.is_active = False
                room.save()
                return JsonResponse({
                    'dice_roll': dice_roll,
                    'new_position': new_position,
                    'timestamp': timestamp,
                    'winner': request.user.username
                })
            
            # Update turn
            player_list = list(room.players.all())
            current_index = player_list.index(request.user)
            next_index = (current_index + 1) % len(player_list)
            room.current_turn = player_list[next_index]
            room.save()
            
            return JsonResponse({
                'dice_roll': dice_roll,
                'new_position': new_position,
                'timestamp': timestamp
            })
    
    # If game is already won, show winner page with statistics
    if room.winner:
        # Calculate game statistics
        total_moves = CellHistory.objects.filter(room=room).count()
        correct_answers = CellHistory.objects.filter(
            room=room, 
            answer_correct=True
        ).count()
        
        # Get time played (in minutes)
        first_move = CellHistory.objects.filter(room=room).order_by('visited_at').first()
        last_move = CellHistory.objects.filter(room=room).order_by('-visited_at').first()
        time_played = "N/A"
        if first_move and last_move:
            minutes = (last_move.visited_at - first_move.visited_at).total_seconds() / 60
            time_played = f"{int(minutes)} minutes"
        
        # Get final positions
        positions = {}
        for player in room.players.all():
            position = PlayerPosition.objects.get(room=room, player=player)
            positions[player.id] = position.position
        
        player_stats = {}
        for player in room.players.all():
            player_moves = CellHistory.objects.filter(room=room, player=player).count()
            player_correct = CellHistory.objects.filter(
                room=room, 
                player=player,
                answer_correct=True
            ).count()
            
            # Get player's first and last move
            player_first_move = CellHistory.objects.filter(room=room, player=player).order_by('visited_at').first()
            player_last_move = CellHistory.objects.filter(room=room, player=player).order_by('-visited_at').first()
            
            player_time = "N/A"
            if player_first_move and player_last_move:
                minutes = (player_last_move.visited_at - player_first_move.visited_at).total_seconds() / 60
                player_time = f"{int(minutes)} minutes"
            
            player_stats[player.id] = {
                'total_moves': player_moves,
                'correct_answers': player_correct,
                'time_played': player_time,
                'accuracy': f"{(player_correct / player_moves * 100):.1f}%" if player_moves > 0 else "0%"
            }
        
        return render(request, 'winner.html', {
            'room': room,
            'winner': room.winner,
            'total_moves': total_moves,
            'correct_answers': correct_answers,
            'time_played': time_played,
            'players': room.players.all(),
            'positions': positions,
            'player_stats': player_stats
        })
    
    # Get cells first
    cells = Cell.objects.all().order_by('number')
    cells_dict = {cell.number: cell for cell in cells}
    
    # Board generation - Updated to start from bottom left
    board = []
    numbers = list(range(1, 101))  # Start from 1 to 100
    for i in range(9, -1, -1):  # Start from bottom row (9) to top row (0)
        row = numbers[i * 10:(i + 1) * 10]
        if i % 2 == 1:  # Alternate rows go right to left
            row = list(reversed(row))
        board.append(row)
    
    # Get player positions
    positions = {}
    for player in room.players.all():
        position, _ = PlayerPosition.objects.get_or_create(
            room=room, 
            player=player,
            defaults={'position': 1}
        )
        positions[player.id] = position.position
    
    # Create visible cells
    visible_cells = {}
    if request.user.id in positions:
        current_position = positions[request.user.id]
        cell = cells_dict.get(current_position)
        if cell and cell.current_content:  # Check for current_content
            current_time = time.time()
            visible_cells[current_position] = {
                'content': cell.current_content.content,  # Get content from current_content
                'topic': cell.current_content.topic if cell.current_content else None,
                'timestamp': current_time,
                'expires': current_time + 30
            }
    
    # Initialize dice_roll as None
    last_dice_roll = None
    
    # Handle dice roll
    if request.method == 'POST' and request.POST.get('roll'):
        if room.current_turn == request.user:
            dice_roll, timestamp = generate_dice_roll()
            player_position = PlayerPosition.objects.get(room=room, player=request.user)
            new_position = player_position.position + dice_roll
            
            # Update position logic
            if new_position == 100:
                room.winner = request.user
                room.is_active = False
                room.save()
                return JsonResponse({'redirect': True, 'winner': room.winner.username})
            elif new_position > 100:
                new_position = player_position.position
            
            # Update position and history
            current_cell = Cell.objects.get(number=new_position)
            player_position.position = new_position
            player_position.save()
            
            CellHistory.objects.create(
                player=request.user,
                room=room,
                cell=current_cell,
                dice_roll=dice_roll
            )
            
            # Update turn
            player_list = list(room.players.all())
            current_index = player_list.index(request.user)
            next_index = (current_index + 1) % len(player_list)
            room.current_turn = player_list[next_index]
            room.save()
            
            # Return JSON response with dice roll
            return JsonResponse({
                'dice_roll': dice_roll,
                'new_position': new_position,
                'timestamp': timestamp
            })
    
    context = {
        'room': room,
        'board': board,
        'cells': cells_dict,
        'players': room.players.all(),
        'current_turn': room.current_turn,
        'positions': positions,
        'visible_cells': visible_cells,
        'dice_roll': dice_roll,
        'last_dice_roll': last_dice_roll,  # Add to context
    }
    
    return render(request, 'game_board.html', context)

@login_required
def create_room(request):
    """Creates a new game room"""
    try:
        # Check if coming from a specific checkpoint
        checkpoint_part = request.GET.get('checkpoint_part')
        checkpoint_type = request.GET.get('checkpoint_type')
        
        # Get player's platform points
        player_points = PlayerPlatPoints.objects.get(player=request.user)
        
        # If checkpoint specified and unlocked, use that
        if checkpoint_part and checkpoint_type and player_points.can_unlock_checkpoint(
            int(checkpoint_part), checkpoint_type
        ):
            content_part = int(checkpoint_part)
            content_type = checkpoint_type
        else:
            # Otherwise use current progress
            content_part = player_points.current_part
            content_type = player_points.current_type
        
        print(f"[DEBUG] Creating room with content: Part {content_part} {content_type}")
        
        # Create new room
        room = GameRoom.objects.create(
            creator=request.user,
            current_content_part=content_part,
            current_content_type=content_type
        )
        room.players.add(request.user)
        
        # Set initial game content
        room.set_game_content_type(
            part=content_part,
            type=content_type
        )
        
        return redirect('snake_ladder:room_detail', room_id=room.room_id)
        
    except PlayerPlatPoints.DoesNotExist:
        # If no progress found, default to Part 5 JUD
        room = GameRoom.objects.create(
            creator=request.user,
            current_content_part=5,
            current_content_type='JUD'
        )
        room.players.add(request.user)
        room.set_game_content_type(part=5, type='JUD')
        return redirect('snake_ladder:room_detail', room_id=room.room_id)

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
        return redirect('snake_ladder:game_board', room_id=room_id)
    
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
    
    return redirect('snake_ladder:room_detail', room_id=room_id)

@login_required
def game_state(request, room_id):
    """
    Real-time game state API that returns:
    1. Current player positions
    2. Whose turn it is
    3. Visible cell contents
    4. Player colors and data
    5. Game over status
    Used for continuous game updates
    """
    try:
        room = get_object_or_404(GameRoom, room_id=room_id)
        room.refresh_from_db()
        
        # Get all player positions
        positions = {
            position.player_id: position.position 
            for position in PlayerPosition.objects.filter(room=room)
        }
        
        # Check for winner
        for player_id, position in positions.items():
            if position >= 100 and not room.winner:
                winner = get_object_or_404(User, id=player_id)
                room.winner = winner
                # Add 40 points for winning
                room.update_points(winner.id, 40)
                
                # Update overall points for all players in the room
                for player in room.players.all():
                    player_points = room.points.get(str(player.id), 0)
                    overall_points, _ = PlayerOverallPoints.objects.get_or_create(player=player)
                    overall_points.total_points += player_points
                    overall_points.save()
                
                room.is_active = False
                room.save()
                
                return JsonResponse({
                    'winner': winner.username,
                    'points': room.points,
                    'redirect_url': reverse('snake_ladder:game_over', args=[room_id])
                })
        
        # Get the latest dice roll with a more precise timestamp
        latest_roll = CellHistory.objects.filter(
            room=room,
            dice_roll__isnull=False
        ).select_related('player').order_by('-visited_at').first()

        # Add dice roll information with roll ID to prevent duplicates
        dice_info = None
        if latest_roll:
            dice_info = {
                'value': latest_roll.dice_roll,
                'timestamp': latest_roll.visited_at.timestamp(),
                'player_name': latest_roll.player.username,
                'player_id': latest_roll.player.id,
                'roll_id': f"{latest_roll.id}_{latest_roll.visited_at.timestamp()}"  # Unique roll ID
            }

        # Check if game is over
        if room.winner:
            return JsonResponse({
                'redirect_url': reverse('snake_ladder:game_board', args=[room_id])
            })
        
        # If no current turn is set, set it to the first player
        if not room.current_turn and room.players.exists():
            room.current_turn = room.players.first()
            room.save()
        
        positions = {}
        visible_cells = {}
        player_colors = room.get_player_color()
        players_data = []
        
        # Get fresh position data
        for player in room.players.all():
            position = PlayerPosition.objects.get(room=room, player=player).position
            positions[player.id] = position
            
            # Show cell content for current user's position
            if player.id == request.user.id:
                cell = Cell.objects.select_related('current_content').filter(number=position).first()
                if cell and cell.current_content:  # Check for current_content
                    force_display = CellHistory.objects.filter(
                        room=room,
                        player=request.user,
                        cell__number=position,
                        answer_correct=False
                    ).exists()
                    
                    visible_cells[position] = {
                        'content': cell.current_content.content,
                        'topic': cell.current_content.topic,
                        'force_display': force_display
                    }
            
            # Add player data including color
            color = player_colors.get(player, ('gray-500', 'Gray'))[0]
            players_data.append({
                'id': player.id,
                'username': player.username,
                'color': color,
                'is_current_turn': player.id == room.current_turn.id if room.current_turn else False
            })

        return JsonResponse({
            'game_over': False,
            'current_turn': room.current_turn.id if room.current_turn else None,
            'current_turn_username': room.current_turn.username if room.current_turn else '',
            'positions': positions,
            'visible_cells': visible_cells,
            'players': players_data,
            'current_user_id': request.user.id,
            'latest_dice': dice_info,
            'points': room.points,  # Add this line
            'timestamp': time.time()
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def home(request):
    return render(request, 'home.html')

def verify_board(request):
    """
    Validates game board setup:
    1. Counts total cells
    2. Identifies special cells (snakes/ladders)
    3. Calculates distribution percentages
    Used for admin verification
    """
    cells = Cell.objects.all().order_by('number')
    snake_ladder_cells = cells.filter(cell_type='SNAKE_LADDER').values_list('number', flat=True)
    return JsonResponse({
        'total_cells': cells.count(),
        'snake_ladder_cells': list(snake_ladder_cells),
        'percentage': (len(snake_ladder_cells) / cells.count()) * 100
    })



@login_required
def generate_mcq(request, room_id):
    """
    Creates MCQ questions when player lands on special cell:
    1. Gets cell's educational content
    2. Uses AI to generate relevant question
    3. Creates 4 options with 1 correct answer
    4. Returns question data in JSON format
    """
    try:
        room = get_object_or_404(GameRoom, room_id=room_id)
        player_position = PlayerPosition.objects.get(room=room, player=request.user)
        current_position = player_position.position

        # Get only the last 10 visited normal cells
        visited_cells = CellHistory.objects.filter(
            room=room,
            player=request.user,
            cell__cell_type='NORMAL'
        ).select_related('cell__current_content').order_by('-visited_at')[:10]

        if not visited_cells:
            # If no cells visited yet, use current cell as fallback
            source_cell = Cell.objects.select_related('current_content').get(number=current_position)
        else:
            # Randomly select one cell from the last 10 visited cells
            source_cell = random.choice(visited_cells).cell

        # Use content from current_content
        content_for_question = source_cell.current_content.content if source_cell.current_content else "Default content"
        topic_for_question = source_cell.current_content.topic if source_cell.current_content else "Constitutional Law"

        # Generate MCQ using the selected cell's content
        genai.configure(api_key='AIzaSyA8GHU0QhwXkgCXEBYnost56YOPmsd2pPs')
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(
            f"""Based on this fact about Indian Constitution:
            {content_for_question}
            Create a multiple choice question testing their knowledge of this specific fact.
            Return only valid JSON in this exact format:
            {{"question": "your question", "options": ["A) option1", "B) option2", "C) option3", "D) option4"], "correct": "A"}}"""
        )
        
        try:
            data = json.loads(response.text)
            if not all(key in data for key in ['question', 'options', 'correct']):
                raise ValueError("Invalid response format")
            
            data['source_cell'] = source_cell.number
            data['topic_category'] = topic_for_question
            return JsonResponse(data)
        except json.JSONDecodeError:
            return JsonResponse({
                "source_cell": source_cell.number,
                "question": "What type of democracy is India?",
                "options": [
                    "A) Parliamentary Democracy",
                    "B) Presidential Democracy",
                    "C) Direct Democracy",
                    "D) Authoritarian Democracy"
                ],
                "correct": "A",
                "topic_category": topic_for_question
            })
    except Exception as e:
        print(f"Error in generate_mcq: {str(e)}")
        return JsonResponse({"error": str(e)})

@login_required
def answer_mcq(request, room_id):
    try:
        data = json.loads(request.body)
        room = get_object_or_404(GameRoom, room_id=room_id)
        player_position = PlayerPosition.objects.get(room=room, player=request.user)
        current_position = player_position.position
        
        # Extract data from request
        is_correct = data.get('correct', False)
        time_taken = data.get('time_taken', 10)
        source_cell = data.get('source_cell')
        
        # Add points for correct answer
        if is_correct:
            room.update_points(request.user.id, 10)  # Add 10 points for correct answer
        
        # Create cell history with source cell
        CellHistory.objects.create(
            player=request.user,
            room=room,
            cell=Cell.objects.get(number=current_position),
            question_text=data.get('question', ''),
            selected_answer=data.get('selected_option', ''),
            correct_answer=data.get('correct_option', ''),
            answer_correct=is_correct,
            time_to_answer=time_taken,
            topic_category=data.get('topic_category', 'Constitutional Law'),
            options=json.dumps(data.get('all_options', [])),
            source_cell=source_cell,
            difficulty_level='MEDIUM',
            visited_at=now(),
            cumulative_score=calculate_score(is_correct, time_taken)
        )
        
        # Calculate movement
        if is_correct:
            # Calculate move amount based on response time
            move_amount = min(
                math.ceil(3 + 20 / (time_taken + 1)),
                12  # MAX_MOVE
            )
            new_position = min(current_position + move_amount, 100)
            
            # Check if new position is a snake/ladder cell
            try:
                current_cell = Cell.objects.get(number=new_position)
                if current_cell.cell_type == 'SNAKE_LADDER':
                    new_position = new_position + 1 if new_position < 100 else new_position - 1
            except Cell.DoesNotExist:
                pass
        else:
            move_amount = source_cell - current_position
            new_position = max(source_cell, 1)
        
        # Update player position
        player_position.position = new_position
        player_position.save()
        
        # Get content for new position
        try:
            new_cell = Cell.objects.get(number=new_position)
            cell_content = new_cell.current_content.content if new_cell.current_content else None
        except Cell.DoesNotExist:
            cell_content = None
        
        return JsonResponse({
            'success': True,
            'move_amount': move_amount,
            'new_position': new_position,
            'cell_content': cell_content,
            'points_earned': 10 if is_correct else 0,
            'total_points': room.points.get(str(request.user.id), 0)  # Include total points
        })
        
    except Exception as e:
        print(f"Error in answer_mcq: {str(e)}")
        return JsonResponse({
            'error': str(e),
            'success': False
        }, status=500)

def generate_topic_title(content):
    """Generate a 2-word topic title for cell content using Gemini"""
    try:
        genai.configure(api_key='AIzaSyA8GHU0QhwXkgCXEBYnost56YOPmsd2pPs')
        model = genai.GenerativeModel('gemini-pro')
        
        prompt = f"""
        Generate a 2-word topic title for this educational content. The title should be specific and descriptive.
        Keep it exactly 2 words, with proper capitalization. Example: "Constitutional Rights" or "Criminal Law"

        Content: {content}
        
        Response format: Just the 2-word title, nothing else.
        """
        
        response = model.generate_content(prompt)
        title = response.text.strip()
        
        # Validate it's 2 words
        if len(title.split()) == 2:
            return title
        return None
    except:
        return None

def prepare_comparative_time_graph(room, current_user):
    """Prepares data for comparing question response times between players"""
    players = room.players.all()
    
    # Predefined colors for better visibility
    color_palette = [
        {'border': 'rgb(59, 130, 246)', 'background': 'rgba(59, 130, 246, 0.1)'},  # Blue
        {'border': 'rgb(16, 185, 129)', 'background': 'rgba(16, 185, 129, 0.1)'},  # Green
        {'border': 'rgb(245, 158, 11)', 'background': 'rgba(245, 158, 11, 0.1)'},  # Yellow
        {'border': 'rgb(239, 68, 68)', 'background': 'rgba(239, 68, 68, 0.1)'},    # Red
        {'border': 'rgb(139, 92, 246)', 'background': 'rgba(139, 92, 246, 0.1)'},  # Purple
    ]
    
    # Get all unique questions answered by any player
    all_questions = CellHistory.objects.filter(
        room=room,
        question_text__isnull=False
    ).values('question_text').distinct()
    
    datasets = []
    for idx, player in enumerate(players):
        color = color_palette[idx % len(color_palette)]
        player_times = []
        for q in all_questions:
            # Get the first attempt for this question by this player
            attempt = CellHistory.objects.filter(
                room=room,
                player=player,
                question_text=q['question_text']
            ).order_by('visited_at').first()
            
            player_times.append(attempt.time_to_answer if attempt else None)
        
        datasets.append({
            'label': f"{player.username}{'(You)' if player == current_user else ''}",
            'data': player_times,
            'borderColor': color['border'],
            'backgroundColor': color['background'],
            'fill': False,
            'tension': 0.4,
            'borderWidth': 2,
            'pointRadius': 4,
            'pointHoverRadius': 6,
            'pointBackgroundColor': color['border'],
            'pointBorderColor': '#fff',
            'pointHoverBackgroundColor': '#fff',
            'pointHoverBorderColor': color['border']
        })
    
    # Get question numbers for labels
    question_numbers = list(range(1, len(all_questions) + 1))
    
    return {
        'labels': [f"Q{i}" for i in question_numbers],
        'datasets': datasets
    }

@login_required
def player_game_report(request, room_id):
    room = get_object_or_404(GameRoom, room_id=room_id)
    history = CellHistory.objects.filter(room=room, player=request.user)
    
    # Get points data correctly
    player_points = room.points.get(str(request.user.id), 0)
    overall_points_obj = PlayerOverallPoints.objects.get_or_create(player=request.user)[0]
    
    # Get all visited cells (both normal and snake/ladder)
    visited_cells = history.select_related('cell').order_by('visited_at')
    
    # Get unique cells visited by the player
    unique_visited_cells = []
    seen_cells = set()
    
    for visit in visited_cells:
        if visit.cell and visit.cell.number not in seen_cells:
            unique_visited_cells.append({
                'number': visit.cell.number,
                'content': visit.cell.current_content.content if visit.cell.current_content else None,
                'type': visit.cell.cell_type
            })
            seen_cells.add(visit.cell.number)

    # Calculate statistics
    attempted_questions = history.exclude(question_text__isnull=True)
    total_attempted = attempted_questions.count()
    correct_answers = attempted_questions.filter(answer_correct=True).count()
    
    def extract_source_cell(options_str):
        try:
            options = json.loads(options_str) if options_str else []
            if options and isinstance(options, list) and len(options) > 0:
                first_option = options[0]
                if 'Cell ' in first_option:
                    return first_option.split('Cell ')[1].split(':')[0]
        except (json.JSONDecodeError, IndexError, AttributeError):
            pass
        return None
     # Get points data
    player_points = room.points.get(str(request.user.id), 0)
    overall_points = PlayerOverallPoints.objects.get_or_create(player=request.user)[0].total_points
    context = {
        'statistics': {
            'total_questions': total_attempted,
            'correct_answers': correct_answers,
            'avg_time': attempted_questions.aggregate(Avg('time_to_answer'))['time_to_answer__avg'] or 0,
            'total_score': player_points,
            'overall_score': overall_points_obj.total_points,  # Use the object's total_points
            'accuracy': (correct_answers / total_attempted * 100) if total_attempted > 0 else 0,
            'cells_visited': len(unique_visited_cells)
        },
        'visited_cells': unique_visited_cells,
        'time_data': json.dumps(prepare_time_graph_data(attempted_questions)),
        'comparative_time_data': json.dumps(prepare_comparative_time_graph(room, request.user)),
        'question_history': [{
            'question_text': q['question_text'],
            'selected_answer': q['selected_answer'],
            'correct_answer': q['correct_answer'],
            'time_to_answer': q['time_to_answer'],
            'topic_category': q['topic_category'],
            'answer_correct': q['answer_correct'],
            'visited_at': q['visited_at'],
            'options': json.loads(q['options']) if q['options'] else [],
            'current_cell': q['cell__number'],
            'source_cell': q['source_cell']
        } for q in attempted_questions.values(
            'question_text',
            'selected_answer',
            'correct_answer',
            'time_to_answer',
            'topic_category',
            'answer_correct',
            'visited_at',
            'options',
            'cell__number',
            'source_cell'
        ).order_by('-visited_at')],
        'ai_analysis': generate_ai_analysis({
            'total_questions': total_attempted,
            'correct_answers': correct_answers,
            'avg_time': attempted_questions.aggregate(Avg('time_to_answer'))['time_to_answer__avg'] or 0,
            'total_cells_visited': visited_cells.count(),
            'normal_cells_visited': visited_cells.filter(cell__cell_type='NORMAL').count(),
            'total_points': player_points,
            'overall_points': overall_points_obj.total_points  # Use the object's total_points
        })
    }
    
    return render(request, 'game_report.html', context)

def calculate_score(correct, time_taken):
    """Calculate score based on correctness and time taken"""
    base_score = 100 if correct else 0
    time_bonus = max(0, 50 - time_taken) if correct else 0
    return base_score + time_bonus

def get_sample_questions(topic):
    """Get sample questions for topics that need improvement"""
    # Implement question generation or retrieval logic
    return [
        f"Sample question 1 for {topic}",
        f"Sample question 2 for {topic}",
        f"Sample question 3 for {topic}"
    ]

def prepare_time_graph_data(history):
    """Prepare time series data for the response time graph"""
    return {
        'labels': [entry.visited_at.strftime('%H:%M:%S') for entry in history],
        'datasets': [{
            'label': 'Response Time',
            'data': [entry.time_to_answer for entry in history],
            'borderColor': 'rgb(75, 192, 192)',
            'tension': 0.1
        }]
    }

def prepare_topic_graph_data(topic_stats):
    """Prepares data for the radar chart showing topic performance"""
    if not topic_stats:
        return {
            'labels': ['No Data'],
            'datasets': [{
                'label': 'Performance',
                'data': [0],
                'fill': True,
                'backgroundColor': 'rgba(75, 192, 192, 0.2)',
                'borderColor': 'rgb(75, 192, 192)',
            }]
        }
    
    return {
        'labels': [topic.get('name', 'Uncategorized') for topic in topic_stats],
        'datasets': [
            {
                'label': 'Topic Accuracy',
                'data': [topic.get('accuracy', 0) for topic in topic_stats],
                'fill': True,
                'backgroundColor': 'rgba(75, 192, 192, 0.2)',
                'borderColor': 'rgb(75, 192, 192)',
            },
            {
                'label': 'Response Speed',
                'data': [max(0, 100 - (topic.get('avg_time', 0) * 5)) for topic in topic_stats],
                'fill': True,
                'backgroundColor': 'rgba(255, 99, 132, 0.2)',
                'borderColor': 'rgb(255, 99, 132)',
            }
        ]
    }

def generate_ai_analysis(player_data):
    """Generate AI analysis of player performance using Gemini"""
    try:
        genai.configure(api_key='AIzaSyA8GHU0QhwXkgCXEBYnost56YOPmsd2pPs')
        model = genai.GenerativeModel('gemini-pro')
        
        # Format the topics list for the prompt
        topics_list = "\n".join([f"- {topic}" for topic in player_data.get('topics_covered', [])])
        
        prompt = f"""
        Analyze this player's game performance:

        Statistics:
        - Total Questions Attempted: {player_data['total_questions']}
        - Correct Answers: {player_data['correct_answers']}
        - Average Response Time: {player_data['avg_time']:.1f} seconds
        - Accuracy: {(player_data['correct_answers'] / player_data['total_questions'] * 100) if player_data['total_questions'] > 0 else 0:.1f}%

        Topics Covered:
        {topics_list}

        Please provide analysis in this format:

        1. Brief Summary of Overall Performance
        2. Time Management Analysis
        3. Specific Recommendations for Improvement

        Keep the analysis concise and focused on these aspects.
        """
        
        response = model.generate_content(prompt)
        analysis_text = response.text
        
        # Split the analysis into sections
        sections = analysis_text.split('\n\n')
        
        return {
            'summary': sections[0] if sections else "Analysis not available",
            'detailed_analysis': {
                'overall_performance': sections[0] if len(sections) > 0 else "",
                'time_analysis': sections[1] if len(sections) > 1 else "",
                'recommendations': sections[2] if len(sections) > 2 else ""
            },
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
    except Exception as e:
        print(f"AI Analysis Error: {str(e)}")
        return {
            'error': str(e),
            'summary': "Unable to generate AI analysis",
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

def get_topic_analysis(history):
    """
    Analyzes performance by topic from cell history
    Returns list of topic stats with accuracy and timing metrics
    """
    topic_stats = []
    
    # Get unique topics
    topics = history.values('topic_category').distinct()
    
    for topic in topics:
        topic_category = topic['topic_category']
        if not topic_category:  # Skip if topic is None
            continue
            
        # Get questions for this topic
        topic_questions = history.filter(topic_category=topic_category)
        total = topic_questions.count()
        
        if total > 0:  # Only include topics with questions
            correct = topic_questions.filter(answer_correct=True).count()
            avg_time = topic_questions.aggregate(Avg('time_to_answer'))['time_to_answer__avg'] or 0
            
            topic_stats.append({
                'name': topic_category,
                'total': total,
                'correct': correct,
                'accuracy': (correct / total * 100),
                'avg_time': avg_time,
                'questions': list(topic_questions.values(
                    'question_text',
                    'selected_answer',
                    'correct_answer',
                    'answer_correct',
                    'time_to_answer'
                ))
            })
    
    # Sort by accuracy (highest first)
    topic_stats.sort(key=lambda x: x['accuracy'], reverse=True)
    
    return topic_stats

def format_topic_analysis(topics):
    """Formats topic analysis for AI prompt"""
    if not topics:
        return "No topic data available"
        
    result = []
    for topic in topics:
        result.append(
            f"Topic: {topic['name']}\n"
            f"- Accuracy: {topic['accuracy']:.1f}%\n"
            f"- Questions Attempted: {topic['total']}\n"
            f"- Average Response Time: {topic['avg_time']:.1f}s"
        )
    return "\n\n".join(result)

def format_question_history(questions):
    """Formats question history for AI prompt"""
    if not questions:
        return "No question history available"
        
    result = []
    for q in questions:
        result.append(
            f"Question: {q['question_text']}\n"
            f"Selected: {q['selected_answer']}\n"
            f"Correct: {q['correct_answer']}\n"
            f"Time: {q['time_to_answer']}s\n"
            f"Topic: {q['topic_category']}\n"
            f"Result: {'Correct' if q['answer_correct'] else 'Incorrect'}"
        )
    return "\n\n".join(result)

@login_required
def room_state(request, room_id):
    """API endpoint to get current room state"""
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
        
    try:
        room = get_object_or_404(GameRoom, room_id=room_id)
        room.refresh_from_db()
        
        players_data = [{
            'username': player.username,
            'is_creator': player == room.creator
        } for player in room.players.all()]
        
        return JsonResponse({
            'players': players_data,
            'game_started': not room.is_active,
            'timestamp': time.time()
        })
    except Exception as e:
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
            
        # Initialize game
        room.current_turn = room.creator
        room.is_active = False
        room.save()
        
        # Set initial positions
        for player in room.players.all():
            PlayerPosition.objects.get_or_create(
                room=room,
                player=player,
                defaults={'position': 1}
            )
            
        return JsonResponse({
            'success': True,
            'redirect_url': reverse('snake_ladder:game_board', args=[room_id])
        })
        
    except Exception as e:
        print(f"Error starting game: {str(e)}")  # Server-side logging
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def join_room(request, room_id):
    """
    Handles new player joining:
    1. Adds player to room if not already in
    2. Redirects to room detail page
    """
    room = get_object_or_404(GameRoom, room_id=room_id)
    
    # Don't allow joining if game has started
    if not room.is_active:
        return redirect('snake_ladder:game_board', room_id=room_id)
    
    if request.user not in room.players.all():
        room.players.add(request.user)
    
    return redirect('snake_ladder:room_detail', room_id=room_id)

@login_required
def snake_ladder_intro(request):
    """
    View to show the Snake & Ladder intro/create room page
    """
    return render(request, 'create_room.html')
