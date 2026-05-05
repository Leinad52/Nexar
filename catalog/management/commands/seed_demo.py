from django.core.management.base import BaseCommand

from catalog.models import Category, Part, Vehicle


class Command(BaseCommand):
    help = 'Cria veiculos e pecas de exemplo para testar o Nexar.'

    def handle(self, *args, **options):
        categories = {
            'oleo': 'Oleo do motor',
            'filtro_oleo': 'Filtro de oleo',
            'filtro_ar': 'Filtro de ar',
            'bieleta': 'Bieleta',
            'pastilha_freio': 'Pastilha de freio',
            'vela': 'Vela',
            'outro': 'Outro',
        }
        for slug, name in categories.items():
            Category.objects.update_or_create(slug=slug, defaults={'name': name})

        voyage, _ = Vehicle.objects.update_or_create(
            brand='Volkswagen',
            model='Voyage',
            version='1.6 MSI Comfortline',
            year=2019,
            engine='1.6',
            defaults={
                'fuel': 'Flex',
            },
        )

        items = [
            ('oleo', 'Oleo sintetico 5W40', 'Especificacao', '5W40', 'Validar norma VW aplicavel antes da venda.'),
            ('filtro_oleo', 'Filtro de oleo', 'Tecfil', 'PSL560', ''),
            ('filtro_oleo', 'Filtro de oleo', 'Mann-Filter', 'W712/52', ''),
            ('filtro_oleo', 'Filtro de oleo original', 'Volkswagen', '04E115561H', ''),
            ('filtro_ar', 'Filtro de ar do motor', 'Tecfil', 'FAP2214', ''),
        ]

        for category, name, brand, code, notes in items:
            part, _ = Part.objects.update_or_create(
                brand=brand,
                code=code,
                defaults={'category': category, 'name': name, 'notes': notes},
            )
            part.compatible_vehicles.add(voyage)

        self.stdout.write(self.style.SUCCESS('Dados demo criados.'))
