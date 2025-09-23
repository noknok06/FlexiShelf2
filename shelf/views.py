# shelf/views.py 完全修正版

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from decimal import Decimal, ROUND_HALF_UP
import json
import logging

from .models import Shelf, ShelfSegment, Product, ProductPlacement, round_decimal
from .forms import ShelfCreateForm, ProductPlacementForm, ShelfSegmentForm

logger = logging.getLogger(__name__)


def shelf_list(request):
    """棚一覧ページ"""
    shelves = Shelf.objects.filter(is_active=True).prefetch_related('segments', 'placements')
    context = {
        'shelves': shelves,
        'title': '棚割り一覧'
    }
    return render(request, 'shelf/shelf_list.html', context)


def shelf_detail(request, shelf_id):
    """棚詳細・棚割り編集ページ"""
    shelf = get_object_or_404(Shelf, id=shelf_id, is_active=True)
    segments = shelf.segments.filter(is_active=True).order_by('level').prefetch_related('placements__product')
    products = Product.objects.filter(is_active=True).order_by('name')
    
    context = {
        'shelf': shelf,
        'segments': segments,
        'products': products,
        'title': f'棚割り編集 - {shelf.name}'
    }
    return render(request, 'shelf/shelf_detail.html', context)


def shelf_create(request):
    """棚新規作成ページ"""
    if request.method == 'POST':
        form = ShelfCreateForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # 棚を作成
                    shelf = form.save()
                    
                    # 段を作成（デフォルトで4段）
                    segment_heights = [30, 35, 35, 40]  # デフォルトの段高さ
                    y_pos = 0
                    
                    for level, height in enumerate(segment_heights, 1):
                        ShelfSegment.objects.create(
                            shelf=shelf,
                            level=level,
                            height=height,
                            y_position=y_pos
                        )
                        y_pos += height
                    
                    messages.success(request, f'棚「{shelf.name}」を作成しました。')
                    return redirect('shelf:detail', shelf_id=shelf.id)
            except Exception as e:
                messages.error(request, f'棚の作成に失敗しました: {str(e)}')
    else:
        form = ShelfCreateForm()
    
    context = {
        'form': form,
        'title': '新しい棚を作成'
    }
    return render(request, 'shelf/shelf_create.html', context)


@csrf_exempt
@require_http_methods(["POST"])
def place_product_ajax(request):
    """商品配置のAjax処理（完全修正版）"""
    try:
        data = json.loads(request.body)
        shelf_id = data.get('shelf_id')
        segment_id = data.get('segment_id')
        product_id = data.get('product_id')
        x_position = round_decimal(float(data.get('x_position', 0)))
        face_count = int(data.get('face_count', 1))
        
        logger.debug(f"配置リクエスト: 商品ID={product_id}, 段ID={segment_id}, X={x_position}cm, フェース={face_count}")
        
        shelf = get_object_or_404(Shelf, id=shelf_id)
        segment = get_object_or_404(ShelfSegment, id=segment_id, shelf=shelf)
        product = get_object_or_404(Product, id=product_id)
        
        # 配置可能かチェック
        required_width = product.get_occupied_width(face_count)
        if not segment.can_fit_product(product, face_count):
            return JsonResponse({
                'success': False, 
                'error': f'商品を配置できません（段高さ: {segment.height}cm < 商品高さ: {product.height}cm または 利用可能幅: {segment.available_width}cm < 必要幅: {required_width}cm）'
            })
        
        # 座標の正規化と範囲チェック
        start_x = max(0, x_position)
        end_x = round_decimal(start_x + required_width)
        
        # 棚幅チェック
        if end_x > shelf.width:
            return JsonResponse({
                'success': False,
                'error': f'棚幅を超えています（配置範囲: {start_x:.1f}-{end_x:.1f}cm, 棚幅: {shelf.width}cm）'
            })
        
        # 重複チェック（新しいロジック）
        existing_ranges = segment.get_placement_ranges()
        for range_info in existing_ranges:
            existing_start = range_info['start']
            existing_end = range_info['end']
            existing_placement = range_info['placement']
            
            # 許容誤差0.05cmで重複判定
            tolerance = 0.05
            if (end_x > existing_start + tolerance) and (start_x < existing_end - tolerance):
                logger.warning(f"重複検出: 新配置[{start_x:.1f}-{end_x:.1f}] vs 既存[{existing_start:.1f}-{existing_end:.1f}] ({existing_placement.product.name})")
                return JsonResponse({
                    'success': False,
                    'error': f'商品「{existing_placement.product.name}」と重複する位置です（新配置: {start_x:.1f}-{end_x:.1f}cm, 既存: {existing_start:.1f}-{existing_end:.1f}cm）'
                })
        
        # 配置順序を設定
        max_order_result = ProductPlacement.objects.filter(segment=segment).aggregate(
            max_order=Max('placement_order')
        )
        max_order = max_order_result['max_order'] or 0
        
        # 商品を配置
        placement = ProductPlacement.objects.create(
            shelf=shelf,
            segment=segment,
            product=product,
            x_position=start_x,
            face_count=face_count,
            placement_order=max_order + 1
        )
        
        logger.info(f"商品配置成功: {product.name} 段{segment.level} X={start_x:.1f}cm 幅={placement.occupied_width:.1f}cm フェース={face_count}")
        
        return JsonResponse({
            'success': True,
            'placement_id': placement.id,
            'message': f'{product.name} を配置しました（位置: {start_x:.1f}cm, {face_count}フェース）',
            'debug_info': {
                'x_position': start_x,
                'end_position': end_x,
                'occupied_width': placement.occupied_width,
                'face_count': face_count
            }
        })
        
    except Exception as e:
        logger.error(f"配置エラー: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'配置エラー: {str(e)}'
        })


