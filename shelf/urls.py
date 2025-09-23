# shelf/urls.py

from django.urls import path
from . import views

app_name = 'shelf'

urlpatterns = [
    # 既存のURL...
    path('', views.shelf_list, name='list'),
    path('create/', views.shelf_create, name='create'),
    path('<int:shelf_id>/', views.shelf_detail, name='detail'),
    path('<int:shelf_id>/segments/edit/', views.shelf_segment_edit, name='segment_edit'),
    
    # Ajax API
    path('ajax/place-product/', views.place_product_ajax, name='place_product_ajax'),
    path('ajax/update-placement/', views.update_placement_ajax, name='update_placement_ajax'),
    path('ajax/delete-placement/', views.delete_placement_ajax, name='delete_placement_ajax'),
    path('ajax/search-products/', views.product_search_ajax, name='product_search_ajax'),
    path('ajax/clear-all-placements/', views.clear_all_placements_ajax, name='clear_all_placements_ajax'),
    
    # デバッグ用URL（本番では削除またはスタッフ限定にする）
    path('debug/<int:shelf_id>/', views.debug_placement_info, name='debug_placement_info'),
]
