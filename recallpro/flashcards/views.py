from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.contrib.auth.models import User
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.db.models import Q
from datetime import datetime
from . import groq_api
from .forms import UserRegistrationForm, DeckForm, CardForm, SecurityQuestionForm, PasswordResetForm, MCQCardForm
from .models import Deck, Card, StudySession, SecurityQuestion
from django.http import HttpResponse
import matplotlib.pyplot as plt
import io
from matplotlib.backends.backend_pdf import PdfPages

import json
import os
import random # Added for shuffling MCQ options
import requests
import re
import time

# Remove hardcoded key and URL
groq_api_key = os.environ.get('GROQ_API_KEY')
groq_api_url = os.environ.get('GROQ_API_URL', 'https://api.groq.com/openai/v1/chat/completions')

def extract_json_from_groq(content):
    import json as pyjson
    # Try to find a JSON array in the response (even inside code blocks)
    code_block = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", content)
    if code_block:
        possible_json = code_block.group(1)
    else:
        array_match = re.search(r"(\[\s*{[\s\S]+?}\s*\])", content)
        if array_match:
            possible_json = array_match.group(1)
        else:
            possible_json = content
    # Try normal parsing first
    try:
        return pyjson.loads(possible_json)
    except Exception:
        # Attempt to recover from malformed/truncated JSON arrays
        # Find all top-level { ... } objects inside [ ... ]
        objects = re.findall(r"{[^{}]*}", possible_json)
        valid_cards = []
        for obj in objects:
            try:
                card = pyjson.loads(obj)
                valid_cards.append(card)
            except Exception:
                continue
        if valid_cards:
            return valid_cards
        # As a last resort, return empty list
        return []

