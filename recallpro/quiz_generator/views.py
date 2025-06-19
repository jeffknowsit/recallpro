from django.shortcuts import render

# Create your views here.

import os
import json
import google.generativeai as genai

from django.shortcuts import render, redirect
from django.views import View
from django.conf import settings
from django.core.cache import cache

from .forms import ParagraphForm

# Configure Gemini API
# It's recommended to store your API key in environment variables
# For this MVP, we'll use it directly as provided:
GEMINI_API_KEY = "AIzaSyDPeMjtISkyN8WRxM3QC3_fk97Eke7yxnM"
genai.configure(api_key=GEMINI_API_KEY)

class QuizGeneratorView(View):
    template_name = 'quiz_generator/generate_quiz.html'

    def get(self, request, *args, **kwargs):
        form = ParagraphForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request, *args, **kwargs):
        form = ParagraphForm(request.POST)
        if form.is_valid():
            paragraph = form.cleaned_data['paragraph_text']

            # Prompt for Gemini API
            prompt = f'''
            Analyze the following paragraph and generate a quiz with 10 questions. The questions should be a combination of multiple-choice, true/false, and short answer questions.
            For multiple-choice questions, provide a 'question', a 'type' of 'mcq', a list of 'options', and the 'correct_answer'.
            For true/false questions, provide a 'question', a 'type' of 'tf', and the 'correct_answer' (true/false).
            For short answer questions, provide a 'question', a 'type' of 'sa', and the 'correct_answer'.

            Ensure the output is a JSON array of question objects, like this example:
            [
                {{"question": "What is the capital of France?", "type": "mcq", "options": ["London", "Paris", "Berlin", "Rome"], "correct_answer": "Paris"}},
                {{"question": "The Earth is flat.", "type": "tf", "correct_answer": "False"}},
                {{"question": "Who wrote Hamlet?", "type": "sa", "correct_answer": "William Shakespeare"}}
            ]

            Paragraph: 
            """{paragraph}"""
'''
            try:
                model = genai.GenerativeModel('gemini-pro')
                response = model.generate_content(prompt)
                quiz_data_str = response.text

                # Attempt to parse the JSON. Gemini might sometimes add markdown backticks.
                if quiz_data_str.startswith('```json') and quiz_data_str.endswith('```'):
                    quiz_data_str = quiz_data_str[len('```json'):-len('```')].strip()
                
                quiz_data = json.loads(quiz_data_str)

                # Store quiz data in session
                request.session['generated_quiz'] = quiz_data
                # Store the original paragraph in session for weak points summary
                request.session['last_paragraph_text'] = paragraph
                request.session.save()

                return redirect('display_quiz')

            except Exception as e:
                form.add_error(None, f"Error generating quiz: {e}")
                # Log the full error for debugging
                print(f"Gemini API Error: {e}")
                print(f"Gemini Response Text: {response.text if 'response' in locals() else 'No response text'}")

        return render(request, self.template_name, {'form': form})

class QuizDisplayView(View):
    template_name = 'quiz_generator/display_quiz.html'

    def get(self, request, *args, **kwargs):
        quiz_data = request.session.get('generated_quiz')
        if not quiz_data:
            return redirect('generate_quiz') # Redirect if no quiz data
        
        return render(request, self.template_name, {'quiz_data': quiz_data})

    def post(self, request, *args, **kwargs):
        quiz_data = request.session.get('generated_quiz')
        if not quiz_data:
            return redirect('generate_quiz')

        user_answers = {}
        for i, question in enumerate(quiz_data):
            user_answers[f'question_{i}'] = request.POST.get(f'question_{i}')
        
        score = 0
        weak_points = []
        
        for i, question_data in enumerate(quiz_data):
            user_answer = user_answers.get(f'question_{i}')
            correct_answer = str(question_data['correct_answer'])

            if user_answer and user_answer.strip().lower() == correct_answer.strip().lower():
                score += 1
            else:
                weak_points.append({
                    'question': question_data['question'],
                    'user_answer': user_answer,
                    'correct_answer': correct_answer
                })
        
        total_questions = len(quiz_data)

        # Clear quiz data from session after scoring
        if 'generated_quiz' in request.session:
            del request.session['generated_quiz']
        request.session.save()

        return render(request, 'quiz_generator/quiz_results.html', {
            'score': score,
            'total_questions': total_questions,
            'weak_points': weak_points,
            'paragraph': request.session.get('last_paragraph_text', 'No paragraph available')
        })
