from django.contrib import admin
from .models import Article, Case

class ArticleAdmin(admin.ModelAdmin):
    list_display = ('title',)
    search_fields = ('title',)

class CaseAdmin(admin.ModelAdmin):
    list_display = ('article', 'description', 'created_at')
    search_fields = ('description',)
    list_filter = ('article',)

admin.site.register(Article, ArticleAdmin)
admin.site.register(Case, CaseAdmin)
