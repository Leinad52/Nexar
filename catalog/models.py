from django.db import models


class Vehicle(models.Model):
    brand = models.CharField('marca', max_length=80)
    model = models.CharField('modelo', max_length=120)
    version = models.CharField('versao', max_length=160)
    year = models.PositiveIntegerField('ano')
    engine = models.CharField('motor', max_length=40, blank=True)
    fuel = models.CharField('combustivel', max_length=40, blank=True)
    fipe_code = models.CharField('codigo FIPE', max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['brand', 'model', 'version', 'year']
        unique_together = [('brand', 'model', 'version', 'year', 'engine')]

    def __str__(self):
        return f'{self.brand} {self.model} {self.version} {self.year}'


class Category(models.Model):
    name = models.CharField('nome', max_length=80, unique=True)
    slug = models.SlugField('identificador', max_length=80, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'categoria'
        verbose_name_plural = 'categorias'

    def __str__(self):
        return self.name


class Part(models.Model):
    category = models.CharField('categoria', max_length=80)
    name = models.CharField('nome', max_length=140)
    brand = models.CharField('marca da peca', max_length=100, blank=True)
    code = models.CharField('codigo', max_length=80)
    notes = models.TextField('observacoes', blank=True)
    compatible_vehicles = models.ManyToManyField(
        Vehicle,
        related_name='compatible_parts',
        verbose_name='modelos compativeis',
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'brand', 'code']
        unique_together = [('brand', 'code')]

    def __str__(self):
        maker = f'{self.brand} ' if self.brand else ''
        return f'{maker}{self.code} - {self.name}'

    @property
    def category_label(self):
        category = Category.objects.filter(slug=self.category).first()
        return category.name if category else self.category.replace('_', ' ').title()
