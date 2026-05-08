import time
import unicodedata

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.models import Vehicle


class Command(BaseCommand):
    help = 'Importa marcas, modelos e anos da API FIPE para popular o catalogo de veiculos.'

    def add_arguments(self, parser):
        parser.add_argument('--vehicle-type', default='carros', choices=['carros', 'motos', 'caminhoes'])
        parser.add_argument('--brand-code', default='', help='Importa somente uma ou mais marcas. Ex: 59 ou 59,21,23.')
        parser.add_argument('--brand-limit', type=int, default=0)
        parser.add_argument('--model-limit', type=int, default=0)
        parser.add_argument(
            '--catalog-only',
            action='store_true',
            help='Importa somente marcas e modelos, sem consultar anos. Usa poucas requisicoes e evita 429.',
        )
        parser.add_argument(
            '--expand-existing-years',
            action='store_true',
            help='Busca anos somente dos modelos FIPE ja existentes no banco e cria variantes por ano.',
        )
        parser.add_argument(
            '--backfill-codes',
            action='store_true',
            help='Preenche codigos internos da FIPE em modelos ja importados sem codigos.',
        )
        parser.add_argument('--start-brand-code', default='', help='Retoma a importacao a partir do codigo da marca.')
        parser.add_argument('--start-model-code', default='', help='Retoma a marca inicial a partir do codigo do modelo.')
        parser.add_argument('--sleep', type=float, default=0.35)
        parser.add_argument('--max-retries', type=int, default=6)
        parser.add_argument('--retry-wait', type=float, default=90)
        parser.add_argument('--max-rate-wait', type=float, default=600)
        parser.add_argument(
            '--strategy',
            default='auto',
            choices=['auto', 'by_year', 'by_model'],
            help='by_year usa menos requisicoes na FIPE v2; by_model consulta anos modelo a modelo.',
        )
        parser.add_argument(
            '--with-values',
            action='store_true',
            help='Busca o detalhe final de cada ano para preencher CodigoFipe, combustivel e nome oficial.',
        )

    def handle(self, *args, **options):
        importer = FipeImporter(
            vehicle_type=options['vehicle_type'],
            brand_code=options['brand_code'],
            brand_limit=options['brand_limit'],
            model_limit=options['model_limit'],
            catalog_only=options['catalog_only'],
            expand_existing_years=options['expand_existing_years'],
            backfill_codes=options['backfill_codes'],
            start_brand_code=options['start_brand_code'],
            start_model_code=options['start_model_code'],
            sleep=options['sleep'],
            max_retries=options['max_retries'],
            retry_wait=options['retry_wait'],
            max_rate_wait=options['max_rate_wait'],
            strategy=options['strategy'],
            with_values=options['with_values'],
            stdout=self.stdout,
        )
        try:
            created, updated = importer.run()
        except requests.HTTPError as error:
            raise CommandError(str(error)) from error
        self.stdout.write(self.style.SUCCESS(f'Importacao FIPE concluida: {created} criado(s), {updated} atualizado(s).'))


