from django import forms

from .comment_models import InvoiceComment


class InvoiceCommentForm(forms.ModelForm):

    class Meta:

        model = InvoiceComment

        fields = ['text']

        widgets = {
            'text': forms.Textarea(
                attrs={
                    'rows': 4,
                    'placeholder': 'Введите комментарий'
                }
            )
        }