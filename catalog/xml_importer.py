import csv
import io
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree

from .models import Category, Part


NFE_NS = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}


@dataclass
class XmlImportResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


def import_parts_file(uploaded_file):
    filename = (getattr(uploaded_file, 'name', '') or '').lower()
    if filename.endswith('.csv'):
        return import_parts_csv(uploaded_file)
    return import_nfe_xml(uploaded_file)


CATEGORY_RULES = [
    ('filtro_ar', 'Filtro de ar', ['FILTRO AR', 'FILTRO DE AR']),
    ('filtro_oleo', 'Filtro de oleo', ['FILTRO OLEO', 'FILTRO DE OLEO']),
    ('pastilha_freio', 'Pastilha de freio', ['PASTILHA']),
    ('disco_freio', 'Disco de freio', ['DISCO FREIO', 'DISCO DE FREIO']),
    ('vela', 'Vela', ['VELA IGNICAO', 'CABO VELA']),
    ('amortecedor', 'Amortecedor', ['AMORT', 'AMORTECEDOR']),
    ('rolamento', 'Rolamento', ['ROL RODA', 'ROLAMENTO']),
    ('cubo_roda', 'Cubo de roda', ['CUBO RODA']),
    ('homocinetica', 'Homocinetica', ['HOMOC']),
    ('bomba_agua', 'Bomba dagua', ['BOMBA DAGUA', "BOMBA D'AGUA"]),
    ('correia', 'Correia', ['CORREIA']),
    ('direcao', 'Direcao', ['DIRECAO']),
    ('arrefecimento', 'Arrefecimento', ['RADIADOR', 'TUBO DAGUA']),
    ('ignicao', 'Ignicao', ['BOBINA IGNICAO']),
    ('coxim', 'Coxim', ['COXIM']),
    ('junta', 'Junta', ['JUNTA']),
    ('vedacao', 'Vedacao', ['ANEL VEDACAO']),
]


def import_nfe_xml(uploaded_file):
    result = XmlImportResult()
    root = ElementTree.parse(uploaded_file).getroot()

    for item in root.findall('.//nfe:det', NFE_NS):
        product = item.find('nfe:prod', NFE_NS)
        if product is None:
            result.skipped += 1
            continue

        try:
            imported = parse_product(product)
            defaults = {key: value for key, value in imported.items() if key not in ('brand', 'code')}
            part, created = Part.objects.update_or_create(
                brand='',
                code=imported['code'],
                defaults=defaults,
            )
            if created:
                result.created += 1
            else:
                result.updated += 1
        except Exception as error:
            result.skipped += 1
            result.errors.append(str(error))

    return result


def import_parts_csv(uploaded_file):
    result = XmlImportResult()
    rows = read_csv_rows(uploaded_file)

    for index, row in enumerate(rows, start=2):
        try:
            imported = parse_csv_row(row)
            defaults = {key: value for key, value in imported.items() if key not in ('brand', 'code')}
            part, created = Part.objects.update_or_create(
                brand=imported['brand'],
                code=imported['code'],
                defaults=defaults,
            )
            if created:
                result.created += 1
            else:
                result.updated += 1
        except Exception as error:
            result.skipped += 1
            result.errors.append(f'Linha {index}: {error}')

    return result


def read_csv_rows(uploaded_file):
    raw = uploaded_file.read()
    text_content = decode_csv(raw)
    sample = text_content[:4096]
    delimiter = ';' if sample.count(';') >= sample.count(',') else ','
    reader = csv.DictReader(io.StringIO(text_content), delimiter=delimiter)
    return [{normalize_header(key): (value or '').strip() for key, value in row.items()} for row in reader]


def decode_csv(raw):
    for encoding in ('utf-8-sig', 'latin-1', 'cp1252'):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', errors='ignore')