def generate_flashcards_with_groq(paragraph):
    prompt = f"""
    Generate a list of flashcards from the following text. For each flashcard, provide:
    - question (string)
    - answer (string)
    - question_type (always 'mcq')
    - options (list of 4 strings, required for every card)
    Only generate multiple choice (MCQ) questions. Do not generate short answer or true/false questions. Do not include any explanations or text outside the JSON array. Return as a valid JSON array of objects, with no code block or markdown formatting.
    Text: {paragraph}
    """
    headers = {
        "Authorization": f"Bearer {groq_api_key}",
        "Content-Type": "application/json",
    }
    data = {
        "model": "llama3-70b-8192",
        "messages": [
            {"role": "system", "content": "You are a helpful flashcard generator. Only output a valid JSON array of MCQ cards as described."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 1024,
        "temperature": 0.7,
    }
    response = requests.post(groq_api_url, headers=headers, json=data)
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    # Only accept a JSON array of MCQ cards
    cards = extract_json_from_groq(content)
    # Filter to MCQ only, with 4 options, globally (for all users)
    mcq_cards = [card for card in cards if card.get('question_type') == 'mcq' and isinstance(card.get('options'), list) and len(card['options']) == 4]
    return mcq_cards

class HomeView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('deck_list', username=request.user.username)
        return render(request, 'flashcards/hero.html')

def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account created for {username}!')
            return redirect('login')
    else:
        form = UserRegistrationForm()
    return render(request, 'flashcards/register.html', {'form': form})

class DeckListView(View):
    template_name = 'flashcards/deck_list.html'

    def chunked(self, iterable, n):
        """Yield successive n-sized chunks from iterable."""
        for i in range(0, len(iterable), n):
            yield iterable[i:i + n]

    def get(self, request, username):
        user = User.objects.get(username=username)
        # Restrict: Only allow logged-in user to view their own decks
        if not request.user.is_authenticated or request.user.username != username:
            messages.error(request, 'You are not authorized to view this page.')
            return redirect('login')
        decks = list(Deck.objects.filter(user=user).order_by('-updated_at'))
        total_cards = Card.objects.filter(deck__user=user).count()
        study_sessions = StudySession.objects.filter(user=user).count()
        deck_rows = list(self.chunked(decks, 3))
        context = {
            'decks': decks,
            'deck_rows': deck_rows,
            'total_cards': total_cards,
            'study_sessions': study_sessions,
            'total_decks': len(decks),
        }
        return render(request, self.template_name, context)

class DeckDetailView(View):
    template_name = 'flashcards/deck_detail.html'

    def get(self, request, username, pk):
        deck = Deck.objects.get(user__username=username, pk=pk)
        # Restrict: Only allow deck owner to view deck detail
        if not request.user.is_authenticated or request.user.username != username:
            messages.error(request, 'You are not authorized to view this deck.')
            return redirect('login')
        cards = deck.cards.all()
        # Defensive: avoid division by zero and always provide all stats
        total_cards = deck.cards.count()
        new_cards_count = deck.new_cards_count if total_cards else 0
        learning_cards_count = deck.learning_cards_count if total_cards else 0
        mastered_cards_count = deck.mastered_cards_count if total_cards else 0
        new_cards_percentage = deck.new_cards_percentage if total_cards else 0
        learning_cards_percentage = deck.learning_cards_percentage if total_cards else 0
        mastered_cards_percentage = deck.mastered_cards_percentage if total_cards else 0
        average_score = deck.average_score if total_cards else 0
        # Show avg_time_per_card from recent StudySessions
        recent_sessions = deck.study_sessions.all()[:5]
        avg_time_per_card = 0
        last_quiz_time = None
        quiz_times = []
        if recent_sessions:
            valid_sessions = [s for s in recent_sessions if s.avg_time_per_card]
            if valid_sessions:
                avg_time_per_card = sum(s.avg_time_per_card for s in valid_sessions) / len(valid_sessions)
                last_quiz_time = valid_sessions[0].avg_time_per_card
                quiz_times = [s.avg_time_per_card for s in valid_sessions]
            else:
                avg_time_per_card = 0
                last_quiz_time = None
                quiz_times = []
        success_rate = getattr(deck, 'success_rate', 0) if total_cards else 0
        retention_rate = getattr(deck, 'retention_rate', 0) if total_cards else 0
        # Correct/Wrong answer stats for progress bar
        total_reviews = sum(card.review_count for card in cards)
        total_correct = sum(card.correct_count for card in cards)
        total_wrong = total_reviews - total_correct
        correct_pct = (total_correct / total_reviews) * 100 if total_reviews else 0
        wrong_pct = (total_wrong / total_reviews) * 100 if total_reviews else 0
        context = {
            'deck': deck,
            'cards': cards,
            'total_cards': total_cards,
            'new_cards_count': new_cards_count,
            'learning_cards_count': learning_cards_count,
            'mastered_cards_count': mastered_cards_count,
            'new_cards_percentage': new_cards_percentage,
            'learning_cards_percentage': learning_cards_percentage,
            'mastered_cards_percentage': mastered_cards_percentage,
            'average_score': average_score,
            'avg_time_per_card': avg_time_per_card,
            'last_quiz_time': last_quiz_time,
            'quiz_times': quiz_times,
            'success_rate': success_rate,
            'retention_rate': retention_rate,
            'correct_count': total_correct,
            'wrong_count': total_wrong,
            'correct_pct': correct_pct,
            'wrong_pct': wrong_pct,
            'total_reviews': total_reviews,
        }
        return render(request, self.template_name, context)

class DeckCreateView(LoginRequiredMixin, CreateView):
    model = Deck
    form_class = DeckForm
    template_name = 'flashcards/deck_form.html'

    def form_valid(self, form):
        form.instance.user = self.request.user
        deck = form.save(commit=False)
        paragraph_text = form.cleaned_data.get('paragraph_text')
        deck.save()
        if paragraph_text:
            try:
                ai_cards = generate_flashcards_with_groq(paragraph_text)
                created_cards_count = 0
                for card in ai_cards:
                    Card.objects.create(
                        deck=deck,
                        question=card.get('question', ''),
                        answer=card.get('answer', ''),
                        question_type=card.get('question_type', 'sa'),
                        options=card.get('options', [])
                    )
                    created_cards_count += 1
                if created_cards_count > 0:
                    messages.success(self.request, f'Deck created and {created_cards_count} cards generated by AI!')
                else:
                    messages.info(self.request, 'Deck created, but no cards were generated by AI.')
            except Exception as e:
                messages.error(self.request, f'AI card generation failed: {e}')
        else:
            messages.success(self.request, 'Deck created successfully!')
        return redirect('deck_detail', username=self.request.user.username, pk=deck.pk)

class DeckUpdateView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = 'flashcards/deck_form.html'

    def get(self, request, pk):
        deck = Deck.objects.get(pk=pk)
        form = DeckForm(initial={
            'title': deck.title,
            'description': deck.description,
        })
        return render(request, self.template_name, {'form': form, 'deck': deck})

    def post(self, request, pk):
        deck = Deck.objects.get(pk=pk)
        form = DeckForm(request.POST)
        if form.is_valid():
            deck.title = form.cleaned_data['title']
            deck.description = form.cleaned_data['description']
            deck.save()
            messages.success(request, 'Deck updated successfully!')
            return redirect('deck_detail', username=request.user.username, pk=pk)
        return render(request, self.template_name, {'form': form, 'deck': deck})

    def test_func(self):
        deck = Deck.objects.get(pk=self.kwargs['pk'])
        return self.request.user.id == deck.user_id

class DeckDeleteView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = 'flashcards/deck_confirm_delete.html'

    def get(self, request, username, pk):
        deck = Deck.objects.get(user__username=username, pk=pk)
        return render(request, self.template_name, {'deck': deck})

    def post(self, request, username, pk):
        deck = Deck.objects.get(user__username=username, pk=pk)
        deck.delete()
        messages.success(request, 'Deck deleted successfully!')
        return redirect('deck_list', username=username)

    def test_func(self):
        deck = Deck.objects.get(pk=self.kwargs['pk'])
        return self.request.user.id == deck.user_id

class CardCreateView(LoginRequiredMixin, View):
    template_name = 'flashcards/card_form.html'

    def get(self, request, username, deck_pk):
        question_type = request.GET.get('question_type', 'sa')
        if question_type == 'mcq':
            form = MCQCardForm()
            mcq_mode = True
        else:
            form = CardForm()
            mcq_mode = False
        return render(request, self.template_name, {'form': form, 'mcq_mode': mcq_mode, 'question_type': question_type})

    def post(self, request, username, deck_pk):
        question_type = request.POST.get('question_type', 'sa')
        if question_type == 'mcq':
            form = MCQCardForm(request.POST)
            mcq_mode = True
        else:
            form = CardForm(request.POST)
            mcq_mode = False
        if form.is_valid():
            if question_type == 'mcq':
                form.save(deck_id=deck_pk)
            else:
                card_data = {
                    'question': form.cleaned_data['question'],
                    'answer': form.cleaned_data['answer'],
                    'question_type': question_type,
                    'options': [],
                    'difficulty': 'medium',
                }
                Card.objects.create(deck_id=deck_pk, **card_data)
            messages.success(request, 'Card created successfully!')
            return redirect('deck_detail', username=username, pk=deck_pk)
        return render(request, self.template_name, {'form': form, 'mcq_mode': mcq_mode, 'question_type': question_type})

class CardUpdateView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = 'flashcards/card_form.html'

    def get(self, request, deck_pk, pk):
        card = Card.objects.get(pk=pk)
        form = CardForm(initial={
            'question': card.question,
            'answer': card.answer,
            'question_type': card.question_type,
            'options': card.options,
            'difficulty': card.difficulty,
        })
        return render(request, self.template_name, {'form': form, 'card': card})

    def post(self, request, deck_pk, pk):
        card = Card.objects.get(pk=pk)
        form = CardForm(request.POST)
        if form.is_valid():
            card.question = form.cleaned_data['question']
            card.answer = form.cleaned_data['answer']
            card.question_type = form.cleaned_data['question_type']
            card.options = form.cleaned_data['options']
            card.difficulty = form.cleaned_data['difficulty']
            card.save()
            messages.success(request, 'Card updated successfully!')
            return redirect('card_detail', username=request.user.username, deck_pk=deck_pk, pk=pk)
        return render(request, self.template_name, {'form': form, 'card': card})

    def test_func(self):
        card = Card.objects.get(pk=self.kwargs['pk'])
        deck = Deck.objects.get(pk=card.deck_id)
        return self.request.user.id == deck.user_id

class CardDeleteView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = 'flashcards/card_confirm_delete.html'

    def get(self, request, deck_pk, pk):
        card = Card.objects.get(pk=pk)
        return render(request, self.template_name, {'card': card})

    def post(self, request, deck_pk, pk):
        card = Card.objects.get(pk=pk)
        card.delete()
        messages.success(request, 'Card deleted successfully!')
        return redirect('deck_detail', username=request.user.username, pk=deck_pk)

    def test_func(self):
        card = Card.objects.get(pk=self.kwargs['pk'])
        deck = Deck.objects.get(pk=card.deck_id)
        return self.request.user.id == deck.user_id

class CardDetailView(LoginRequiredMixin, View):
    template_name = 'flashcards/card_detail.html'

    def get(self, request, username, deck_pk, pk):
        card = Card.objects.get(pk=pk)
        return render(request, self.template_name, {'card': card})

def security_question(request):
    if request.method == 'POST':
        form = SecurityQuestionForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            security_answer = form.cleaned_data['security_answer']
            
            try:
                user = User.objects.get(username=username)
                security_question = SecurityQuestion.objects.get(user=user)
                
                if security_question.answer.lower() == security_answer.lower():
                    request.session['reset_username'] = username
                    return redirect('password_reset')
                else:
                    messages.error(request, 'Incorrect security answer.')
            except (User.DoesNotExist, SecurityQuestion.DoesNotExist):
                messages.error(request, 'User not found or no security question set.')
    else:
        form = SecurityQuestionForm()
    
    return render(request, 'flashcards/security_question.html', {'form': form})

def password_reset(request):
    username = request.session.get('reset_username')
    if not username:
        messages.error(request, 'Please verify your security question first.')
        return redirect('security_question')
    
    if request.method == 'POST':
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            user = User.objects.get(username=username)
            user.password = make_password(form.cleaned_data['new_password1'])
            user.save()
            del request.session['reset_username']
            messages.success(request, 'Password has been reset successfully. Please login with your new password.')
            return redirect('login')
    else:
        form = PasswordResetForm()
    
    return render(request, 'flashcards/password_reset.html', {'form': form})

class StartQuizView(LoginRequiredMixin, View):
    def get(self, request, username, pk):
        deck = Deck.objects.get(pk=pk)
        # Only include MCQ cards with exactly 4 options
        cards = deck.cards.filter(question_type='mcq')
        cards = [card for card in cards if isinstance(card.options, list) and len(card.options) == 4]
        if not cards:
            messages.warning(request, "This deck has no MCQ cards with 4 options. Add some to start a study session!")
            return redirect('deck_detail', username=username, pk=pk)
        quiz_cards = list({
            'id': card.id,
            'question': card.question,
            'question_type': card.question_type,
            'options': card.options,
            'answer': card.answer
        } for card in cards)
        request.session['current_quiz_cards'] = quiz_cards
        request.session['current_question_index'] = 0
        request.session['quiz_correct_answers'] = 0
        request.session['quiz_weak_points'] = []
        request.session['quiz_retry'] = False
        request.session.save()
        return redirect('quiz_card', username=username, deck_pk=pk)

class QuizCardView(LoginRequiredMixin, View):
    template_name = 'flashcards/quiz_card.html'

    def get(self, request, username, deck_pk):
        deck = Deck.objects.get(pk=deck_pk)
        quiz_cards = request.session.get('current_quiz_cards')
        current_question_index = request.session.get('current_question_index', 0)
        show_answer = request.session.get('show_answer', False)
        user_answer = request.session.get('last_user_answer', '')
        is_correct = request.session.get('last_answer_correct', False)
        retry = request.session.get('quiz_retry', False)
        if not quiz_cards or current_question_index >= len(quiz_cards):
            return redirect('quiz_results', username=username, deck_pk=deck_pk)
        current_card_data = quiz_cards[current_question_index]
        if not isinstance(current_card_data.get('options'), list):
            current_card_data['options'] = []
        # Store the start time for this question
        if not show_answer:
            request.session['question_start_time'] = time.time()
            request.session.save()
        context = {
            'deck': deck,
            'card': current_card_data,
            'current_question_number': current_question_index + 1,
            'total_questions': len(quiz_cards),
            'show_answer': show_answer,
            'user_answer': user_answer,
            'is_correct': is_correct,
            'retry': retry,
        }
        return render(request, self.template_name, context)

    def post(self, request, username, deck_pk):
        deck = Deck.objects.get(pk=deck_pk)
        quiz_cards = request.session.get('current_quiz_cards')
        current_question_index = request.session.get('current_question_index', 0)
        quiz_correct_answers = request.session.get('quiz_correct_answers', 0)
        quiz_weak_points = request.session.get('quiz_weak_points', [])
        retry = request.session.get('quiz_retry', False)
        # Track time per question
        question_times = request.session.get('question_times', [])
        start_time = request.session.get('question_start_time')
        if start_time:
            elapsed = time.time() - start_time
            question_times.append(elapsed)
            request.session['question_times'] = question_times
            request.session.save()
        if not quiz_cards or current_question_index >= len(quiz_cards):
            return redirect('quiz_results', username=username, deck_pk=deck_pk)

        # Handle next question navigation
        if 'next_question' in request.POST:
            request.session['current_question_index'] = current_question_index + 1
            request.session['show_answer'] = False
            request.session['last_user_answer'] = ''
            request.session['last_answer_correct'] = False
            request.session.save()
            return redirect('quiz_card', username=username, deck_pk=deck_pk)

        current_card_data = quiz_cards[current_question_index]
        # Handle retry and skip
        if 'retry' in request.POST:
            request.session['show_answer'] = False
            request.session['quiz_retry'] = True
            request.session.save()
            return redirect('quiz_card', username=username, deck_pk=deck_pk)
        if 'skip' in request.POST:
            request.session['show_answer'] = False
            request.session['quiz_retry'] = False
            request.session['last_user_answer'] = ''
            request.session['last_answer_correct'] = False
            request.session['current_question_index'] = current_question_index + 1
            request.session.save()
            return redirect('quiz_card', username=username, deck_pk=deck_pk)
        # Normal answer submission
        user_answer = request.POST.get('user_answer', '')
        user_answer_cleaned = user_answer.strip()
        is_correct = False
        ai_remark = ''
        # Check answer for all question types
        if current_card_data['question_type'] == 'mcq':
            if user_answer_cleaned.lower() == str(current_card_data['answer']).strip().lower():
                is_correct = True
                ai_remark = 'Correct! Great job.'
            else:
                ai_remark = 'Incorrect. The correct answer is: ' + str(current_card_data['answer'])
        else:
            # For short answer and other types
            if user_answer_cleaned.lower() == str(current_card_data['answer']).strip().lower():
                is_correct = True
                ai_remark = 'Correct! Great job.'
            else:
                ai_remark = 'Incorrect. The correct answer is: ' + str(current_card_data['answer'])
        request.session['last_user_answer'] = user_answer_cleaned
        request.session['last_answer_correct'] = is_correct
        request.session['show_answer'] = True
        request.session['quiz_retry'] = False
        request.session['ai_remark'] = ai_remark
        if is_correct:
            quiz_correct_answers += 1
        else:
            quiz_weak_points.append({
                'question': current_card_data['question'],
                'user_answer': user_answer_cleaned,
                'correct_answer': current_card_data['answer']
            })
        # Always update card stats for any question type
        card_obj = Card.objects.get(id=current_card_data['id'])
        card_obj.review_count += 1
        if is_correct:
            card_obj.correct_count += 1
            # Update card status based on correct answer
            if card_obj.status == 'new':
                card_obj.status = 'learning'
            elif card_obj.status == 'learning' and card_obj.correct_count >= 3:
                card_obj.status = 'mastered'
        else:
            if card_obj.status == 'mastered':
                card_obj.status = 'learning'
        card_obj.last_reviewed = datetime.now()
        card_obj.save()
        request.session['quiz_correct_answers'] = quiz_correct_answers
        request.session['quiz_weak_points'] = quiz_weak_points
        request.session.save()
        return redirect('quiz_card', username=username, deck_pk=deck_pk)

class QuizResultsView(LoginRequiredMixin, View):
    template_name = 'flashcards/quiz_results.html'

    def get(self, request, username, deck_pk):
        deck = Deck.objects.get(pk=deck_pk)
        quiz_cards = request.session.get('current_quiz_cards', [])
        quiz_correct_answers = request.session.get('quiz_correct_answers', 0)
        quiz_weak_points = request.session.get('quiz_weak_points', [])
        total_questions = len(quiz_cards)
        score = (quiz_correct_answers / total_questions) * 100 if total_questions > 0 else 0
        gemini_advice = ""
        if not quiz_weak_points:
            gemini_advice = "Great job! You answered all questions correctly. Keep up the excellent work!"
        else:
            gemini_advice = "You have some weak points. Review the questions you struggled with to improve!"
        # --- NEW: Save StudySession ---
        avg_time_per_card = 0
        question_times = request.session.get('question_times', [])
        if question_times and total_questions > 0:
            avg_time_per_card = sum(question_times) / len(question_times)
        if total_questions > 0:
            StudySession.objects.create(
                deck=deck,
                user=request.user,
                cards_studied=total_questions,
                correct_answers=quiz_correct_answers,
                score=score,
                duration=0,  # Optionally, you can track time if available
                avg_time_per_card=avg_time_per_card,
            )
            # Update deck stats
            deck.last_studied = datetime.now()
            deck.study_count = deck.study_sessions.count()
            deck.save()
        # --- END NEW ---
        for key in ['current_quiz_cards', 'current_question_index', 'quiz_correct_answers', 'quiz_weak_points', 'current_study_session_id', 'question_times', 'question_start_time']:
            if key in request.session:
                del request.session[key]
        request.session.save()
        context = {
            'deck': deck,
            'score': round(score, 2),
            'total_questions': total_questions,
            'weak_points': quiz_weak_points,
            'gemini_advice': gemini_advice,
            'avg_time_per_card': avg_time_per_card,
        }
        return render(request, self.template_name, context)

class ExportQuizReportView(LoginRequiredMixin, View):
    def get(self, request, username, pk):
        deck = Deck.objects.get(user__username=username, pk=pk)
        # Only allow deck owner
        if request.user.username != username:
            return HttpResponse('Unauthorized', status=403)
        recent_sessions = deck.study_sessions.all()[:5]
        quiz_times = [s.avg_time_per_card for s in recent_sessions if s.avg_time_per_card]
        if not quiz_times:
            return HttpResponse('No quiz data to export.', status=400)
        # Generate bar graph using matplotlib and export as PDF
        buf = io.BytesIO()
        with PdfPages(buf) as pdf:
            plt.figure(figsize=(7,4))
            plt.bar(range(1, len(quiz_times)+1), quiz_times, color='#00fff7')
            plt.xlabel('Session')
            plt.ylabel('Avg Response Time (s)')
            plt.title('Quiz Response Times (Last 5 Sessions)')
            plt.grid(axis='y', linestyle='--', alpha=0.5)
            plt.tight_layout()
            pdf.savefig()
            plt.close()
        buf.seek(0)
        response = HttpResponse(buf.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="quiz_report.pdf"; filename*=UTF-8''quiz_report.pdf'
        return response