class FipeImporter:
    def __init__(
        self,
        vehicle_type,
        brand_code,
        brand_limit,
        model_limit,
        catalog_only,
        expand_existing_years,
        backfill_codes,
        start_brand_code,
        start_model_code,
        sleep,
        max_retries,
        retry_wait,
        max_rate_wait,
        strategy,
        with_values,
        stdout,
    ):
        self.base_url = settings.NEXAR_FIPE_API_BASE_URL.rstrip('/')
        self.api_version = settings.NEXAR_FIPE_API_VERSION.lower()
        self.vehicle_type = vehicle_type
        self.brand_codes = {code.strip() for code in str(brand_code or '').split(',') if code.strip()}
        self.brand_limit = brand_limit
        self.model_limit = model_limit
        self.catalog_only = catalog_only
        self.expand_existing_years = expand_existing_years
        self.backfill_codes = backfill_codes
        self.start_brand_code = str(start_brand_code or '')
        self.start_model_code = str(start_model_code or '')
        self.sleep = sleep
        self.max_retries = max_retries
        self.retry_wait = retry_wait
        self.max_rate_wait = max_rate_wait
        self.strategy = strategy
        self.with_values = with_values
        self.stdout = stdout
        self.session = requests.Session()
        if settings.NEXAR_FIPE_API_TOKEN:
            self.session.headers.update(
                {
                    'Authorization': f'Bearer {settings.NEXAR_FIPE_API_TOKEN}',
                    'X-Subscription-Token': settings.NEXAR_FIPE_API_TOKEN,
                }
            )

    def run(self):
        if self.backfill_codes:
            return self.backfill_existing_codes()

        if self.expand_existing_years:
            return self.expand_existing_catalog_years()

        created = 0
        updated = 0
        brands = [normalize_api_item(brand) for brand in self.fetch_json(self.brands_url())]
        if self.brand_codes:
            brands = [brand for brand in brands if str(brand.get('codigo')) in self.brand_codes]
        brands = self.apply_start_filter(brands, self.start_brand_code)
        if self.brand_limit:
            brands = brands[: self.brand_limit]

        for brand in brands:
            brand_code = str(brand['codigo'])
            brand_name = brand['nome']
            self.stdout.write(f'Importando {brand_name}...')
            if self.catalog_only:
                brand_created, brand_updated = self.import_brand_catalog_only(brand_code, brand_name)
                created += brand_created
                updated += brand_updated
                continue

            if self.should_import_by_year():
                brand_created, brand_updated = self.import_brand_by_year(brand_code, brand_name)
                created += brand_created
                updated += brand_updated
                continue

            models_response = self.fetch_json(self.models_url(brand_code))
            models = models_response.get('modelos', []) if isinstance(models_response, dict) else models_response
            models = [normalize_api_item(model) for model in models]
            if self.start_model_code and brand_code == self.start_brand_code:
                models = self.apply_start_filter(models, self.start_model_code)
            if self.model_limit:
                models = models[: self.model_limit]

            for model in models:
                model_code = str(model['codigo'])
                model_name = model['nome']
                self.stdout.write(f'  Modelo {model_code} - {model_name}')
                years = self.fetch_json(self.years_url(brand_code, model_code))
                years = [normalize_api_item(year) for year in years]

                for year_item in years:
                    obj, was_created = self.save_vehicle(brand_code, brand_name, model_code, model_name, year_item)
                    if was_created:
                        created += 1
                    else:
                        updated += 1

                self.pause()

        return created, updated

    def import_brand_catalog_only(self, brand_code, brand_name):
        created = 0
        updated = 0
        models_response = self.fetch_json(self.models_url(brand_code))
        models = models_response.get('modelos', []) if isinstance(models_response, dict) else models_response
        models = [normalize_api_item(model) for model in models]
        if self.start_model_code and brand_code == self.start_brand_code:
            models = self.apply_start_filter(models, self.start_model_code)
        if self.model_limit:
            models = models[: self.model_limit]

        for model in models:
            model_code = str(model['codigo'])
            model_name = model['nome']
            self.stdout.write(f'  Modelo {model_code} - {model_name}')
            obj, was_created = Vehicle.objects.update_or_create(
                brand=brand_name,
                model=model_name,
                version=model_name,
                year=0,
                engine='',
                defaults={
                    'fuel': '',
                    'fipe_code': '',
                    'fipe_vehicle_type': self.vehicle_type,
                    'fipe_brand_code': brand_code,
                    'fipe_model_code': model_code,
                    'fipe_year_code': '',
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.pause()
        return created, updated

    def backfill_existing_codes(self):
        created = 0
        updated = 0
        brands = [normalize_api_item(brand) for brand in self.fetch_json(self.brands_url())]
        if self.brand_codes:
            brands = [brand for brand in brands if str(brand.get('codigo')) in self.brand_codes]
        brands = self.apply_start_filter(brands, self.start_brand_code)
        if self.brand_limit:
            brands = brands[: self.brand_limit]

        for brand in brands:
            brand_code = str(brand['codigo'])
            brand_name = brand['nome']
            self.stdout.write(f'Preenchendo codigos de {brand_name}...')
            models_response = self.fetch_json(self.models_url(brand_code))
            models = models_response.get('modelos', []) if isinstance(models_response, dict) else models_response
            models = [normalize_api_item(model) for model in models]
            model_index = {normalize_name(model['nome']): str(model['codigo']) for model in models}

            vehicles = Vehicle.objects.filter(brand=brand_name, fipe_model_code='')
            if self.model_limit:
                vehicles = vehicles[: self.model_limit]

            for vehicle in vehicles:
                model_code = model_index.get(normalize_name(vehicle.model))
                if not model_code:
                    model_code = find_close_model_code(vehicle.model, model_index)
                if not model_code:
                    continue
                vehicle.fipe_vehicle_type = self.vehicle_type
                vehicle.fipe_brand_code = brand_code
                vehicle.fipe_model_code = model_code
                vehicle.save(update_fields=['fipe_vehicle_type', 'fipe_brand_code', 'fipe_model_code', 'updated_at'])
                updated += 1

            self.pause()

        return created, updated

    def expand_existing_catalog_years(self):
        created = 0
        updated = 0
        vehicles = Vehicle.objects.filter(
            fipe_vehicle_type=self.vehicle_type,
            fipe_brand_code__gt='',
            fipe_model_code__gt='',
        )
        if self.brand_codes:
            vehicles = vehicles.filter(fipe_brand_code__in=self.brand_codes)
        if self.start_brand_code:
            vehicles = vehicles.filter(fipe_brand_code__gte=self.start_brand_code)
        unique_vehicles = []
        seen = set()
        for vehicle in vehicles.order_by('fipe_brand_code', 'fipe_model_code', 'brand', 'model'):
            key = (vehicle.fipe_brand_code, vehicle.fipe_model_code)
            if key in seen:
                continue
            seen.add(key)
            unique_vehicles.append(vehicle)
            if self.model_limit and len(unique_vehicles) >= self.model_limit:
                break

        if not unique_vehicles:
            raise CommandError(
                'Nenhum modelo com codigos FIPE foi encontrado. Rode primeiro: '
                'python manage.py import_fipe --catalog-only'
            )

        for vehicle in unique_vehicles:
            self.stdout.write(
                f'Expandindo {vehicle.brand} {vehicle.model} ({vehicle.fipe_brand_code}/{vehicle.fipe_model_code})...'
            )
            years = self.fetch_json(self.years_url(vehicle.fipe_brand_code, vehicle.fipe_model_code))
            years = [normalize_api_item(year) for year in years]

            for year_item in years:
                obj, was_created = self.save_vehicle(
                    vehicle.fipe_brand_code,
                    vehicle.brand,
                    vehicle.fipe_model_code,
                    vehicle.model,
                    year_item,
                )
                for part in vehicle.compatible_parts.all():
                    part.compatible_vehicles.add(obj)

                if was_created:
                    created += 1
                else:
                    updated += 1

            self.pause()

        return created, updated

    def should_import_by_year(self):
        if self.with_values:
            return False
        if self.strategy == 'by_year':
            return True
        if self.strategy == 'by_model':
            return False
        return self.api_version == 'v2'

    def import_brand_by_year(self, brand_code, brand_name):
        created = 0
        updated = 0
        years = [normalize_api_item(year) for year in self.fetch_json(self.brand_years_url(brand_code))]
        if self.start_model_code and brand_code == self.start_brand_code:
            self.stdout.write('  Aviso: --start-model-code e ignorado na estrategia by_year.')

        for year_item in years:
            year_code = str(year_item['codigo'])
            year, fuel = parse_year_name(year_item.get('nome', ''))
            self.stdout.write(f'  Ano {year_item.get("nome", year_code)}')
            models = [normalize_api_item(model) for model in self.fetch_json(self.models_by_year_url(brand_code, year_code))]
            if self.model_limit:
                models = models[: self.model_limit]

            for model in models:
                model_name = model['nome']
                version = f'{model_name} {fuel}'.strip()
                obj, was_created = Vehicle.objects.update_or_create(
                    brand=brand_name,
                    model=model_name,
                    version=version,
                    year=year or 0,
                    engine='',
                    defaults={
                        'fuel': fuel,
                        'fipe_vehicle_type': self.vehicle_type,
                        'fipe_brand_code': brand_code,
                        'fipe_model_code': str(model['codigo']),
                        'fipe_year_code': year_code,
                    },
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

            self.pause()

        return created, updated

    def brands_url(self):
        if self.api_version == 'v2':
            return f'{self.base_url}/{to_v2_vehicle_type(self.vehicle_type)}/brands'
        return f'{self.base_url}/{self.vehicle_type}/marcas'

    def models_url(self, brand_code):
        if self.api_version == 'v2':
            return f'{self.base_url}/{to_v2_vehicle_type(self.vehicle_type)}/brands/{brand_code}/models'
        return f'{self.base_url}/{self.vehicle_type}/marcas/{brand_code}/modelos'

    def years_url(self, brand_code, model_code):
        if self.api_version == 'v2':
            return f'{self.base_url}/{to_v2_vehicle_type(self.vehicle_type)}/brands/{brand_code}/models/{model_code}/years'
        return f'{self.base_url}/{self.vehicle_type}/marcas/{brand_code}/modelos/{model_code}/anos'

    def brand_years_url(self, brand_code):
        if self.api_version != 'v2':
            raise CommandError('A estrategia by_year exige FIPE v2.')
        return f'{self.base_url}/{to_v2_vehicle_type(self.vehicle_type)}/brands/{brand_code}/years'

    def models_by_year_url(self, brand_code, year_code):
        if self.api_version != 'v2':
            raise CommandError('A estrategia by_year exige FIPE v2.')
        return f'{self.base_url}/{to_v2_vehicle_type(self.vehicle_type)}/brands/{brand_code}/years/{year_code}/models'

    def details_url(self, brand_code, model_code, year_code):
        if self.api_version == 'v2':
            return f'{self.base_url}/{to_v2_vehicle_type(self.vehicle_type)}/brands/{brand_code}/models/{model_code}/years/{year_code}'
        return f'{self.base_url}/{self.vehicle_type}/marcas/{brand_code}/modelos/{model_code}/anos/{year_code}'

    def apply_start_filter(self, items, start_code):
        if not start_code:
            return items

        for index, item in enumerate(items):
            if str(item.get('codigo')) == start_code:
                return items[index:]

        return items

    def save_vehicle(self, brand_code, brand_name, model_code, model_name, year_item):
        year_code = str(year_item['codigo'])
        year, fuel = parse_year_name(year_item.get('nome', ''))
        details = {}

        if self.with_values:
            details = self.fetch_json(self.details_url(brand_code, model_code, year_code))
            year = details.get('AnoModelo') or details.get('modelYear') or year
            fuel = details.get('Combustivel') or details.get('fuel') or fuel
            model_name = details.get('Modelo') or details.get('model') or model_name

        version = f'{model_name} {fuel}'.strip()

        with transaction.atomic():
            return Vehicle.objects.update_or_create(
                brand=brand_name,
                model=model_name,
                version=version,
                year=year or 0,
                engine='',
                defaults={
                    'fuel': fuel,
                    'fipe_code': details.get('CodigoFipe') or details.get('codeFipe') or '',
                    'fipe_vehicle_type': self.vehicle_type,
                    'fipe_brand_code': brand_code,
                    'fipe_model_code': model_code,
                    'fipe_year_code': year_code,
                },
            )

    def fetch_json(self, url):
        for attempt in range(1, self.max_retries + 1):
            response = self.session.get(url, timeout=20)
            if response.status_code != 429:
                response.raise_for_status()
                return response.json()

            retry_after = response.headers.get('Retry-After')
            wait = float(retry_after) if retry_after and retry_after.isdigit() else self.retry_wait * attempt
            if wait > self.max_rate_wait:
                raise requests.HTTPError(
                    f'FIPE pediu para aguardar {wait:.0f}s. Troque para v2, use token, ou tente mais tarde: {url}'
                )
            self.stdout.write(
                f'Limite da FIPE atingido (429). Aguardando {wait:.0f}s antes de tentar de novo...'
            )
            time.sleep(wait)

        raise requests.HTTPError(f'FIPE ainda retornou 429 apos {self.max_retries} tentativas: {url}')

    def pause(self):
        if self.sleep:
            time.sleep(self.sleep)


def parse_year_name(value):
    parts = str(value or '').split(maxsplit=1)
    try:
        year = int(parts[0])
    except (IndexError, ValueError):
        year = 0
    fuel = parts[1] if len(parts) > 1 else ''
    return year, fuel


def normalize_api_item(item):
    if 'codigo' in item or 'nome' in item:
        return item
    return {'codigo': item.get('code'), 'nome': item.get('name')}


def to_v2_vehicle_type(vehicle_type):
    return {
        'carros': 'cars',
        'motos': 'motorcycles',
        'caminhoes': 'trucks',
    }[vehicle_type]


def normalize_name(value):
    value = unicodedata.normalize('NFKD', str(value or ''))
    value = ''.join(char for char in value if not unicodedata.combining(char))
    return ' '.join(value.upper().replace('-', ' ').split())


def find_close_model_code(vehicle_model, model_index):
    normalized_vehicle = normalize_name(vehicle_model)
    for normalized_model, code in model_index.items():
        if normalized_vehicle == normalized_model:
            return code
        if normalized_vehicle in normalized_model or normalized_model in normalized_vehicle:
            return code
    return ''
