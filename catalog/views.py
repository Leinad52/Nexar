import re

from django.conf import settings
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .application_importer import ApplicationImportResult, import_application_file
from .forms import (
    CategoryForm,
    CompatibilityBulkForm,
    PartForm,
    PdfImportForm,
    StaffPasswordForm,
    VehicleForm,
    VehicleSearchForm,
    XmlImportForm,
)
from .models import Category, Part, Vehicle
from .xml_importer import XmlImportResult, import_parts_file


def home(request):
    form = VehicleSearchForm(request.GET or None)
    selected_vehicle = None
    vehicles = []
    parts = []

    selected_vehicle_id = request.GET.get('vehicle')
    if selected_vehicle_id:
        selected_vehicle = get_object_or_404(Vehicle, pk=selected_vehicle_id)
        parts = selected_vehicle.compatible_parts.all()

    if form.is_valid():
        query = form.cleaned_data.get('q', '').strip()
        if query:
            vehicles = search_vehicles(query)

    return render(
        request,
        'catalog/home.html',
        {'form': form, 'vehicles': vehicles, 'selected_vehicle': selected_vehicle, 'parts': parts},
    )


def search_vehicles(query):
    return search_vehicles_queryset(query)[:80]


def search_vehicles_queryset(query):
    terms = [term for term in re.split(r'\s+', query) if term]
    vehicles = Vehicle.objects.all()
    for term in terms:
        vehicles = vehicles.filter(
            Q(brand__icontains=term)
            | Q(model__icontains=term)
            | Q(version__icontains=term)
            | Q(year__icontains=term)
            | Q(engine__icontains=term)
            | Q(fuel__icontains=term)
            | Q(fipe_code__icontains=term)
        )
    return vehicles


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
    processed_files = 0

    if request.method == 'POST' and form.is_valid():
        files = request.FILES.getlist('xml_file')
        result = merge_xml_imports(files)
        processed_files = len(files)
        messages.success(
            request,
            f'Importacao concluida: {processed_files} arquivo(s), {result.created} criada(s), {result.updated} atualizada(s), {result.skipped} ignorada(s).',
        )

    return render(request, 'catalog/import_xml.html', {'form': form, 'result': result, 'processed_files': processed_files})


@staff_required
def import_parts_pdf(request):
    form = PdfImportForm(request.POST or None, request.FILES or None)
    processed_files = 0

    if request.method == 'POST' and form.is_valid():
        processed_files = len(request.FILES.getlist('pdf_file'))
        messages.info(request, 'Importacao por PDF preparada. O parser sera ajustado conforme o modelo do catalogo.')

    return render(
        request,
        'catalog/pdf_placeholder.html',
        {
            'form': form,
            'processed_files': processed_files,
            'title': 'Importar pecas por PDF',
            'description': 'Envie catalogos ou tabelas em PDF com dados de pecas. O proximo passo e adaptar a leitura ao layout do arquivo.',
        },
    )


@staff_required
def link_parts_pdf(request):
    form = PdfImportForm(request.POST or None, request.FILES or None)
    result = None
    processed_files = 0

    if request.method == 'POST' and form.is_valid():
        files = request.FILES.getlist('pdf_file')
        processed_files = len(files)
        result = merge_application_imports(files, apply=request.POST.get('action') == 'apply')
        if request.POST.get('action') == 'apply':
            messages.success(request, f'{result.linked} vinculo(s) criado(s) a partir da planilha.')
        else:
            messages.info(request, 'Pre-visualizacao gerada. Confira os resultados antes de aplicar.')

    return render(
        request,
        'catalog/pdf_placeholder.html',
        {
            'form': form,
            'processed_files': processed_files,
            'title': 'Vincular pecas por PDF',
            'description': 'Envie tabelas de aplicacao em PDF, XLSX ou XLSM. PDFs escaneados precisam de OCR ou da planilha original.',
            'result': result,
            'supports_apply': True,
        },
    )


def merge_application_imports(files, apply=False):
    final_result = ApplicationImportResult()
    for uploaded_file in files:
        imported = import_application_file(uploaded_file, apply=apply)
        final_result.files += imported.files
        final_result.rows += imported.rows
        final_result.linked += imported.linked
        final_result.skipped += imported.skipped
        final_result.errors.extend([f'{uploaded_file.name}: {error}' for error in imported.errors])
        final_result.preview.extend(imported.preview)
    return final_result


@staff_required
def bulk_compatibility(request):
    form = CompatibilityBulkForm(request.POST or None)
    preview = []
    total_matches = 0
    applied = False

    if request.method == 'POST' and form.is_valid():
        part = form.cleaned_data['part']
        lines = parse_query_lines(form.cleaned_data['queries'])
        preview = build_compatibility_preview(lines)
        total_matches = sum(item['count'] for item in preview)

        if request.POST.get('action') == 'apply':
            if form.cleaned_data['replace_existing']:
                part.compatible_vehicles.clear()

            vehicle_ids = set()
            for item in preview:
                vehicle_ids.update(item['ids'])

            part.compatible_vehicles.add(*Vehicle.objects.filter(id__in=vehicle_ids))
            applied = True
            messages.success(request, f'{len(vehicle_ids)} modelo(s) vinculado(s) a {part}.')

    return render(
        request,
        'catalog/bulk_compatibility.html',
        {
            'form': form,
            'preview': preview,
            'total_matches': total_matches,
            'applied': applied,
        },
    )


def parse_query_lines(value):
    return [line.strip() for line in value.splitlines() if line.strip()]


def build_compatibility_preview(lines):
    preview = []
    for line in lines:
        matches = search_vehicles_queryset(line).order_by('brand', 'model', 'year')
        ids = list(matches.values_list('id', flat=True))
        preview.append(
            {
                'query': line,
                'count': len(ids),
                'ids': ids,
                'sample': list(matches[:8]),
            }
        )
    return preview


def merge_xml_imports(files):
    final_result = XmlImportResult()
    for uploaded_file in files:
        imported = import_parts_file(uploaded_file)
        final_result.created += imported.created
        final_result.updated += imported.updated
        final_result.skipped += imported.skipped
        final_result.errors.extend([f'{uploaded_file.name}: {error}' for error in imported.errors])

    return final_result


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
    category = request.GET.get('category', '').strip()
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
    if category:
        parts = parts.filter(category=category)

    return render(
        request,
        'catalog/part_list.html',
        {
            'parts': parts,
            'query': query,
            'category': category,
            'categories': Category.objects.all(),
            'title': 'Pecas',
            'search_placeholder': 'Pesquisar peca, codigo, EAN, NCM ou observacao',
        },
    )


@staff_required
def product_code_search(request):
    query = request.GET.get('q', '').strip()
    parts = Part.objects.all()
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
    else:
        parts = Part.objects.none()

    return render(
        request,
        'catalog/product_code_search.html',
        {
            'parts': parts[:100],
            'query': query,
            'result_count': parts.count() if query else 0,
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
