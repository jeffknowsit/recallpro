from django.contrib import admin
from .models import Deck, Card, StudySession

@admin.register(Deck)
class DeckAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'created_at', 'updated_at', 'last_studied', 'study_count')
    search_fields = ('title', 'user__username')
    list_filter = ('created_at', 'updated_at', 'last_studied')

@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ('question', 'deck', 'difficulty', 'review_count', 'correct_count', 'last_reviewed', 'next_review')
    search_fields = ('question', 'deck__title')
    list_filter = ('difficulty', 'created_at', 'last_reviewed')

@admin.register(StudySession)
class StudySessionAdmin(admin.ModelAdmin):
    list_display = ('deck', 'user', 'started_at', 'ended_at', 'cards_studied', 'correct_answers', 'calculate_score')
    search_fields = ('deck__title', 'user__username')
    list_filter = ('started_at', 'ended_at')
