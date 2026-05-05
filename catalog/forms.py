from django import forms
from django.utils.text import slugify

from .models import Category, Part, Vehicle
from .services import normalize_plate


class PlateSearchForm(forms.Form):
    plate = forms.CharField(
        label='Placa',
        max_length=8,
        widget=forms.TextInput(
            attrs={
                'placeholder': 'ABC1D23',
                'autocomplete': 'off',
                'autofocus': True,
                'data-plate-input': True,
            },
        ),
    )

    def clean_plate(self):
        plate = normalize_plate(self.cleaned_data['plate'])
        if len(plate) != 7:
            raise forms.ValidationError('Informe uma placa valida com 7 caracteres.')
        return plate


class StaffPasswordForm(forms.Form):
    password = forms.CharField(label='Senha especial', widget=forms.PasswordInput)


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
        fields = ['category', 'name', 'brand', 'code', 'notes', 'compatible_vehicles']

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
