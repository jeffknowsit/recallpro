from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.validators import MinLengthValidator
from django.db.models import JSONField
from django.utils import timezone

class Deck(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='decks')
    title = models.CharField(max_length=200, validators=[MinLengthValidator(1)])
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_studied = models.DateTimeField(null=True, blank=True)
    study_count = models.IntegerField(default=0)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('deck_detail', kwargs={'username': self.user.username, 'pk': self.pk})

    @property
    def total_study_time(self):
        total_minutes = sum(session.duration for session in self.study_sessions.all() if session.duration is not None)
        return total_minutes

    @property
    def average_score(self):
        sessions_with_score = [session.calculate_score() for session in self.study_sessions.all() if session.cards_studied > 0]
        if sessions_with_score:
            return sum(sessions_with_score) / len(sessions_with_score)
        return 0

    @property
    def avg_time_per_card(self):
        total_time = self.total_study_time
        total_cards_studied = sum(session.cards_studied for session in self.study_sessions.all())
        if total_cards_studied > 0:
            return (total_time * 60) / total_cards_studied  # Convert minutes to seconds
        return 0

    @property
    def mastery_level(self):
        total_cards = self.cards.count()
        if total_cards == 0:
            return "Beginner"

        mastered_cards = self.cards.filter(status='mastered').count()
        learning_cards = self.cards.filter(status='learning').count()
        new_cards = self.cards.filter(status='new').count()

        mastery_percentage = (mastered_cards / total_cards) * 100

        if mastery_percentage >= 80:
            return "Mastered"
        elif mastery_percentage >= 50:
            return "Advanced"
        elif mastery_percentage >= 20:
            return "Intermediate"
        else:
            return "Beginner"

    @property
    def new_cards_count(self):
        return self.cards.filter(status='new').count()

    @property
    def learning_cards_count(self):
        return self.cards.filter(status='learning').count()

    @property
    def mastered_cards_count(self):
        return self.cards.filter(status='mastered').count()

    @property
    def total_cards_count(self):
        return self.cards.count()

    @property
    def new_cards_percentage(self):
        total = self.total_cards_count
        if total == 0:
            return 0
        return (self.new_cards_count / total) * 100

    @property
    def learning_cards_percentage(self):
        total = self.total_cards_count
        if total == 0:
            return 0
        return (self.learning_cards_count / total) * 100

    @property
    def mastered_cards_percentage(self):
        total = self.total_cards_count
        if total == 0:
            return 0
        return (self.mastered_cards_count / total) * 100

    @property
    def mastery_percentage(self):
        total = self.total_cards_count
        if total == 0:
            return 0
        return (self.mastered_cards_count / total) * 100

    @property
    def success_rate(self):
        total_correct = sum(session.correct_answers for session in self.study_sessions.all())
        total_studied = sum(session.cards_studied for session in self.study_sessions.all())
        if total_studied > 0:
            return (total_correct / total_studied) * 100
        return 0

    @property
    def retention_rate(self):
        # This would require more complex logic based on spaced repetition algorithms.
        # For now, return a placeholder or calculate based on correct answers / total cards reviewed.
        # A more accurate retention rate would involve tracking individual card mastery over time.
        return self.average_score # Placeholder for now

class Card(models.Model):
    QUESTION_TYPE_CHOICES = [
        ('mcq', 'Multiple Choice'),
        ('tf', 'True/False'),
        ('sa', 'Short Answer'),
    ]

    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]

    deck = models.ForeignKey(Deck, on_delete=models.CASCADE, related_name='cards')
    question = models.TextField(validators=[MinLengthValidator(1)])
    answer = models.TextField(validators=[MinLengthValidator(1)]) # This will be the correct answer
    question_type = models.CharField(max_length=10, choices=QUESTION_TYPE_CHOICES, default='sa')
    options = JSONField(blank=True, null=True) # For MCQ options
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='medium')
    last_reviewed = models.DateTimeField(null=True, blank=True)
    review_count = models.IntegerField(default=0)
    correct_count = models.IntegerField(default=0)
    next_review = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=[('new', 'New'), ('learning', 'Learning'), ('mastered', 'Mastered')], default='new')

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.question[:50]}..."

    def get_absolute_url(self):
        return reverse('card_detail', kwargs={
            'username': self.deck.user.username,
            'deck_pk': self.deck.pk,
            'pk': self.pk
        })

    def calculate_accuracy(self):
        if self.review_count > 0:
            return (self.correct_count / self.review_count) * 100
        return 0

class StudySession(models.Model):
    deck = models.ForeignKey(Deck, on_delete=models.CASCADE, related_name='study_sessions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='study_sessions')
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    cards_studied = models.IntegerField(default=0)
    correct_answers = models.IntegerField(default=0)
    duration = models.IntegerField(default=0) # Duration in minutes
    score = models.IntegerField(default=0) # Score for the session

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"Study session for {self.deck.title} by {self.user.username}"

    def calculate_score(self):
        if self.cards_studied > 0:
            return (self.correct_answers / self.cards_studied) * 100
        return 0

    def save(self, *args, **kwargs):
        if self.started_at and self.ended_at and self.duration == 0:
            # Ensure both datetimes are timezone-aware
            if timezone.is_naive(self.started_at):
                self.started_at = timezone.make_aware(self.started_at)
            if timezone.is_naive(self.ended_at):
                self.ended_at = timezone.make_aware(self.ended_at)
            duration_seconds = (self.ended_at - self.started_at).total_seconds()
            self.duration = int(duration_seconds / 60)  # Store duration in minutes
        if self.cards_studied > 0 and self.score == 0: # Calculate score if not set
            self.score = self.calculate_score()
        super().save(*args, **kwargs)

class SecurityQuestion(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='security_question')
    question = models.CharField(max_length=200)
    answer = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Security question for {self.user.username}"
