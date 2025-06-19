from django import forms
 
class ParagraphForm(forms.Form):
    paragraph_text = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 10, 'cols': 80, 'placeholder': 'Paste your paragraph here...'}),
        label='Enter Paragraph for Quiz Generation'
    ) 