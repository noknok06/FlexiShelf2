# shelf/services.py

from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Shelf, ShelfSegment, Product, ProductPlacement
import logging

logger = logging.getLogger(__name__)


class ShelfService:
    """棚関連のビジネスロジックを管理するサービスクラス"""
    
    @staticmethod
    @transaction.atomic
    def create_shelf_with_segments(shelf_data, segment_heights=None):
        """
        棚と段を一括で作成する
        
        Args:
            shelf_data (dict): 棚の基本データ
            segment_heights (list): 段の高さリスト（デフォルト: [30, 35, 35, 40]）
        
        Returns:
            Shelf: 作成された棚オブジェクト
        """
        if segment_heights is None:
            segment_heights = [30, 35, 35, 40]  # デフォルト4段
        
        try:
            # 棚を作成
            shelf = Shelf.objects.create(**shelf_data)
            
            # 段を作成
            y_position = 0
            for level, height in enumerate(segment_heights, 1):
                ShelfSegment.objects.create(
                    shelf=shelf,
                    level=level,
                    height=height,
                    y_position=y_position
                )
                y_position += height
            
            logger.info(f"棚「{shelf.name}」を{len(segment_heights)}段で作成しました")
            return shelf
            
        except Exception as e:
            logger.error(f"棚作成エラー: {str(e)}")
            raise
    
    @staticmethod
    @transaction.atomic
    def update_segment_heights(shelf, height_data):
        """
        段の高さを一括更新する
        
        Args:
            shelf (Shelf): 対象の棚
            height_data (dict): {segment_id: new_height} の辞書
        
        Returns:
            bool: 更新成功可否
        """
        try:
            segments = shelf.segments.filter(is_active=True).order_by('level')
            y_position = 0
            
            for segment in segments:
                if segment.id in height_data:
                    new_height = float(height_data[segment.id])
                    
                    # 配置済み商品の高さチェック
                    max_product_height = segment.placements.aggregate(
                        max_height=models.Max('product__height')
                    )['max_height'] or 0
                    
                    if new_height < max_product_height:
                        raise ValidationError(
                            f"段{segment.level}には高さ{max_product_height}cmの商品が配置されているため、"
                            f"{new_height}cmに変更できません"
                        )
                    
                    segment.height = new_height
                
                segment.y_position = y_position
                segment.save()
                y_position += segment.height
            
            logger.info(f"棚「{shelf.name}」の段高さを更新しました")
            return True
            
        except Exception as e:
            logger.error(f"段高さ更新エラー: {str(e)}")
            raise


