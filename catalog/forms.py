from django import forms
from django.utils.text import slugify

from .models import Category, Part, Vehicle


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_file_clean(item, initial) for item in data]
        return [single_file_clean(data, initial)]


class VehicleSearchForm(forms.Form):
    q = forms.CharField(
        label='Modelo do carro',
        required=False,
        max_length=120,
        widget=forms.TextInput(
            attrs={
                'placeholder': 'Ex: Voyage 2020, Onix LT, Corolla',
                'autocomplete': 'off',
                'autofocus': True,
            },
        ),
    )


class StaffPasswordForm(forms.Form):
    password = forms.CharField(label='Senha especial', widget=forms.PasswordInput)


class XmlImportForm(forms.Form):
    xml_file = MultipleFileField(
        label='Arquivos de pecas',
        help_text='Selecione um ou mais arquivos .xml ou .csv.',
        widget=MultipleFileInput(attrs={'multiple': True, 'accept': '.xml,.csv,text/xml,application/xml,text/csv'}),
    )


class PdfImportForm(forms.Form):
    pdf_file = MultipleFileField(
        label='Arquivos PDF',
        help_text='Selecione um ou mais arquivos .pdf.',
        widget=MultipleFileInput(attrs={'multiple': True, 'accept': '.pdf,application/pdf'}),
    )


class CompatibilityBulkForm(forms.Form):
    part = forms.ModelChoiceField(label='Peca', queryset=Part.objects.all())
    queries = forms.CharField(
        label='Buscas de modelos',
        help_text='Digite uma busca por linha. Ex: Voyage 1.6, Gol 2012, Onix LT.',
        widget=forms.Textarea(
            attrs={
                'rows': 8,
                'placeholder': 'Voyage 1.6\nGol 2012\nOnix LT',
            }
        ),
    )
    replace_existing = forms.BooleanField(
        label='Substituir vinculos existentes desta peca',
        required=False,
        help_text='Se marcado, remove os modelos ja vinculados antes de adicionar os novos resultados.',
    )


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ['brand', 'model', 'version', 'year', 'engine', 'fuel', 'fipe_code']


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name']

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.slug = slugify(instance.name).replace('-', '_')
        if commit:
            instance.save()
        return instance


class PartForm(forms.ModelForm):
    category = forms.ModelChoiceField(label='Categoria', queryset=Category.objects.all())
    compatible_vehicles = forms.ModelMultipleChoiceField(
        label='Modelos compativeis',
        queryset=Vehicle.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Part
        fields = [
            'category',
            'name',
            'brand',
            'code',
            'barcode',
            'ncm',
            'unit',
            'last_purchase_quantity',
            'last_purchase_unit_price',
            'last_purchase_total',
            'notes',
            'compatible_vehicles',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['category'].initial = Category.objects.filter(slug=self.instance.category).first()

    def save(self, commit=True):
        instance = super().save(commit=False)
        category = self.cleaned_data['category']
        instance.category = category.slug
        if commit:
            instance.save()
            self.save_m2m()
        return instance
