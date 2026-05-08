from django.test import TestCase

from .models import Category, Part, Vehicle


class VehicleSearchTests(TestCase):
    def test_home_search_finds_vehicle_by_model(self):
        Vehicle.objects.create(
            brand='Volkswagen',
            model='Voyage 1.6 MSI',
            version='Voyage 1.6 MSI Flex',
            year=2020,
            fuel='Flex',
        )

        response = self.client.get('/', {'q': 'voyage 2020'}, HTTP_HOST='127.0.0.1')

        self.assertContains(response, 'Voyage 1.6 MSI')


class PartCategoryFilterTests(TestCase):
    def test_part_list_filters_by_category(self):
        Category.objects.create(name='Filtro de ar', slug='filtro_ar')
        Category.objects.create(name='Pastilha de freio', slug='pastilha_freio')
        Part.objects.create(category='filtro_ar', name='Filtro de ar', code='FAP123')
        Part.objects.create(category='pastilha_freio', name='Pastilha', code='PD60')

        session = self.client.session
        session['staff_unlocked'] = True
        session.save()
        response = self.client.get('/painel/pecas/', {'category': 'filtro_ar'}, HTTP_HOST='127.0.0.1')

        self.assertContains(response, 'FAP123')
        self.assertNotContains(response, 'PD60')


class BulkCompatibilityTests(TestCase):
    def test_bulk_compatibility_links_part_to_matching_vehicles(self):
        part = Part.objects.create(category='outro', name='Filtro de oleo', code='PSL560')
        voyage = Vehicle.objects.create(
            brand='Volkswagen',
            model='Voyage 1.6',
            version='Voyage 1.6 Flex',
            year=2020,
        )
        Vehicle.objects.create(
            brand='Chevrolet',
            model='Onix',
            version='Onix LT',
            year=2020,
        )
        session = self.client.session
        session['staff_unlocked'] = True
        session.save()

        response = self.client.post(
            '/painel/compatibilidades/lote/',
            {'part': part.pk, 'queries': 'Voyage 2020', 'action': 'apply'},
            HTTP_HOST='127.0.0.1',
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(voyage, part.compatible_vehicles.all())
