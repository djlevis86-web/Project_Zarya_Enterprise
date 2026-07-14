from django import forms
from decimal import Decimal, InvalidOperation
from .models import (
    Invoice,
    Counterparty,
    ResponsiblePerson,
)

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

class MultipleFileField(forms.FileField):

    widget = MultipleFileInput

    def clean(self, data, initial=None):
        if not data:
            raise forms.ValidationError(
                'Необходимо выбрать файлы.'
            )

        if isinstance(data, (list, tuple)):
            return [
                super(MultipleFileField, self).clean(file, initial)
                for file in data
            ]

        return [
            super().clean(data, initial)
        ]


class InvoiceForm(forms.ModelForm):

    class Meta:
        model = Invoice

        fields = [
            'document_type',
            'title',
            'description',
            'amount',
        ]

        labels = {
            'document_type': 'Тип документа',
            'title': 'Название документа',
            'description': 'Описание',
            'amount': 'Сумма',
        }

        widgets = {
            'document_type': forms.Select(
                attrs={
                    'class': 'form-control',
                }
            ),
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

class UploadInvoiceForm(forms.Form):

    document_type = forms.ChoiceField(
        label='Тип документа',
        choices=Invoice.DOCUMENT_TYPE_CHOICES,
        required=False,
        widget=forms.Select(
            attrs={
                'class': 'form-control',
            }
        )
    )

    title = forms.CharField(
        label='Название',
        required=True,
        max_length=255,
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Например: Собенина А.А. / Аксютина Г.А.',
            }
        )
    )

    description = forms.CharField(
        label='Описание',
        required=False,
        widget=forms.Textarea(
            attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Комментарий к загрузке',
            }
        )
    )

    amount = forms.CharField(
        label='Сумма',
        required=False,
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Можно оставить пустым или указать 12345,67',
            }
        )
    )

    planned_payment_date = forms.DateField(
        label='Плановая дата оплаты',
        required=True,
        widget=forms.DateInput(
            attrs={
                'class': 'form-control',
                'type': 'date',
            }
        ),
        error_messages={
            'required': 'Укажите плановую дату оплаты.',
            'invalid': 'Введите корректную плановую дату оплаты.',
        },
    )

    responsible = forms.ModelChoiceField(
        label="Ответственный",
        queryset=ResponsiblePerson.objects.filter(
            is_active=True
        ).order_by(
            "full_name",
            "id",
        ),
        required=True,
        empty_label="Выберите ответственного",
        widget=forms.Select(
            attrs={
                "class": "form-control",
            }
        ),
        error_messages={
            "required": "Выберите ответственного.",
            "invalid_choice": "Выбранный ответственный недоступен.",
        },
    )

    files = MultipleFileField(
        label='Файлы счетов',
        required=True,
        widget=MultipleFileInput(
            attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.jpeg,.png',
            }
        )
    )

    def clean_document_type(self):
        value = self.cleaned_data.get(
            'document_type'
        )

        return value or Invoice.DOCUMENT_TYPE_INVOICE

    def clean_amount(self):
        value = self.cleaned_data.get(
            'amount'
        )

        if value in [
            None,
            '',
        ]:
            return None

        value = str(value)
        value = value.replace(
            '\u00a0',
            ' '
        )
        value = value.replace(
            ' ',
            ''
        )
        value = value.replace(
            ',',
            '.'
        )

        try:
            return Decimal(value)

        except (InvalidOperation, ValueError):
            raise forms.ValidationError(
                'Введите сумму числом, например 12345,67.'
            )

    def clean_files(self):
        files = self.cleaned_data.get(
            'files'
        ) or self.files.getlist(
            'files'
        )

        if not files:
            raise forms.ValidationError(
                'Необходимо выбрать файлы.'
            )

        if len(files) > 20:
            raise forms.ValidationError(
                'Можно загрузить максимум 20 файлов за раз.'
            )

        bad_files = []

        for uploaded_file in files:
            filename = str(
                uploaded_file.name
            ).lower()

            if not any(filename.endswith(extension) for extension in ALLOWED_EXTENSIONS):
                bad_files.append(
                    uploaded_file.name
                )

        if bad_files:
            raise forms.ValidationError(
                'Неподдерживаемый формат файла: ' + ', '.join(bad_files)
            )

        return files


