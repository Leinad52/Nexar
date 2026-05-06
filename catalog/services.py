import re
from dataclasses import dataclass

import requests
from django.conf import settings


@dataclass
class PlateVehicleData:
    plate: str
    brand: str
    model: str
    version: str
    year: int
    engine: str = ''
    fuel: str = ''
    color: str = ''
    fipe_code: str = ''


MOCK_VEHICLES = {
    'ABC1D23': PlateVehicleData(
        plate='ABC1D23',
        brand='Volkswagen',
        model='Voyage',
        version='1.6 MSI Comfortline',
        year=2019,
        engine='1.6',
        fuel='Flex',
        color='',
    ),
    'BRA2E19': PlateVehicleData(
        plate='BRA2E19',
        brand='Chevrolet',
        model='Onix',
        version='1.0 LT',
        year=2020,
        engine='1.0',
        fuel='Flex',
        color='',
    ),
    'NXR0A01': PlateVehicleData(
        plate='NXR0A01',
        brand='Fiat',
        model='Argo',
        version='1.3 Drive',
        year=2021,
        engine='1.3',
        fuel='Flex',
        color='',
    ),
}


def normalize_plate(value):
    return re.sub(r'[^A-Za-z0-9]', '', value or '').upper()


def lookup_plate(plate):
    normalized = normalize_plate(plate)
    if len(normalized) != 7:
        raise ValueError('Informe uma placa valida com 7 caracteres.')

    if settings.NEXAR_PLATE_API_URL:
        return lookup_plate_from_configured_api(normalized)

    return MOCK_VEHICLES.get(normalized) or PlateVehicleData(
        plate=normalized,
        brand='Volkswagen',
        model='Voyage',
        version='1.6 MSI Comfortline',
        year=2019,
        engine='1.6',
        fuel='Flex',
        color='',
    )


def lookup_plate_from_configured_api(plate):
    provider = settings.NEXAR_PLATE_API_PROVIDER.lower()

    if provider == 'fipeapi':
        return lookup_plate_from_fipeapi(plate)

    if provider == 'placafipe':
        return lookup_plate_from_placa_fipe(plate)

    if provider == 'placafipeonline':
        return lookup_plate_from_placa_fipe_online(plate)

    return lookup_plate_from_generic_get(plate)


def lookup_plate_from_fipeapi(plate):
    if not settings.NEXAR_PLATE_API_URL:
        raise ValueError('Configure NEXAR_PLATE_API_URL para usar a FipeAPI.')

    if not settings.NEXAR_PLATE_API_TOKEN:
        raise ValueError('Configure NEXAR_PLATE_API_TOKEN com a key da FipeAPI.')

    url = settings.NEXAR_PLATE_API_URL.rstrip('/').replace('{placa}', plate)
    response = requests.get(
        url,
        params={'key': settings.NEXAR_PLATE_API_TOKEN},
        headers={'Accept': 'application/json'},
        timeout=12,
    )
    response.raise_for_status()
    return map_fipeapi_response(response.json(), plate)


def lookup_plate_from_placa_fipe(plate):
    if not settings.NEXAR_PLATE_API_URL:
        raise ValueError('Configure NEXAR_PLATE_API_URL para usar a API Placa Fipe.')

    if not settings.NEXAR_PLATE_API_TOKEN:
        raise ValueError('Configure NEXAR_PLATE_API_TOKEN com o token da API Placa Fipe.')

    response = requests.post(
        settings.NEXAR_PLATE_API_URL,
        json={'placa': plate, 'token': settings.NEXAR_PLATE_API_TOKEN},
        headers={'Accept': 'application/json', 'Content-Type': 'application/json'},
        timeout=12,
    )
    response.raise_for_status()
    return map_plate_response(response.json(), plate)