def parse_csv_row(row):
    code = first_row_value(row, 'codigo', 'cod', 'código', 'referencia', 'referência', 'sku', 'codigoproduto')
    name = first_row_value(row, 'nome', 'descricao', 'descrição', 'produto', 'xprod', 'descricao produto')
    brand = first_row_value(row, 'marca', 'fabricante', 'marca peca', 'marca peça')
    category_name = first_row_value(row, 'categoria', 'grupo', 'departamento', 'linha')
    barcode = first_row_value(row, 'ean', 'codigo barras', 'codigo de barras', 'codbarras', 'gtin')
    ncm = first_row_value(row, 'ncm')
    unit = first_row_value(row, 'unidade', 'un', 'ucom')
    price = first_row_value(row, 'preco', 'preço', 'valor', 'custo', 'vuncom', 'valor unitario', 'valor unitário')
    quantity = first_row_value(row, 'quantidade', 'qtd', 'qcom')
    total = first_row_value(row, 'total', 'vprod', 'valor total')

    if not code and name:
        code, name = split_code_and_name(name, '')

    if not code or not name:
        raise ValueError('produto sem codigo ou descricao')

    category = category_from_csv(category_name, name)
    notes = 'Importado de CSV.'

    return {
        'category': category.slug,
        'name': clean_name(name),
        'brand': brand.strip(),
        'code': code.strip().upper(),
        'barcode': normalize_barcode(barcode),
        'ncm': ncm.strip(),
        'unit': unit.strip().upper(),
        'last_purchase_quantity': decimal_or_none(quantity),
        'last_purchase_unit_price': decimal_or_none(price),
        'last_purchase_total': decimal_or_none(total),
        'notes': notes,
    }


def parse_product(product):
    raw_description = text(product, 'xProd')
    code, name = split_code_and_name(raw_description, text(product, 'cProd'))
    category = infer_category(name)
    supplier_code = text(product, 'cProd')

    if not code or not name:
        raise ValueError(f'Produto ignorado por falta de codigo ou nome: {raw_description}')

    notes = f'Importado de XML NF-e. Codigo fornecedor: {supplier_code}'

    return {
        'category': category.slug,
        'name': name,
        'brand': '',
        'code': code,
        'barcode': normalize_barcode(text(product, 'cEAN')),
        'ncm': text(product, 'NCM'),
        'unit': text(product, 'uCom'),
        'last_purchase_quantity': decimal_or_none(text(product, 'qCom')),
        'last_purchase_unit_price': decimal_or_none(text(product, 'vUnCom')),
        'last_purchase_total': decimal_or_none(text(product, 'vProd')),
        'notes': notes,
    }


def split_code_and_name(description, fallback_code):
    if '-' in description:
        code, name = description.split('-', 1)
        return code.strip().upper(), clean_name(name)

    return fallback_code.strip().upper(), clean_name(description)


def clean_name(value):
    return ' '.join((value or '').strip().upper().split())


def infer_category(name):
    normalized = clean_name(name)
    for slug, label, keywords in CATEGORY_RULES:
        if any(keyword in normalized for keyword in keywords):
            return Category.objects.get_or_create(slug=slug, defaults={'name': label})[0]

    return Category.objects.get_or_create(slug='outro', defaults={'name': 'Outro'})[0]


def category_from_csv(category_name, product_name):
    if category_name:
        slug = slugify_simple(category_name)
        return Category.objects.get_or_create(slug=slug, defaults={'name': category_name.strip().title()})[0]
    return infer_category(product_name)


def normalize_barcode(value):
    value = (value or '').strip()
    return '' if value.upper() == 'SEM GTIN' else value


def decimal_or_none(value):
    value = normalize_decimal(value)
    try:
        return Decimal((value or '').strip())
    except (InvalidOperation, AttributeError):
        return None


def text(parent, tag):
    child = parent.find(f'nfe:{tag}', NFE_NS)
    return child.text.strip() if child is not None and child.text else ''


def normalize_header(value):
    value = clean_name(value).lower()
    replacements = str.maketrans({'á': 'a', 'à': 'a', 'ã': 'a', 'â': 'a', 'é': 'e', 'ê': 'e', 'í': 'i', 'ó': 'o', 'ô': 'o', 'õ': 'o', 'ú': 'u', 'ç': 'c'})
    return value.translate(replacements).replace('_', ' ')


def first_row_value(row, *names):
    normalized_names = [normalize_header(name) for name in names]
    for name in normalized_names:
        if row.get(name):
            return row[name]
    return ''


def normalize_decimal(value):
    value = str(value or '').strip().replace('R$', '').replace(' ', '')
    if ',' in value and '.' in value:
        value = value.replace('.', '').replace(',', '.')
    elif ',' in value:
        value = value.replace(',', '.')
    return value


def slugify_simple(value):
    slug = normalize_header(value).replace(' ', '_')
    return ''.join(char for char in slug if char.isalnum() or char == '_') or 'outro'
