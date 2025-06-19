from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from datetime import datetime

class QuizCardView(LoginRequiredMixin, View):
    template_name = 'flashcards/quiz_card.html'

    def get(self, request, username, deck_pk):
        deck = get_object_or_404(Deck, user__username=username, pk=deck_pk)
        
        quiz_cards = request.session.get('current_quiz_cards')
        current_question_index = request.session.get('current_question_index', 0)
        show_answer = request.session.get('show_answer', False)

        if not quiz_cards or current_question_index >= len(quiz_cards):
            # Quiz finished or no quiz in session, redirect to results or deck detail
            return redirect('quiz_results', username=username, deck_pk=deck_pk)

        current_card_data = quiz_cards[current_question_index]
        
        # Ensure card.options is a list, even if it's None or something else from JSONField
        if not isinstance(current_card_data.get('options'), list):
            current_card_data['options'] = []

        context = {
            'deck': deck,
            'card': current_card_data,
            'current_question_number': current_question_index + 1,
            'total_questions': len(quiz_cards),
            'show_answer': show_answer,
            'user_answer': request.session.get('last_user_answer', ''),
            'is_correct': request.session.get('last_answer_correct', False),
        }
        return render(request, self.template_name, context)

    def post(self, request, username, deck_pk):
        deck = get_object_or_404(Deck, user__username=username, pk=deck_pk)

        # Check if this is a "Next Question" request
        if request.POST.get('next_question'):
            return self.get_next_question(request, username, deck_pk)

        quiz_cards = request.session.get('current_quiz_cards')
        current_question_index = request.session.get('current_question_index', 0)
        quiz_correct_answers = request.session.get('quiz_correct_answers', 0)
        quiz_weak_points = request.session.get('quiz_weak_points', [])
        
        if not quiz_cards or current_question_index >= len(quiz_cards):
            return redirect('quiz_results', username=username, deck_pk=deck_pk)

        current_card_data = quiz_cards[current_question_index]
        user_answer = request.POST.get('user_answer', '')
        user_answer_cleaned = user_answer.strip()
        
        print(f"DEBUG: User Input (cleaned): '{user_answer_cleaned}'")
        print(f"DEBUG: Correct Answer (from card): '{current_card_data['answer']}'")

        is_correct = False
        # Now only handling short answer questions
        if user_answer_cleaned.lower() == str(current_card_data['answer']).strip().lower():
            is_correct = True
        
        print(f"DEBUG: Is Correct: {is_correct}")

        # Store the answer and correctness in session
        request.session['last_user_answer'] = user_answer_cleaned
        request.session['last_answer_correct'] = is_correct
        request.session['show_answer'] = True

        if is_correct:
            quiz_correct_answers += 1
        else:
            quiz_weak_points.append({
                'question': current_card_data['question'],
                'user_answer': user_answer_cleaned,
                'correct_answer': current_card_data['answer']
            })
        
        print(f"DEBUG: Quiz Weak Points after update: {quiz_weak_points}")
        
        # Update the actual Card's review count and correct count
        card_obj = get_object_or_404(Card, id=current_card_data['id'])
        card_obj.review_count += 1
        if is_correct:
            card_obj.correct_count += 1

            # Update card status based on correct answer
            if card_obj.status == 'new':
                card_obj.status = 'learning'
            elif card_obj.status == 'learning' and card_obj.correct_count >= 3: # Example: 3 correct answers to master
                card_obj.status = 'mastered'
        else:
            # If incorrect, and it was mastered, revert to learning
            if card_obj.status == 'mastered':
                card_obj.status = 'learning'
            # If it was 'new' or 'learning' and incorrect, it stays 'learning' or 'new'.

        card_obj.last_reviewed = datetime.now()
        card_obj.save()

        request.session['quiz_correct_answers'] = quiz_correct_answers
        request.session['quiz_weak_points'] = quiz_weak_points
        request.session.save()

        return redirect('quiz_card', username=username, deck_pk=deck_pk)

    def get_next_question(self, request, username, deck_pk):
        # Reset show_answer flag
        request.session['show_answer'] = False
        request.session['last_user_answer'] = ''
        request.session['last_answer_correct'] = False
        
        # Increment question index
        current_question_index = request.session.get('current_question_index', 0)
        request.session['current_question_index'] = current_question_index + 1
        request.session.save()
        
        return redirect('quiz_card', username=username, deck_pk=deck_pk) 