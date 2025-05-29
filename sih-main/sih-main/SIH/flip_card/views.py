from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from dbs.models import SimplifiedArticle
from .models import UserProgress, LevelArticles, PlayerPlatPoints
import json

@login_required
def start_page(request, part=None, type=None):
    """
    Renders the initial start page with video and loads filtered articles in background
    """
    # Get parameters from URL query string if not provided in URL path
    part = part or request.GET.get('part', '5')
    type = type or request.GET.get('type', 'JUD')
    
    # Convert part to integer for database query
    part = int(part)
    
    # Get filtered articles
    articles = SimplifiedArticle.objects.filter(part=part, type=type)
    articles_data = [
        {
            'article_number': article.article_number,
            'title': article.article_title,
            'simplified_content': article.simplified_content
        }
        for article in articles
    ]
    
    return render(request, 'flip_card/start.html', {
        'articles_data': json.dumps(articles_data),
        'current_part': part,
        'current_type': type
    })

@login_required
def levels_page(request):
    """
    Renders the level selection page with user progress
    """
    # Get or create user progress
    progress, created = UserProgress.objects.get_or_create(user=request.user)
    
    # Sync with platform immediately after getting progress
    progress.sync_with_platform()
    
    # Prepare level data
    levels_data = {}
    for level in range(1, 7):  # Assuming 6 levels
        level_str = str(level)
        levels_data[level] = {
            'unlocked': progress.is_level_unlocked(level),
            'completed': level_str in progress.completed_levels,
            'high_score': progress.high_scores.get(level_str, 0),
            'best_time': progress.best_times.get(level_str, None)
        }
    
    return render(request, 'flip_card/levels.html', {'levels_data': levels_data})

@login_required
def filtered_levels_page(request, part, type):
    """
    Renders the level selection page with levels generated from filtered articles
    """
    # Generate levels for this part and type if they don't exist
    total_levels = LevelArticles.generate_levels(part, type)
    
    # Get or create user progress
    progress, created = UserProgress.objects.get_or_create(user=request.user)
    
    # Sync with platform immediately
    progress.sync_with_platform()
    
    # Prepare level data
    levels_data = {}
    for level in range(1, total_levels + 1):
        try:
            level_obj = LevelArticles.objects.get(level=level, part=part, type=type)
            
            levels_data[level] = {
                'unlocked': 'true' if level == 1 or progress.is_level_unlocked(level) else 'false',  # Always unlock level 1
                'completed': 'true' if str(level) in progress.completed_levels else 'false',
                'high_score': progress.high_scores.get(str(level), 0),
                'best_time': progress.best_times.get(str(level), None),
                'article_count': level_obj.articles.count(),
                'part': part,
                'type': type
            }
            print(f"Level {level} data prepared:", levels_data[level])  # Debug print
        except LevelArticles.DoesNotExist:
            print(f"Level {level} not found")  # Debug print
            continue
    
    context = {
        'levels_data': levels_data,  # Remove json.dumps() here
        'current_part': part,
        'current_type': type,
        'type_display': dict(SimplifiedArticle.TYPE_CHOICES)[type]
    }
    
    print("Final levels_data:", levels_data)  # Debug print
    return render(request, 'flip_card/levels.html', context)

@login_required
def flip_card_game(request):
    """
    Renders the main game page with articles for the selected level
    """
    level = int(request.GET.get('level', 1))
    part = int(request.GET.get('part', 5))
    type = request.GET.get('type', 'JUD')
    
    # Check if level is unlocked
    progress = UserProgress.objects.get(user=request.user)
    
    # Sync with platform before checking level
    progress.sync_with_platform()
    
    if not progress.is_level_unlocked(level):
        return redirect('flip_card:levels_page')
    
    try:
        # Get articles for this level
        level_obj = LevelArticles.objects.get(level=level, part=part, type=type)
        articles_data = [
            {
                'article_number': article.article_number,
                'title': article.article_title,
                'simplified_content': article.simplified_content
            }
            for article in level_obj.articles.all()
        ]
        
        # Print debug information
        print(f"Found {len(articles_data)} articles for level {level}")
        for article in articles_data:
            print(f"Article {article['article_number']}: {article['title']}")
        
        context = {
            'articles': json.dumps(articles_data),
            'level': level,
            'part': part,
            'type': type
        }
        
        return render(request, 'flip_card/index.html', context)
    
    except LevelArticles.DoesNotExist:
        print(f"No level found for level={level}, part={part}, type={type}")
        return redirect('flip_card:levels_page')

@login_required
def complete_level(request):
    """
    API endpoint to mark level completion and award points
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        level = data.get('level')
        score = data.get('score')
        time = data.get('time')
        
        # Get user progress and complete level
        progress = UserProgress.objects.get(user=request.user)
        result = progress.complete_level(level, score, time)
        
        # Points are now handled in complete_level method
        return JsonResponse({
            'success': True,
            'points_earned': result['points_earned'],
            'next_level': result['next_level'],
            'total_platform_points': result['total_platform_points'],
            'flipcard_points': result['flipcard_points']
        })
    return JsonResponse({'success': False})

@login_required
def filtered_articles(request, part, type):
    """
    Returns filtered articles based on part and type
    """
    articles = SimplifiedArticle.objects.filter(part=part, type=type)
    articles_data = [
        {
            'article_number': article.article_number,
            'title': article.article_title,
            'simplified_content': article.simplified_content
        }
        for article in articles
    ]
    
    return JsonResponse({
        'success': True,
        'articles': articles_data
    })