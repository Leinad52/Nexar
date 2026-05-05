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
    ),
    'BRA2E19': PlateVehicleData(
        plate='BRA2E19',
        brand='Chevrolet',
        model='Onix',
        version='1.0 LT',
        year=2020,
        engine='1.0',
        fuel='Flex',
    ),
    'NXR0A01': PlateVehicleData(
        plate='NXR0A01',
        brand='Fiat',
        model='Argo',
        version='1.3 Drive',
        year=2021,
        engine='1.3',
        fuel='Flex',
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
    )


def lookup_plate_from_configured_api(plate):
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
    year = data.get('year') or data.get('ano') or data.get('anoModelo') or data.get('ano_modelo')
    try:
        year = int(year)
    except (TypeError, ValueError):
        year = 0

    brand = data.get('brand') or data.get('marca') or ''
    model = data.get('model') or data.get('modelo') or ''

    if not brand and not model:
        raise ValueError('A API retornou dados incompletos para a placa.')

    return PlateVehicleData(
        plate=normalize_plate(data.get('plate') or data.get('placa') or fallback_plate),
        brand=brand or 'Marca nao informada',
        model=model or 'Modelo nao informado',
        version=data.get('version') or data.get('versao') or data.get('submodelo') or 'Versao nao informada',
        year=year or 0,
        engine=data.get('engine') or data.get('motor') or '',
        fuel=data.get('fuel') or data.get('combustivel') or '',
        fipe_code=data.get('fipe_code') or data.get('codigo_fipe') or data.get('codigoFipe') or '',
    )
