import re
import unicodedata
from dataclasses import dataclass

from django.db.models import Q
from openpyxl import load_workbook

from .models import Part, Vehicle


@dataclass
class ApplicationImportResult:
    files: int = 0
    rows: int = 0
    linked: int = 0
    skipped: int = 0
    errors: list[str] = None
    preview: list[dict] = None

    def __post_init__(self):
        self.errors = self.errors or []
        self.preview = self.preview or []


PART_HEADERS = {'codigo', 'cod', 'referencia', 'ref', 'sku', 'produto', 'peca', 'codigo peca', 'ref peca'}
BRAND_HEADERS = {'marca veiculo', 'montadora', 'fabricante veiculo', 'fabricante', 'marca'}
MODEL_HEADERS = {'modelo', 'veiculo', 'carro', 'aplicacao'}
VERSION_HEADERS = {'versao', 'descricao veiculo', 'descricao modelo'}
YEAR_HEADERS = {'ano', 'anos', 'ano modelo'}
YEAR_START_HEADERS = {'ano inicial', 'inicio', 'de', 'ano de', 'ano ini'}
YEAR_END_HEADERS = {'ano final', 'fim', 'ate', 'ano ate', 'ano fim'}
ENGINE_HEADERS = {'motor', 'motorizacao', 'cilindrada'}
IGNORED_HEADERS = {'linha', 'tipo', 'combustivel', 'obs', 'observacao', 'observacoes'}
APPLY_MARKS = {'x', 'sim', 's', 'ok', 'aplica', 'aplicavel', '1'}


def import_application_file(uploaded_file, apply=False, max_preview=40):
    filename = (getattr(uploaded_file, 'name', '') or '').lower()
    result = ApplicationImportResult(files=1)
    if not filename.endswith(('.xlsx', '.xlsm')):
        result.errors.append('PDF recebido. Para automatizar, envie a versao XLSX da tabela.')
        result.skipped += 1
        return result

    workbook = load_workbook(uploaded_file, read_only=True, data_only=True)
    for sheet in workbook.worksheets:
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            continue

        header_index = find_header_index(rows)
        if header_index is None:
            continue

        headers = [normalize_header(value) for value in rows[header_index]]
        mapping = map_headers(headers)
        for row in rows[header_index + 1:]:
            row_data = {
                headers[index]: normalize_cell(value)
                for index, value in enumerate(row)
                if index < len(headers) and headers[index]
            }
            process_row(row_data, mapping, result, apply, max_preview)

    return result


def find_header_index(rows):
    for index, row in enumerate(rows[:20]):
        headers = {normalize_header(value) for value in row}
        has_vehicle_columns = headers & (MODEL_HEADERS | BRAND_HEADERS)
        has_application_columns = headers & PART_HEADERS or len([header for header in headers if header]) >= 5
        if has_vehicle_columns and has_application_columns:
            return index
    return None


def map_headers(headers):
    mapped_headers = {
        first_matching_header(headers, PART_HEADERS),
        first_matching_header(headers, BRAND_HEADERS),
        first_matching_header(headers, MODEL_HEADERS),
        first_matching_header(headers, VERSION_HEADERS),
        first_matching_header(headers, YEAR_HEADERS),
        first_matching_header(headers, YEAR_START_HEADERS),
        first_matching_header(headers, YEAR_END_HEADERS),
        first_matching_header(headers, ENGINE_HEADERS),
    }
    mapped_headers.discard('')
    ignored_headers = {normalize_header(header) for header in IGNORED_HEADERS}
    return {
        'part': first_matching_header(headers, PART_HEADERS),
        'brand': first_matching_header(headers, BRAND_HEADERS),
        'model': first_matching_header(headers, MODEL_HEADERS),
        'version': first_matching_header(headers, VERSION_HEADERS),
        'year': first_matching_header(headers, YEAR_HEADERS),
        'year_start': first_matching_header(headers, YEAR_START_HEADERS),
        'year_end': first_matching_header(headers, YEAR_END_HEADERS),
        'engine': first_matching_header(headers, ENGINE_HEADERS),
        'part_columns': [
            header
            for header in headers
            if header and header not in mapped_headers and header not in ignored_headers
        ],
    }


