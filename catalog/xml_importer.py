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


def normalize_barcode(value):
    value = (value or '').strip()
    return '' if value.upper() == 'SEM GTIN' else value


def decimal_or_none(value):
    try:
        return Decimal((value or '').strip())
    except (InvalidOperation, AttributeError):
        return None


def text(parent, tag):
    child = parent.find(f'nfe:{tag}', NFE_NS)
    return child.text.strip() if child is not None and child.text else ''
