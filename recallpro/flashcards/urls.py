from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(
        template_name='flashcards/login.html',
        redirect_authenticated_user=True
    ), name='login'),
    path('logout/', auth_views.LogoutView.as_view(
        template_name='flashcards/logout.html'
    ), name='logout'),
    path('security-question/', views.security_question, name='security_question'),
    path('password-reset/', views.password_reset, name='password_reset'),
    
    # Deck URLs
    path('<str:username>/decks/', views.DeckListView.as_view(), name='deck_list'),
    path('<str:username>/decks/new/', views.DeckCreateView.as_view(), name='deck_create'),
    path('<str:username>/decks/<int:pk>/', views.DeckDetailView.as_view(), name='deck_detail'),
    path('<str:username>/decks/<int:pk>/update/', views.DeckUpdateView.as_view(), name='deck_update'),
    path('<str:username>/decks/<int:pk>/delete/', views.DeckDeleteView.as_view(), name='deck_delete'),
    
    # Card URLs
    path('<str:username>/decks/<int:deck_pk>/cards/new/', views.CardCreateView.as_view(), name='card_create'),
    path('<str:username>/decks/<int:deck_pk>/cards/<int:pk>/update/', views.CardUpdateView.as_view(), name='card_update'),
    path('<str:username>/decks/<int:deck_pk>/cards/<int:pk>/delete/', views.CardDeleteView.as_view(), name='card_delete'),
    path('<str:username>/decks/<int:deck_pk>/cards/<int:pk>/', views.CardDetailView.as_view(), name='card_detail'),

    # Quiz URLs
    path('<str:username>/decks/<int:pk>/start-quiz/', views.StartQuizView.as_view(), name='start_quiz'),
    path('<str:username>/decks/<int:deck_pk>/quiz-card/', views.QuizCardView.as_view(), name='quiz_card'),
    path('<str:username>/decks/<int:deck_pk>/quiz-results/', views.QuizResultsView.as_view(), name='quiz_results'),
] 