def lookup_plate_from_placa_fipe_online(plate):
    if not settings.NEXAR_PLATE_API_URL:
        raise ValueError('Configure NEXAR_PLATE_API_URL para usar a PlacaFipeOnline.')

    if not settings.NEXAR_PLATE_API_TOKEN:
        raise ValueError('Configure NEXAR_PLATE_API_TOKEN com a API key da PlacaFipeOnline.')

    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }
    if settings.NEXAR_PLATE_API_TOKEN:
        headers['Authorization'] = f'Bearer {settings.NEXAR_PLATE_API_TOKEN}'

    response = requests.post(
        settings.NEXAR_PLATE_API_URL,
        json={'plate': plate},
        headers=headers,
        timeout=12,
    )
    response.raise_for_status()
    return map_plate_response(response.json(), plate)


def lookup_plate_from_generic_get(plate):
    headers = {}
    if settings.NEXAR_PLATE_API_TOKEN:
        headers['Authorization'] = f'Bearer {settings.NEXAR_PLATE_API_TOKEN}'

    response = requests.get(
        settings.NEXAR_PLATE_API_URL,
        params={'placa': plate},
        headers=headers,
        timeout=12,
    )
    response.raise_for_status()
    return map_plate_response(response.json(), plate)


def map_plate_response(data, fallback_plate):
    data = unwrap_plate_response(data)
    year = parse_year(data.get('year') or data.get('ano') or data.get('anoModelo') or data.get('ano_modelo'))

    brand = data.get('brand') or data.get('marca') or ''
    model = data.get('model') or data.get('modelo') or ''
    fipe = data.get('fipe') or data.get('fipe_code') or data.get('codigo_fipe') or data.get('codigoFipe') or ''
    if isinstance(fipe, dict):
        fipe = fipe.get('code') or fipe.get('codigo') or fipe.get('codigoFipe') or fipe.get('value') or ''

    if not brand and not model:
        raise ValueError('A API retornou dados incompletos para a placa.')

    return PlateVehicleData(
        plate=normalize_plate(data.get('plate') or data.get('placa') or fallback_plate),
        brand=brand or 'Marca nao informada',
        model=model or 'Modelo nao informado',
        version=data.get('version') or data.get('versao') or data.get('submodelo') or model or 'Versao nao informada',
        year=year or 0,
        engine=data.get('engine') or data.get('motor') or '',
        fuel=data.get('fuel') or data.get('combustivel') or '',
        color=data.get('color') or data.get('cor') or '',
        fipe_code=str(fipe) if fipe else '',
    )


def map_fipeapi_response(data, fallback_plate):
    payload = data.get('data') if isinstance(data, dict) else None
    if not isinstance(payload, dict):
        raise ValueError('A FipeAPI retornou uma resposta em formato inesperado.')

    vehicle = payload.get('veiculo') or {}
    fipes = payload.get('fipes') or []
    first_fipe = fipes[0] if fipes and isinstance(fipes[0], dict) else {}
    brand, model = split_brand_model(vehicle.get('marca_modelo') or '')

    brand = first_fipe.get('marca') or brand
    model = model or first_fipe.get('modelo') or ''
    version = first_fipe.get('modelo') or model or vehicle.get('marca_modelo') or 'Versao nao informada'

    if not brand and not model:
        raise ValueError('A FipeAPI retornou dados incompletos para a placa.')

    return PlateVehicleData(
        plate=normalize_plate(vehicle.get('placa') or fallback_plate),
        brand=brand or 'Marca nao informada',
        model=model or 'Modelo nao informado',
        version=version,
        year=parse_year(vehicle.get('ano') or first_fipe.get('id_modelo_ano')),
        engine=vehicle.get('cilindradas') or vehicle.get('n_motor') or '',
        fuel=vehicle.get('combustivel') or '',
        color=vehicle.get('cor') or '',
        fipe_code=str(first_fipe.get('codigo') or ''),
    )


def parse_year(value):
    match = re.search(r'\d{4}', str(value or ''))
    return int(match.group(0)) if match else 0


def split_brand_model(value):
    if '/' not in value:
        return '', value.strip()

    brand, model = value.split('/', 1)
    return brand.strip(), model.strip()


def unwrap_plate_response(data):
    if not isinstance(data, dict):
        raise ValueError('A API retornou uma resposta em formato inesperado.')

    for key in ('informacoes_veiculo', 'data', 'vehicle', 'veiculo', 'result', 'resultado'):
        value = data.get(key)
        if isinstance(value, dict):
            return value

    return data
