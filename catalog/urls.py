from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('painel/', views.staff_dashboard, name='staff_dashboard'),
    path('painel/entrar/', views.staff_login, name='staff_login'),
    path('painel/sair/', views.staff_logout, name='staff_logout'),
    path('painel/categorias/', views.category_list, name='category_list'),
    path('painel/categorias/nova/', views.category_create, name='category_create'),
    path('painel/categorias/<int:pk>/editar/', views.category_edit, name='category_edit'),
    path('painel/categorias/<int:pk>/excluir/', views.category_delete, name='category_delete'),
    path('painel/modelos/', views.vehicle_list, name='vehicle_list'),
    path('painel/pecas/', views.part_list, name='part_list'),
    path('painel/compatibilidades/lote/', views.bulk_compatibility, name='bulk_compatibility'),
    path('painel/pecas/importar-xml/', views.import_parts_xml, name='import_parts_xml'),
    path('painel/veiculos/novo/', views.vehicle_create, name='vehicle_create'),
    path('painel/veiculos/<int:pk>/editar/', views.vehicle_edit, name='vehicle_edit'),
    path('painel/veiculos/<int:pk>/excluir/', views.vehicle_delete, name='vehicle_delete'),
    path('painel/pecas/nova/', views.part_create, name='part_create'),
    path('painel/pecas/<int:pk>/editar/', views.part_edit, name='part_edit'),
    path('painel/pecas/<int:pk>/excluir/', views.part_delete, name='part_delete'),
]