class InvoiceEditForm(forms.ModelForm):

    responsible = forms.ModelChoiceField(
        queryset=ResponsiblePerson.objects.none(),
        label='Ответственный',
        required=True,
        empty_label='Выберите ответственного',
        widget=forms.Select(
            attrs={
                'class': 'form-control',
            }
        ),
        error_messages={
            'required': 'Выберите ответственного.',
            'invalid_choice': 'Выбранный ответственный недоступен.',
        },
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        responsible_queryset = ResponsiblePerson.objects.filter(
            is_active=True
        )

        if (
            self.instance
            and self.instance.pk
            and self.instance.responsible_id
        ):
            responsible_queryset = (
                responsible_queryset
                | ResponsiblePerson.objects.filter(
                    pk=self.instance.responsible_id
                )
            )

        self.fields['responsible'].queryset = (
            responsible_queryset
            .order_by('full_name', 'id')
        )

        self.fields['planned_payment_date'].required = True
        self.fields['planned_payment_date'].error_messages.update(
            {
                'required': 'Укажите плановую дату оплаты.',
                'invalid': 'Введите корректную плановую дату оплаты.',
            }
        )

    class Meta:
        model = Invoice

        fields = [
            'document_type',
            'title',
            'description',
            'vendor',
            'invoice_number',
            'invoice_date',
            'document_date',
            'amount',

            'planned_payment_date',
            'responsible',
            'payment_priority',
            'paid_at',

            'status',
        ]

        widgets = {

            'document_type': forms.Select(
                attrs={'class': 'form-control'}
            ),

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

            'document_date': forms.DateInput(
                attrs={
                    'class': 'form-control',
                    'type': 'date',
                }
            ),

            'amount': forms.NumberInput(
                attrs={'class': 'form-control'}
            ),

            'planned_payment_date': forms.DateInput(
                attrs={
                    'class': 'form-control',
                    'type': 'date',
                }
            ),

            'payment_priority': forms.NumberInput(
                attrs={
                    'class': 'form-control',
                    'min': 1,
                    'max': 5,
                }
            ),

            'paid_at': forms.DateInput(
                attrs={
                    'class': 'form-control',
                    'type': 'date',
                }
            ),

            'status': forms.Select(
                attrs={'class': 'form-control'}
            ),
        }

class CounterpartyImportForm(forms.Form):

    file = forms.FileField(
        label='Файл выгрузки из 1С',
        help_text='Поддерживаются .xlsx, .xlsm, .csv',
        widget=forms.FileInput(
            attrs={
                'class': 'form-control',
                'accept': '.xlsx,.xlsm,.csv',
            }
        )
    )

    clear_ocr = forms.BooleanField(
        label='Удалить OCR-контрагентов',
        required=False,
        initial=True,
        widget=forms.CheckboxInput(
            attrs={
                'class': 'form-check-input',
            }
        )
    )

    deactivate_missing = forms.BooleanField(
        label='Деактивировать отсутствующих в новой выгрузке 1С',
        required=False,
        initial=False,
        widget=forms.CheckboxInput(
            attrs={
                'class': 'form-check-input',
            }
        )
    )

class CounterpartyManualForm(forms.ModelForm):

    class Meta:

        model = Counterparty

        fields = [
            'name',
            'full_name',
            'inn',
            'kpp',
            'bank_name',
            'bik',
            'account_number',
            'correspondent_account',
            'email',
            'phone',
            'is_active',
        ]

        widgets = {
            'name': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Например: ООО ГОСКОМПЛЕКТ',
                }
            ),
            'full_name': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Полное наименование',
                }
            ),
            'inn': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'ИНН',
                }
            ),
            'kpp': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'КПП',
                }
            ),
            'bank_name': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Банк',
                }
            ),
            'bik': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'БИК',
                }
            ),
            'account_number': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Расчетный счет',
                }
            ),
            'correspondent_account': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Корреспондентский счет',
                }
            ),
            'email': forms.EmailInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Email',
                }
            ),
            'phone': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Телефон',
                }
            ),
            'is_active': forms.CheckboxInput(
                attrs={
                    'class': 'form-check-input',
                }
            ),
        }

    def clean_inn(self):

        value = self.cleaned_data.get(
            'inn'
        )

        if not value:

            return value

        return ''.join(
            char
            for char in str(value)
            if char.isdigit()
        )

    def clean_kpp(self):

        value = self.cleaned_data.get(
            'kpp'
        )

        if not value:

            return value

        return ''.join(
            char
            for char in str(value)
            if char.isdigit()
        )

    def clean_bik(self):

        value = self.cleaned_data.get(
            'bik'
        )

        if not value:

            return value

        return ''.join(
            char
            for char in str(value)
            if char.isdigit()
        )

    def clean_account_number(self):

        value = self.cleaned_data.get(
            'account_number'
        )

        if not value:

            return value

        return ''.join(
            char
            for char in str(value)
            if char.isdigit()
        )

    def clean_correspondent_account(self):

        value = self.cleaned_data.get(
            'correspondent_account'
        )

        if not value:

            return value

        return ''.join(
            char
            for char in str(value)
            if char.isdigit()
        )
    
class InvoiceCounterpartyAssignForm(forms.Form):

    counterparty = forms.IntegerField(
        label='Контрагент',
        required=True,
        widget=forms.HiddenInput(),
        error_messages={
            'required': 'Выберите контрагента из результатов поиска.',
            'invalid': 'Некорректный идентификатор контрагента.',
        },
    )

    def clean_counterparty(self):

        counterparty_id = self.cleaned_data[
            'counterparty'
        ]

        try:
            return (
                Counterparty.objects
                .filter(
                    is_active=True,
                    source__in=[
                        Counterparty.SOURCE_1C,
                        Counterparty.SOURCE_MANUAL,
                    ],
                )
                .get(
                    id=counterparty_id,
                )
            )

        except Counterparty.DoesNotExist:

            raise forms.ValidationError(
                'Выберите активного контрагента из 1С или ручного справочника.'
            )


from .models import InvoicePayment

class InvoicePaymentForm(forms.ModelForm):
    class Meta:
        model = InvoicePayment
        fields = (
            "amount",
            "paid_at",
            "payment_number",
            "comment",
        )
        widgets = {
            "amount": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0.01",
                    "placeholder": "Сумма оплаты",
                }
            ),
            "paid_at": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),
            "payment_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Номер платёжного документа",
                }
            ),
            "comment": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Комментарий",
                }
            ),
        }

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")

        if amount is None or amount <= 0:
            raise forms.ValidationError(
                "Сумма оплаты должна быть больше нуля."
            )

        return amount
