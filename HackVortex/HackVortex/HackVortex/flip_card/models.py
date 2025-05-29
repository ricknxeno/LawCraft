from django.db import models
from django.contrib.auth.models import User
from plat.models import PlayerPlatPoints
from dbs.models import SimplifiedArticle
import random

class UserProgress(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    completed_levels = models.JSONField(default=dict)  # Stores level completion data
    high_scores = models.JSONField(default=dict)      # Stores high scores for each level
    best_times = models.JSONField(default=dict)       # Stores best times for each level
    total_points = models.IntegerField(default=0)     # Add total points field

    def __str__(self):
        return f"Progress for {self.user.username}"

    def is_level_unlocked(self, level_number):
        if level_number == 1:
            return True
        return str(level_number - 1) in self.completed_levels

    def calculate_flipcard_points(self):
        """Calculate total flipcard points from all completed levels"""
        total = 0
        print(f"Calculating points for {self.user.username}:")
        print(f"Completed levels: {self.completed_levels}")
        print(f"High scores: {self.high_scores}")
        print(f"Best times: {self.best_times}")
        
        for level_str, completed in self.completed_levels.items():
            if completed:
                level_score = self.high_scores.get(level_str, 0)
                level_time = self.best_times.get(level_str, 0)
                time_bonus = max(0, 100 - level_time)
                level_points = level_score + time_bonus
                total += level_points
                print(f"Level {level_str}:")
                print(f"  Score: {level_score}")
                print(f"  Time: {level_time}")
                print(f"  Time bonus: {time_bonus}")
                print(f"  Level points: {level_points}")
        
        print(f"Total points calculated: {total}")
        return total

    def sync_with_platform(self):
        """Sync points with platform points"""
        try:
            platform_points = PlayerPlatPoints.objects.get(player=self.user)
            # Update platform's flipcard points with our total points
            platform_points.update_points(self.total_points, 'FLIPCARD')
            # Update platform's game stats
            platform_points.flipcard_games = len(self.completed_levels)
            platform_points.flipcard_wins = 1 if '6' in self.completed_levels else 0
            platform_points.save()
            return True
        except Exception as e:
            print(f"Error syncing with platform: {str(e)}")
            return False

    def save(self, *args, **kwargs):
        # First calculate total points if needed
        if not self.total_points:
            self.total_points = self.calculate_flipcard_points()
            
        # Save the model
        super().save(*args, **kwargs)
        
        # Always sync with platform after save
        self.sync_with_platform()

    def complete_level(self, level_number, score, time):
        level_str = str(level_number)
        print(f"\nCompleting level {level_number} for {self.user.username}:")
        print(f"Score: {score}, Time: {time}")
        
        is_first_completion = level_str not in self.completed_levels
        print(f"Is first completion: {is_first_completion}")
        
        old_high_score = self.high_scores.get(level_str, 0)
        old_best_time = self.best_times.get(level_str, float('inf'))
        print(f"Old high score: {old_high_score}")
        print(f"Old best time: {old_best_time}")
        
        # Update completion status
        self.completed_levels[level_str] = True
        
        # Calculate points based on score and time
        time_bonus = max(0, 100 - time)  # Bonus points for completing quickly
        level_points = score + time_bonus
        
        # Track if we need to update platform points
        points_changed = False
        
        # Update high score if better
        if score > old_high_score:
            self.high_scores[level_str] = score
            points_changed = True
            
        # Update best time if better
        if time < old_best_time:
            self.best_times[level_str] = time
            points_changed = True
        
        # Update points if it's first completion or if points changed
        if is_first_completion or points_changed:
            # Calculate total points
            self.total_points = self.calculate_flipcard_points()
            self.save()
            
            # Sync with platform
            self.sync_with_platform()
        
        # Get updated platform points for response
        platform = PlayerPlatPoints.objects.get(player=self.user)
        
        return {
            'points_earned': level_points if is_first_completion else 0,
            'next_level': level_number + 1 if level_number < 6 else None,
            'total_platform_points': platform.total_points,
            'flipcard_points': platform.flipcard_points
        }

class LevelArticles(models.Model):
    level = models.IntegerField()
    part = models.IntegerField()
    type = models.CharField(max_length=4)
    articles = models.ManyToManyField(SimplifiedArticle)
    
    @classmethod
    def generate_levels(cls, part, type):
        """
        Generates 6 levels with 5 random articles each for given part and type
        """
        # Clear existing levels for this part and type
        cls.objects.filter(part=part, type=type).delete()
        
        # Get all articles for this part and type
        available_articles = list(SimplifiedArticle.objects.filter(
            part=part, 
            type=type
        ))
        
        # Calculate how many articles per level
        articles_per_level = 5
        total_levels = min(6, len(available_articles) // articles_per_level)
        
        # Create levels
        for level in range(1, total_levels + 1):
            if len(available_articles) < articles_per_level:
                break
                
            # Select random articles for this level
            selected_articles = random.sample(available_articles, articles_per_level)
            
            # Remove selected articles from available pool
            for article in selected_articles:
                available_articles.remove(article)
            
            # Create level and assign articles
            level_obj = cls.objects.create(
                level=level,
                part=part,
                type=type
            )
            level_obj.articles.set(selected_articles)
        
        return total_levels
