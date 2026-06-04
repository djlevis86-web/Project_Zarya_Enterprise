from django import forms
from .models import Invoice


ALLOWED_EXTENSIONS = [
    '.pdf',
    '.jpg',
    '.jpeg',
    '.png',
]


class MultipleFileInput(forms.ClearableFileInput):

    allow_multiple_selected = True

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.attrs.update({
            'multiple': True
        })

class InvoiceForm(forms.ModelForm):


    class Meta:
        model = Invoice

        fields = [
            'title',
            'description',
            'amount',
        ]

        labels = {
            'title': 'Название счета',
            'description': 'Описание',
            'amount': 'Сумма',
        }

        widgets = {
            'title': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Введите название счета',
                }
            ),
            'description': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 4,
                    'placeholder': 'Введите описание',
                }
            ),
            'amount': forms.NumberInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Введите сумму',
                }
            ),
        }

    def clean_files(self):

        files = self.files.getlist('files')

        if not files:
            raise forms.ValidationError(
                'Необходимо выбрать файлы.'
            )

        if len(files) > 20:
            raise forms.ValidationError(
                'Можно загрузить максимум 20 файлов за раз.'
            )

        return files


class InvoiceEditForm(forms.ModelForm):

    class Meta:
        model = Invoice

        fields = [
            'title',
            'description',
            'vendor',
            'invoice_number',
            'invoice_date',
            'amount',
            'status',
        ]

        widgets = {
            'title': forms.TextInput(
                attrs={'class': 'form-control'}
            ),

            'description': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 4,
                }
            ),

            'vendor': forms.TextInput(
                attrs={'class': 'form-control'}
            ),

            'invoice_number': forms.TextInput(
                attrs={'class': 'form-control'}
            ),

            'invoice_date': forms.TextInput(
                attrs={'class': 'form-control'}
            ),

            'amount': forms.NumberInput(
                attrs={'class': 'form-control'}
            ),

            'status': forms.Select(
                attrs={'class': 'form-control'}
            ),
        }