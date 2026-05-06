import re

from django.conf import settings
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import CategoryForm, PartForm, PlateSearchForm, StaffPasswordForm, VehicleForm, XmlImportForm
from .models import Category, Part, Vehicle
from .services import lookup_plate
from .xml_importer import import_nfe_xml


def home(request):
    form = PlateSearchForm(request.GET or None)
    vehicle = None
    applications = []
    parts = []

    if form.is_valid():
        plate = form.cleaned_data['plate']
        try:
            vehicle = lookup_plate(plate)
            applications = find_vehicle_applications(vehicle)
        except Exception as error:
            messages.error(request, f'Nao foi possivel consultar essa placa: {error}')

        if applications:
            parts = Part.objects.filter(compatible_vehicles__in=applications).distinct()

    return render(
        request,
        'catalog/home.html',
        {'form': form, 'vehicle': vehicle, 'applications': applications, 'parts': parts},
    )


def find_vehicle_applications(vehicle):
    matches = Vehicle.objects.filter(brand__iexact=vehicle.brand, model__iexact=vehicle.model)
    if not matches.exists():
        matches = Vehicle.objects.filter(brand__iexact=vehicle.brand, model__icontains=vehicle.model)
    if not matches.exists():
        matches = Vehicle.objects.filter(brand__iexact=vehicle.brand, model__iregex=first_model_word(vehicle.model))
    if not matches.exists():
        matches = Vehicle.objects.filter(brand__iexact=vehicle.brand)

    if vehicle.version:
        exact_version = matches.filter(version__iexact=vehicle.version)
        if exact_version.exists():
            return list(exact_version)

        version_words = [word for word in vehicle.version.replace('-', ' ').split() if len(word) >= 3]
        for word in version_words:
            partial = matches.filter(version__icontains=word)
            if partial.exists():
                return list(partial)

    return list(matches)


def first_model_word(value):
    words = [word for word in value.replace('-', ' ').split() if len(word) >= 3]
    return re.escape(words[0] if words else value)


def staff_login(request):
    if request.session.get('staff_unlocked'):
        return redirect('staff_dashboard')

    form = StaffPasswordForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        if form.cleaned_data['password'] == settings.NEXAR_STAFF_PASSWORD:
            request.session['staff_unlocked'] = True
            messages.success(request, 'Painel liberado.')
            return redirect('staff_dashboard')
        messages.error(request, 'Senha incorreta.')

    return render(request, 'catalog/staff_login.html', {'form': form})


def staff_logout(request):
    request.session.pop('staff_unlocked', None)
    return redirect('home')


def staff_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.session.get('staff_unlocked'):
            return redirect(f"{reverse('staff_login')}?next={request.path}")
        return view_func(request, *args, **kwargs)

    return wrapper


@staff_required
def staff_dashboard(request):
    categories = Category.objects.all()
    vehicles = Vehicle.objects.all()
    parts = Part.objects.prefetch_related('compatible_vehicles')
    return render(
        request,
        'catalog/staff_dashboard.html',
        {
            'categories': categories[:3],
            'vehicles': vehicles[:3],
            'parts': parts[:3],
            'category_count': categories.count(),
            'vehicle_count': vehicles.count(),
            'part_count': parts.count(),
        },
    )


@staff_required
def category_list(request):
    query = request.GET.get('q', '').strip()
    categories = Category.objects.all()
    if query:
        categories = categories.filter(Q(name__icontains=query) | Q(slug__icontains=query))

    return render(
        request,
        'catalog/category_list.html',
        {
            'categories': categories,
            'query': query,
            'title': 'Categorias',
            'search_placeholder': 'Pesquisar categoria ou identificador',
        },
    )


@staff_required
def category_create(request):
    form = CategoryForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Categoria cadastrada.')
        return redirect('staff_dashboard')
    return render(request, 'catalog/form_page.html', {'form': form, 'title': 'Cadastrar categoria'})


@staff_required
def category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk)
    old_slug = category.slug
    form = CategoryForm(request.POST or None, instance=category)
    if request.method == 'POST' and form.is_valid():
        category = form.save()
        if category.slug != old_slug:
            Part.objects.filter(category=old_slug).update(category=category.slug)
        messages.success(request, 'Categoria atualizada.')
        return redirect('staff_dashboard')
    return render(request, 'catalog/form_page.html', {'form': form, 'title': 'Editar categoria'})