class ProductPlacementService:
    """商品配置関連のビジネスロジックを管理するサービスクラス"""
    
    @staticmethod
    def validate_placement(shelf, segment, product, x_position, face_count):
        """
        配置制約を検証する
        
        Args:
            shelf (Shelf): 対象棚
            segment (ShelfSegment): 対象段
            product (Product): 配置商品
            x_position (float): X座標
            face_count (int): フェース数
        
        Returns:
            list: エラーメッセージのリスト（空リスト=エラーなし）
        """
        errors = []
        
        try:
            # 高さ制約チェック
            if product.height > segment.height:
                errors.append(f"商品高さ({product.height}cm)が段高さ({segment.height}cm)を超えています")
            
            # 占有幅計算
            occupied_width = product.width * face_count
            
            # 幅制約チェック
            if x_position + occupied_width > shelf.width:
                errors.append(f"配置位置が棚幅を超えています（必要幅: {occupied_width}cm, 棚幅: {shelf.width}cm）")
            
            # X座標チェック
            if x_position < 0:
                errors.append("X座標は0以上である必要があります")
            
            # 重複チェック
            overlapping_placements = ProductPlacement.objects.filter(
                segment=segment,
                x_position__lt=x_position + occupied_width,
                x_position__gte=x_position - occupied_width
            )
            
            for placement in overlapping_placements:
                placement_end = placement.x_position + placement.occupied_width
                if not (x_position >= placement_end or x_position + occupied_width <= placement.x_position):
                    errors.append(f"商品「{placement.product.name}」と重複します")
                    break
            
            # フェース数制約
            if face_count < 1:
                errors.append("フェース数は1以上である必要があります")
            elif face_count > 20:
                errors.append("フェース数は20以下である必要があります")
            
        except Exception as e:
            logger.error(f"配置検証エラー: {str(e)}")
            errors.append("配置検証中にエラーが発生しました")
        
        return errors
    
    @staticmethod
    @transaction.atomic
    def place_product(shelf, segment, product, x_position, face_count):
        """
        商品を配置する
        
        Args:
            shelf (Shelf): 対象棚
            segment (ShelfSegment): 対象段
            product (Product): 配置商品
            x_position (float): X座標
            face_count (int): フェース数
        
        Returns:
            ProductPlacement: 作成された配置オブジェクト
        
        Raises:
            ValidationError: 配置制約違反時
        """
        # 事前検証
        errors = ProductPlacementService.validate_placement(
            shelf, segment, product, x_position, face_count
        )
        
        if errors:
            raise ValidationError(errors)
        
        try:
            # 配置順序の決定
            max_order = ProductPlacement.objects.filter(segment=segment).aggregate(
                max_order=models.Max('placement_order')
            )['max_order'] or 0
            
            # 配置オブジェクト作成
            placement = ProductPlacement.objects.create(
                shelf=shelf,
                segment=segment,
                product=product,
                x_position=x_position,
                face_count=face_count,
                placement_order=max_order + 1
            )
            
            logger.info(f"商品「{product.name}」を棚「{shelf.name}」段{segment.level}に配置しました")
            return placement
            
        except Exception as e:
            logger.error(f"商品配置エラー: {str(e)}")
            raise
    
    @staticmethod
    @transaction.atomic
    def move_placement(placement, new_x_position, new_face_count=None):
        """
        配置済み商品を移動する
        
        Args:
            placement (ProductPlacement): 対象配置
            new_x_position (float): 新しいX座標
            new_face_count (int, optional): 新しいフェース数
        
        Returns:
            ProductPlacement: 更新された配置オブジェクト
        """
        if new_face_count is None:
            new_face_count = placement.face_count
        
        # 一時的に配置を無効化して検証
        old_x_position = placement.x_position
        old_face_count = placement.face_count
        
        try:
            # 検証用に一時的に削除
            placement_id = placement.id
            placement.delete()
            
            # 新しい位置での検証
            errors = ProductPlacementService.validate_placement(
                placement.shelf, placement.segment, placement.product,
                new_x_position, new_face_count
            )
            
            if errors:
                # エラーがある場合は元に戻す
                ProductPlacement.objects.create(
                    id=placement_id,
                    shelf=placement.shelf,
                    segment=placement.segment,
                    product=placement.product,
                    x_position=old_x_position,
                    face_count=old_face_count,
                    placement_order=placement.placement_order
                )
                raise ValidationError(errors)
            
            # 問題なければ新しい位置で作成
            new_placement = ProductPlacement.objects.create(
                shelf=placement.shelf,
                segment=placement.segment,
                product=placement.product,
                x_position=new_x_position,
                face_count=new_face_count,
                placement_order=placement.placement_order
            )
            
            logger.info(f"商品「{placement.product.name}」の配置を移動しました")
            return new_placement
            
        except Exception as e:
            logger.error(f"配置移動エラー: {str(e)}")
            raise


class ShelfAnalysisService:
    """棚分析関連のサービス"""
    
    @staticmethod
    def calculate_space_utilization(shelf):
        """
        棚のスペース利用率を計算する
        
        Args:
            shelf (Shelf): 対象棚
        
        Returns:
            dict: 利用率情報
        """
        total_shelf_area = shelf.width * shelf.depth
        segments = shelf.segments.filter(is_active=True)
        
        utilization_data = {
            'total_area': total_shelf_area,
            'segments': [],
            'overall_utilization': 0.0
        }
        
        total_used_area = 0
        total_available_area = 0
        
        for segment in segments:
            segment_area = shelf.width * shelf.depth  # 段あたりの面積
            used_width = sum(placement.occupied_width for placement in segment.placements.all())
            used_area = used_width * shelf.depth
            utilization_rate = (used_area / segment_area) * 100 if segment_area > 0 else 0
            
            segment_data = {
                'level': segment.level,
                'total_area': segment_area,
                'used_area': used_area,
                'utilization_rate': utilization_rate,
                'product_count': segment.placements.count(),
                'available_width': segment.available_width
            }
            
            utilization_data['segments'].append(segment_data)
            total_used_area += used_area
            total_available_area += segment_area
        
        # 全体の利用率
        if total_available_area > 0:
            utilization_data['overall_utilization'] = (total_used_area / total_available_area) * 100
        
        return utilization_data
    
    @staticmethod
    def get_placement_statistics(shelf):
        """
        配置統計情報を取得する
        
        Args:
            shelf (Shelf): 対象棚
        
        Returns:
            dict: 統計情報
        """
        placements = ProductPlacement.objects.filter(shelf=shelf)
        
        stats = {
            'total_products': placements.count(),
            'total_face_count': sum(p.face_count for p in placements),
            'unique_products': placements.values('product').distinct().count(),
            'segments_used': placements.values('segment').distinct().count(),
            'average_face_count': 0.0,
            'most_placed_products': [],
        }
        
        if stats['total_products'] > 0:
            stats['average_face_count'] = stats['total_face_count'] / stats['total_products']
        
        # 最も多く配置されている商品
        from django.db.models import Count, Sum
        most_placed = placements.values('product__name', 'product__maker').annotate(
            total_faces=Sum('face_count'),
            placement_count=Count('id')
        ).order_by('-total_faces')[:5]
        
        stats['most_placed_products'] = list(most_placed)
        
        return stats