@csrf_exempt
@require_http_methods(["POST"])
def update_placement_ajax(request):
    """商品配置更新のAjax処理（完全修正版）"""
    try:
        data = json.loads(request.body)
        placement_id = data.get('placement_id')
        x_position = data.get('x_position')
        face_count = data.get('face_count')
        face_count_change = data.get('face_count_change')
        segment_id = data.get('segment_id')
        
        placement = get_object_or_404(ProductPlacement, id=placement_id)
        
        logger.debug(f"配置更新リクエスト: ID={placement_id}, X={x_position}, フェース={face_count}, 変更={face_count_change}, 段={segment_id}")
        
        # 段間移動の場合
        if segment_id is not None:
            new_segment = get_object_or_404(ShelfSegment, id=segment_id, shelf=placement.shelf)
            
            # 新しい段に移動可能かチェック
            if not new_segment.can_fit_product(placement.product, placement.face_count):
                return JsonResponse({
                    'success': False,
                    'error': f'段{new_segment.level}には商品が収まりません（段高さ: {new_segment.height}cm < 商品高さ: {placement.product.height}cm）'
                })
            
            placement.segment = new_segment
            logger.debug(f"段移動: 段{placement.segment.level} → 段{new_segment.level}")
        
        # 新しい値を決定
        if x_position is not None:
            new_x_position = round_decimal(float(x_position))
        else:
            new_x_position = placement.x_position
            
        if face_count is not None:
            new_face_count = max(1, min(10, int(face_count)))
        elif face_count_change is not None:
            new_face_count = max(1, min(10, placement.face_count + int(face_count_change)))
        else:
            new_face_count = placement.face_count
        
        # 新しい配置での制約チェック
        new_required_width = placement.product.get_occupied_width(new_face_count)
        new_end_x = round_decimal(new_x_position + new_required_width)
        
        # 棚幅チェック
        if new_end_x > placement.shelf.width:
            return JsonResponse({
                'success': False,
                'error': f'棚幅を超えています（配置範囲: {new_x_position:.1f}-{new_end_x:.1f}cm, 棚幅: {placement.shelf.width}cm）'
            })
        
        # 重複チェック（自分以外との重複）
        existing_ranges = placement.segment.get_placement_ranges(exclude_placement=placement)
        for range_info in existing_ranges:
            existing_start = range_info['start']
            existing_end = range_info['end']
            existing_placement = range_info['placement']
            
            tolerance = 0.05
            if (new_end_x > existing_start + tolerance) and (new_x_position < existing_end - tolerance):
                logger.warning(f"更新時重複検出: 新位置[{new_x_position:.1f}-{new_end_x:.1f}] vs 既存[{existing_start:.1f}-{existing_end:.1f}] ({existing_placement.product.name})")
                return JsonResponse({
                    'success': False,
                    'error': f'商品「{existing_placement.product.name}」と重複します（移動先: {new_x_position:.1f}-{new_end_x:.1f}cm, 既存: {existing_start:.1f}-{existing_end:.1f}cm）'
                })
        
        # 安全な更新実行
        success, error_message = placement.update_position(new_x_position, new_face_count)
        
        if success:
            return JsonResponse({
                'success': True,
                'message': f'配置を更新しました（位置: {placement.x_position:.1f}cm, {placement.face_count}フェース）',
                'new_face_count': placement.face_count,
                'debug_info': {
                    'final_position': f'{placement.x_position:.1f}-{placement.get_end_position():.1f}cm',
                    'occupied_width': placement.occupied_width,
                    'face_count': placement.face_count
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'error': error_message or '配置の更新に失敗しました'
            })
        
    except Exception as e:
        logger.error(f"配置更新エラー: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'更新エラー: {str(e)}'
        })