@staff_required
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        Part.objects.filter(category=category.slug).update(category='outro')
        category.delete()
        messages.success(request, 'Categoria excluida.')
        return redirect('staff_dashboard')
    return render(
        request,
        'catalog/confirm_delete.html',
        {'object': category, 'title': 'Excluir categoria', 'label': 'categoria'},
    )


@staff_required
def import_parts_xml(request):
    form = XmlImportForm(request.POST or None, request.FILES or None)
    result = None

    if request.method == 'POST' and form.is_valid():
        result = import_nfe_xml(form.cleaned_data['xml_file'])
        messages.success(
            request,
            f'Importacao concluida: {result.created} criada(s), {result.updated} atualizada(s), {result.skipped} ignorada(s).',
        )

    return render(request, 'catalog/import_xml.html', {'form': form, 'result': result})


@staff_required
def vehicle_list(request):
    query = request.GET.get('q', '').strip()
    vehicles = Vehicle.objects.all()
    if query:
        vehicles = vehicles.filter(
            Q(brand__icontains=query)
            | Q(model__icontains=query)
            | Q(version__icontains=query)
            | Q(engine__icontains=query)
            | Q(fuel__icontains=query)
            | Q(fipe_code__icontains=query)
        )

    return render(
        request,
        'catalog/vehicle_list.html',
        {
            'vehicles': vehicles,
            'query': query,
            'title': 'Modelos',
            'search_placeholder': 'Pesquisar marca, modelo, versao, motor ou FIPE',
        },
    )


@staff_required
def part_list(request):
    query = request.GET.get('q', '').strip()
    parts = Part.objects.prefetch_related('compatible_vehicles')
    if query:
        parts = parts.filter(
            Q(category__icontains=query)
            | Q(name__icontains=query)
            | Q(brand__icontains=query)
            | Q(code__icontains=query)
            | Q(barcode__icontains=query)
            | Q(ncm__icontains=query)
            | Q(notes__icontains=query)
        )

    return render(
        request,
        'catalog/part_list.html',
        {
            'parts': parts,
            'query': query,
            'title': 'Pecas',
            'search_placeholder': 'Pesquisar peca, codigo, EAN, NCM ou observacao',
        },
    )


@staff_required
def vehicle_create(request):
    form = VehicleForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Modelo cadastrado.')
        return redirect('staff_dashboard')
    return render(request, 'catalog/form_page.html', {'form': form, 'title': 'Cadastrar modelo'})


@staff_required
def vehicle_edit(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk)
    form = VehicleForm(request.POST or None, instance=vehicle)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Modelo atualizado.')
        return redirect('staff_dashboard')
    return render(request, 'catalog/form_page.html', {'form': form, 'title': 'Editar modelo'})


@staff_required
def vehicle_delete(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk)
    if request.method == 'POST':
        vehicle.delete()
        messages.success(request, 'Modelo excluido.')
        return redirect('staff_dashboard')
    return render(
        request,
        'catalog/confirm_delete.html',
        {'object': vehicle, 'title': 'Excluir modelo', 'label': 'modelo'},
    )


@staff_required
def part_create(request):
    form = PartForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Peca cadastrada e vinculada.')
        return redirect('staff_dashboard')
    return render(request, 'catalog/form_page.html', {'form': form, 'title': 'Cadastrar peca'})


@staff_required
def part_edit(request, pk):
    part = get_object_or_404(Part, pk=pk)
    form = PartForm(request.POST or None, instance=part)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Peca atualizada.')
        return redirect('staff_dashboard')
    return render(request, 'catalog/form_page.html', {'form': form, 'title': 'Editar peca'})


@staff_required
def part_delete(request, pk):
    part = get_object_or_404(Part, pk=pk)
    if request.method == 'POST':
        part.delete()
        messages.success(request, 'Peca excluida.')
        return redirect('staff_dashboard')
    return render(
        request,
        'catalog/confirm_delete.html',
        {'object': part, 'title': 'Excluir peca', 'label': 'peca'},
    )
