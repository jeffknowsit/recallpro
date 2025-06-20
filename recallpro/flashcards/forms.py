from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Deck, Card, SecurityQuestion

class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    security_question = forms.CharField(max_length=200, required=True)
    security_answer = forms.CharField(max_length=200, required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2', 'security_question', 'security_answer')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            SecurityQuestion.objects.create(
                user=user,
                question=self.cleaned_data['security_question'],
                answer=self.cleaned_data['security_answer']
            )
        return user

class SecurityQuestionForm(forms.Form):
    username = forms.CharField(max_length=150)
    security_answer = forms.CharField(max_length=200)

class PasswordResetForm(forms.Form):
    new_password1 = forms.CharField(widget=forms.PasswordInput)
    new_password2 = forms.CharField(widget=forms.PasswordInput)

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('new_password1')
        password2 = cleaned_data.get('new_password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")
        return cleaned_data

class DeckForm(forms.ModelForm):
    paragraph_text = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 6, 'placeholder': 'Optional: Paste text here to generate quiz cards with AI...'}), required=False, help_text="Paste text here to automatically generate quiz cards using AI.")

    class Meta:
        model = Deck
        fields = ['title', 'description']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class CardForm(forms.ModelForm):
    class Meta:
        model = Card
        fields = ['question', 'answer']
        widgets = {
            'question': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'answer': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class MCQCardForm(forms.ModelForm):
    option1 = forms.CharField(label='Option 1', max_length=255, required=True)
    option2 = forms.CharField(label='Option 2', max_length=255, required=True)
    option3 = forms.CharField(label='Option 3', max_length=255, required=True)
    option4 = forms.CharField(label='Option 4', max_length=255, required=True)
    difficulty = forms.ChoiceField(choices=Card.DIFFICULTY_CHOICES, required=True)

    class Meta:
        model = Card
        fields = ['question', 'answer', 'difficulty']
        widgets = {
            'question': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'answer': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def clean(self):
        cleaned_data = super().clean()
        options = [cleaned_data.get('option1'), cleaned_data.get('option2'), cleaned_data.get('option3'), cleaned_data.get('option4')]
        if len(set(options)) < 4:
            raise forms.ValidationError('All options must be unique.')
        if cleaned_data.get('answer') not in options:
            raise forms.ValidationError('The answer must match one of the options.')
        return cleaned_data

    def save(self, commit=True, deck=None):
        instance = super().save(commit=False)
        instance.question_type = 'mcq'
        instance.options = [self.cleaned_data['option1'], self.cleaned_data['option2'], self.cleaned_data['option3'], self.cleaned_data['option4']]
        if deck:
            instance.deck = deck
        if commit:
            instance.save()
        return instance 