def process_row(row, mapping, result, apply, max_preview):
    part_codes = get_part_codes_from_row(row, mapping)
    if not part_codes:
        result.skipped += 1
        return

    parts = find_parts(part_codes)
    if not parts:
        result.skipped += 1
        result.errors.append(f'Peca nao encontrada: {", ".join(part_codes[:6])}')
        return

    query = build_vehicle_query(row, mapping)
    if not query:
        result.skipped += 1
        return

    vehicles = list(find_vehicles(row, mapping, query)[:300])
    result.rows += 1
    if not vehicles:
        result.skipped += 1
        result.errors.append(f'Nenhum modelo encontrado para: {query}')
        return

    if apply:
        for part in parts:
            part.compatible_vehicles.add(*vehicles)
        result.linked += len(parts) * len(vehicles)

    if len(result.preview) < max_preview:
        result.preview.append(
            {
                'part': ', '.join(str(part) for part in parts),
                'query': query,
                'vehicles': vehicles[:6],
                'vehicle_count': len(vehicles),
            }
        )


def get_part_codes_from_row(row, mapping):
    codes = []
    if mapping['part']:
        codes.extend(split_codes(row.get(mapping['part'], '')))

    for header in mapping['part_columns']:
        value = row.get(header, '')
        if not value:
            continue

        if normalize_header(value) in APPLY_MARKS:
            codes.extend(split_codes(header))
        else:
            codes.extend(split_codes(value))

    return dedupe_preserving_order(codes)


def find_parts(part_codes):
    tokens = part_codes if isinstance(part_codes, list) else split_codes(part_codes)
    query = Q()
    for token in tokens:
        query |= Q(code__iexact=token) | Q(barcode__iexact=token)
    return list(Part.objects.filter(query)) if query else []


def split_codes(value):
    tokens = []
    for token in re.split(r'[,;/\n\r]+', str(value)):
        token = token.strip().upper()
        if token and normalize_header(token) not in APPLY_MARKS:
            tokens.append(token)
    return tokens


def build_vehicle_query(row, mapping):
    pieces = []
    for key in ('brand', 'model', 'version', 'engine'):
        header = mapping.get(key)
        if header and row.get(header):
            pieces.append(row[header])

    year_start, year_end = get_year_range(row, mapping)
    if year_start and year_start == year_end:
        pieces.append(str(year_start))
    return ' '.join(pieces).strip()


def find_vehicles(row, mapping, query):
    vehicles = search_vehicles_queryset(query)
    year_start, year_end = get_year_range(row, mapping)
    if year_start and year_end:
        ranged = vehicles.filter(Q(year__gte=year_start, year__lte=year_end) | Q(year=0))
        if ranged.exists():
            return ranged
    return vehicles


def get_year_range(row, mapping):
    year_start = parse_year(row.get(mapping['year_start'], '')) if mapping.get('year_start') else None
    year_end = parse_year(row.get(mapping['year_end'], '')) if mapping.get('year_end') else None

    if mapping.get('year') and row.get(mapping['year']):
        years = [int(match) for match in re.findall(r'(?:19|20)\d{2}', row[mapping['year']])]
        if years:
            year_start = year_start or min(years)
            year_end = year_end or max(years)

    if year_start and not year_end:
        year_end = year_start
    if year_end and not year_start:
        year_start = year_end
    return year_start, year_end


def parse_year(value):
    match = re.search(r'(?:19|20)\d{2}', str(value))
    return int(match.group(0)) if match else None


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


def first_matching_header(headers, candidates):
    normalized_candidates = {normalize_header(candidate) for candidate in candidates}
    for header in headers:
        if header in normalized_candidates:
            return header
    return ''


def dedupe_preserving_order(values):
    seen = set()
    deduped = []
    for value in values:
        if value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped


def normalize_cell(value):
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def normalize_header(value):
    value = normalize_cell(value).lower()
    value = unicodedata.normalize('NFKD', value)
    value = ''.join(char for char in value if not unicodedata.combining(char))
    return ' '.join(value.replace('_', ' ').split())
