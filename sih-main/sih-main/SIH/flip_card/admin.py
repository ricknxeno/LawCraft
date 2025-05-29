from django.contrib import admin
from django.utils.html import format_html
from .models import UserProgress, LevelArticles
from plat.models import PlayerPlatPoints

@admin.register(UserProgress)
class UserProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'total_points', 'get_completed_levels', 'get_high_scores', 'get_best_times', 'get_platform_points')
    search_fields = ('user__username',)
    list_filter = ('total_points',)
    
    def get_completed_levels(self, obj):
        completed = [f"Level {k}" for k in obj.completed_levels.keys()]
        return format_html('<br>'.join(completed)) if completed else "No levels completed"
    get_completed_levels.short_description = 'Completed Levels'
    
    def get_high_scores(self, obj):
        scores = [f"Level {k}: {v}" for k, v in obj.high_scores.items()]
        return format_html('<br>'.join(scores)) if scores else "No high scores"
    get_high_scores.short_description = 'High Scores'
    
    def get_best_times(self, obj):
        times = [f"Level {k}: {v}s" for k, v in obj.best_times.items()]
        return format_html('<br>'.join(times)) if times else "No recorded times"
    get_best_times.short_description = 'Best Times'
    
    def get_platform_points(self, obj):
        try:
            platform_points = PlayerPlatPoints.objects.get(player=obj.user)
            return platform_points.flipcard_points
        except PlayerPlatPoints.DoesNotExist:
            return 0
    get_platform_points.short_description = 'Platform Points'
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'total_points')
        }),
        ('Progress Details', {
            'fields': ('completed_levels', 'high_scores', 'best_times'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Custom save method to handle point updates"""
        if change:
            old_obj = UserProgress.objects.get(pk=obj.pk)
            old_points = old_obj.calculate_flipcard_points()
            
        # Save the model
        super().save_model(request, obj, form, change)
        
        # Sync with platform
        if obj.sync_with_platform():
            if change:
                new_points = obj.calculate_flipcard_points()
                if old_points != new_points:
                    self.message_user(
                        request, 
                        f"Flipcard points updated and synced with platform: {old_points} → {new_points}"
                    )
        else:
            self.message_user(
                request,
                "Error syncing points with platform",
                level='ERROR'
            )

    def get_readonly_fields(self, request, obj=None):
        """Make certain fields read-only"""
        if obj:  # Editing existing object
            return ('user',)
        return ()

@admin.register(LevelArticles)
class LevelArticlesAdmin(admin.ModelAdmin):
    list_display = ('level', 'part', 'type', 'get_article_count')
    list_filter = ('level', 'part', 'type')
    search_fields = ('articles__article_title', 'articles__article_number')
    filter_horizontal = ('articles',)
    
    def get_article_count(self, obj):
        count = obj.articles.count()
        return f"{count} article{'s' if count != 1 else ''}"
    get_article_count.short_description = 'Articles'
    
    fieldsets = (
        ('Level Information', {
            'fields': ('level', 'part', 'type')
        }),
        ('Articles', {
            'fields': ('articles',),
            'description': 'Select articles for this level'
        }),
    )
    
    def has_delete_permission(self, request, obj=None):
        # Prevent accidental deletion of levels
        return request.user.is_superuser
