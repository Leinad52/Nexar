from django.contrib import admin

from .models import Category, Part, Vehicle


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name', 'slug')


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('brand', 'model', 'version', 'year', 'engine', 'fuel')
    search_fields = ('brand', 'model', 'version')


@admin.register(Part)
class PartAdmin(admin.ModelAdmin):
    list_display = ('category', 'brand', 'code', 'name')
    list_filter = ('category', 'brand')
    search_fields = ('brand', 'code', 'name')
    filter_horizontal = ('compatible_vehicles',)

# Register your models here.
