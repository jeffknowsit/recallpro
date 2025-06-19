from django.urls import path
from .views import QuizGeneratorView, QuizDisplayView
 
urlpatterns = [
    path('generate/', QuizGeneratorView.as_view(), name='generate_quiz'),
    path('display/', QuizDisplayView.as_view(), name='display_quiz'),
] 