@csrf_exempt
@require_http_methods(["POST"])
def delete_placement_ajax(request):
    """商品配置削除のAjax処理"""
    try:
        data = json.loads(request.body)
        placement_id = data.get('placement_id')
        
        placement = get_object_or_404(ProductPlacement, id=placement_id)
        product_name = placement.product.name
        
        logger.info(f"配置削除: {product_name} (ID={placement_id})")
        placement.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'商品「{product_name}」を削除しました'
        })
        
    except Exception as e:
        logger.error(f"削除エラー: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'削除エラー: {str(e)}'
        })


def shelf_segment_edit(request, shelf_id):
    """段高さ編集ページ"""
    shelf = get_object_or_404(Shelf, id=shelf_id, is_active=True)
    segments = shelf.segments.filter(is_active=True).order_by('level')
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                y_pos = 0
                updated_segments = []
                
                for segment in segments:
                    height_key = f'height_{segment.id}'
                    if height_key in request.POST:
                        new_height = float(request.POST.get(height_key, segment.height))
                        
                        # 配置済み商品の高さチェック
                        max_height_result = segment.placements.aggregate(
                            max_height=Max('product__height')
                        )
                        max_product_height = max_height_result['max_height'] or 0
                        
                        if new_height < max_product_height:
                            messages.error(
                                request, 
                                f'段{segment.level}には高さ{max_product_height}cmの商品が配置されているため、'
                                f'{new_height}cmに変更できません。'
                            )
                            return render(request, 'shelf/shelf_segment_edit.html', {
                                'shelf': shelf,
                                'segments': segments,
                                'title': f'段高さ編集 - {shelf.name}'
                            })
                        
                        segment.height = new_height
                        segment.y_position = y_pos
                        segment.save()
                        updated_segments.append(f'段{segment.level}: {new_height}cm')
                        y_pos += new_height
                
                messages.success(request, f'段高さを更新しました: {", ".join(updated_segments)}')
                return redirect('shelf:detail', shelf_id=shelf.id)
                
        except Exception as e:
            logger.error(f"段高さ更新エラー: {str(e)}", exc_info=True)
            messages.error(request, f'段高さの更新に失敗しました: {str(e)}')
    
    context = {
        'shelf': shelf,
        'segments': segments,
        'title': f'段高さ編集 - {shelf.name}'
    }
    return render(request, 'shelf/shelf_segment_edit.html', context)


def product_search_ajax(request):
    """商品検索のAjax処理"""
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'products': []})
    
    products = Product.objects.filter(
        name__icontains=query,
        is_active=True
    ).values('id', 'name', 'maker', 'width', 'height', 'price')[:20]
    
    return JsonResponse({'products': list(products)})


@csrf_exempt  
@require_http_methods(["POST"])
def clear_all_placements_ajax(request):
    """すべての商品配置を削除するAjax処理"""
    try:
        data = json.loads(request.body)
        shelf_id = data.get('shelf_id')
        
        shelf = get_object_or_404(Shelf, id=shelf_id)
        deleted_count = ProductPlacement.objects.filter(shelf=shelf).count()
        
        logger.info(f"全配置削除: 棚「{shelf.name}」から{deleted_count}個の配置を削除")
        ProductPlacement.objects.filter(shelf=shelf).delete()
        
        return JsonResponse({
            'success': True,
            'message': f'{deleted_count}個の商品配置を削除しました'
        })
        
    except Exception as e:
        logger.error(f"全削除エラー: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'削除エラー: {str(e)}'
        })


def debug_placement_info(request, shelf_id):
    """デバッグ用：配置情報の詳細表示"""
    if not request.user.is_staff:  # スタッフユーザーのみ
        return JsonResponse({'error': 'Permission denied'})
    
    shelf = get_object_or_404(Shelf, id=shelf_id)
    segments_info = []
    
    for segment in shelf.segments.all():
        placements_info = []
        for placement in segment.placements.all():
            placements_info.append({
                'id': placement.id,
                'product_name': placement.product.name,
                'product_width': placement.product.width,
                'x_position': placement.x_position,
                'face_count': placement.face_count,
                'occupied_width': placement.occupied_width,
                'calculated_width': placement.product.get_occupied_width(placement.face_count),
                'end_position': placement.get_end_position(),
                'range': f'{placement.x_position:.1f}-{placement.get_end_position():.1f}cm'
            })
        
        segments_info.append({
            'level': segment.level,
            'height': segment.height,
            'available_width': segment.available_width,
            'placements': placements_info
        })
    
    return JsonResponse({
        'shelf_name': shelf.name,
        'shelf_width': shelf.width,
        'segments': segments_info
    })