# shelf/models.py 完全修正版

from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal, ROUND_HALF_UP
import logging

logger = logging.getLogger(__name__)

def round_decimal(value, precision=1):
    """Decimalで正確な四捨五入を行う"""
    return float(Decimal(str(value)).quantize(Decimal(f'0.{"0" * precision}'), rounding=ROUND_HALF_UP))


class Product(models.Model):
    """商品マスタ（最小限の情報のみ）"""
    name = models.CharField('商品名', max_length=100)
    maker = models.CharField('メーカー', max_length=50, blank=True)
    jan_code = models.CharField('JANコード', max_length=13, unique=True, blank=True, null=True)
    width = models.FloatField('幅(cm)', validators=[MinValueValidator(0.1)])
    height = models.FloatField('高さ(cm)', validators=[MinValueValidator(0.1)])
    depth = models.FloatField('奥行(cm)', validators=[MinValueValidator(0.1)])
    price = models.DecimalField('価格', max_digits=8, decimal_places=2, default=Decimal('0.00'))
    image = models.ImageField('商品画像', upload_to='products/', blank=True, null=True)
    is_active = models.BooleanField('有効', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '商品'
        verbose_name_plural = '商品一覧'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.maker})" if self.maker else self.name

    def get_occupied_width(self, face_count=1):
        """指定フェース数での占有幅を正確に計算"""
        return round_decimal(self.width * face_count)


class Shelf(models.Model):
    """棚マスタ"""
    name = models.CharField('棚名', max_length=100)
    width = models.FloatField('幅(cm)', validators=[MinValueValidator(10.0)])
    depth = models.FloatField('奥行(cm)', validators=[MinValueValidator(10.0)])
    total_height = models.FloatField('総高さ(cm)', validators=[MinValueValidator(10.0)])
    description = models.TextField('説明', blank=True)
    is_active = models.BooleanField('有効', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '棚'
        verbose_name_plural = '棚一覧'
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def segment_count(self):
        """段数を返す"""
        return self.segments.count()

    @property
    def total_products(self):
        """配置されている商品の総数を返す"""
        return sum(placement.face_count for placement in self.placements.all())


class ShelfSegment(models.Model):
    """棚の段"""
    shelf = models.ForeignKey(Shelf, on_delete=models.CASCADE, related_name='segments')
    level = models.IntegerField('段番号', validators=[MinValueValidator(1)])
    height = models.FloatField('段高さ(cm)', validators=[MinValueValidator(5.0)])
    y_position = models.FloatField('床からの位置(cm)', validators=[MinValueValidator(0.0)])
    is_active = models.BooleanField('有効', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '棚段'
        verbose_name_plural = '棚段一覧'
        ordering = ['shelf', 'level']
        unique_together = ['shelf', 'level']

    def __str__(self):
        return f"{self.shelf.name} - 段{self.level}"

    @property
    def available_width(self):
        """この段の利用可能な幅を返す"""
        used_width = sum(placement.occupied_width for placement in self.placements.all())
        return max(0, round_decimal(self.shelf.width - used_width))

    def can_fit_product(self, product, face_count=1):
        """商品が配置可能かチェック"""
        required_width = product.get_occupied_width(face_count)
        return (product.height <= self.height and 
                required_width <= self.available_width)

    def get_placement_ranges(self, exclude_placement=None):
        """この段の全ての配置範囲を取得（重複チェック用）"""
        placements = self.placements.all()
        if exclude_placement:
            placements = placements.exclude(pk=exclude_placement.pk)
        
        ranges = []
        for placement in placements:
            start = round_decimal(placement.x_position)
            end = round_decimal(start + placement.occupied_width)
            ranges.append({
                'start': start,
                'end': end,
                'placement': placement
            })
        
        logger.debug(f"段{self.level}の配置範囲: {ranges}")
        return ranges


class ProductPlacement(models.Model):
    """商品配置"""
    shelf = models.ForeignKey(Shelf, on_delete=models.CASCADE, related_name='placements')
    segment = models.ForeignKey(ShelfSegment, on_delete=models.CASCADE, related_name='placements')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    x_position = models.FloatField('X座標(cm)', validators=[MinValueValidator(0.0)])
    face_count = models.IntegerField('フェース数', default=1, validators=[MinValueValidator(1)])
    occupied_width = models.FloatField('占有幅(cm)', validators=[MinValueValidator(0.1)])
    placement_order = models.IntegerField('配置順序', default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '商品配置'
        verbose_name_plural = '商品配置一覧'
        ordering = ['shelf', 'segment__level', 'placement_order']

    def __str__(self):
        return f"{self.shelf.name} - {self.product.name} (×{self.face_count})"

    def save(self, *args, **kwargs):
        # X座標と占有幅を正確に計算
        self.x_position = round_decimal(self.x_position)
        self.occupied_width = self.product.get_occupied_width(self.face_count)
        
        logger.debug(f"配置保存: {self.product.name} X={self.x_position}cm 幅={self.occupied_width}cm フェース={self.face_count}")
        
        super().save(*args, **kwargs)

    def clean(self):
        """配置制約のバリデーション（完全修正版）"""
        errors = []
        
        # 基本的な値の正規化
        if hasattr(self, 'x_position'):
            self.x_position = round_decimal(self.x_position)
        
        # 高さチェック
        if self.product.height > self.segment.height:
            errors.append("商品高さが段高さを超えています")
        
        # 占有幅を正確に計算
        required_width = self.product.get_occupied_width(self.face_count)
        end_position = round_decimal(self.x_position + required_width)
        
        # 棚幅チェック
        if end_position > self.shelf.width:
            errors.append(f"段幅を超える配置です (配置範囲: {self.x_position:.1f}-{end_position:.1f}cm, 棚幅: {self.shelf.width}cm)")
        
        # 重複チェック（修正版）
        overlapping_placement = self._find_overlapping_placement()
        if overlapping_placement:
            errors.append(f"他の商品「{overlapping_placement.product.name}」と重複しています")
        
        if errors:
            raise ValidationError(errors)

    def _find_overlapping_placement(self, tolerance=0.05):
        """重複する配置を検索（許容誤差あり）"""
        self_start = round_decimal(self.x_position)
        self_end = round_decimal(self_start + self.product.get_occupied_width(self.face_count))
        
        # 自分以外の配置をチェック
        other_placements = ProductPlacement.objects.filter(
            segment=self.segment
        ).exclude(pk=self.pk if self.pk else None)
        
        for other_placement in other_placements:
            other_start = round_decimal(other_placement.x_position)
            other_end = round_decimal(other_start + other_placement.occupied_width)
            
            # 許容誤差を考慮した重複判定
            is_overlapping = (
                (self_end > other_start + tolerance) and 
                (self_start < other_end - tolerance)
            )
            
            logger.debug(f"重複チェック: {self.product.name}[{self_start:.1f}-{self_end:.1f}] vs {other_placement.product.name}[{other_start:.1f}-{other_end:.1f}] -> {is_overlapping}")
            
            if is_overlapping:
                return other_placement
        
        return None

    def get_end_position(self):
        """配置の終了位置を取得"""
        return round_decimal(self.x_position + self.occupied_width)

    def update_position(self, new_x_position, new_face_count=None):
        """位置とフェース数を安全に更新"""
        old_x = self.x_position
        old_face_count = self.face_count
        
        try:
            # 新しい値を設定
            self.x_position = round_decimal(new_x_position)
            if new_face_count is not None:
                self.face_count = max(1, int(new_face_count))
            
            # バリデーション実行
            self.clean()
            self.save()
            
            logger.info(f"配置更新成功: {self.product.name} {old_x:.1f}→{self.x_position:.1f}cm フェース{old_face_count}→{self.face_count}")
            return True, None
            
        except ValidationError as e:
            # エラー時は元の値に戻す
            self.x_position = old_x
            self.face_count = old_face_count
            error_message = '; '.join(e.messages) if hasattr(e, 'messages') else str(e)
            logger.warning(f"配置更新失敗: {self.product.name} - {error_message}")
            return False, error_message
        except Exception as e:
            # 予期しないエラー
            self.x_position = old_x
            self.face_count = old_face_count
            logger.error(f"配置更新エラー: {self.product.name} - {str(e)}")
            return False, f"更新エラー: {str(e)}"


class ShelfTemplate(models.Model):
    """棚割りテンプレート"""
    name = models.CharField('テンプレート名', max_length=100)
    description = models.TextField('説明', blank=True)
    shelf_width = models.FloatField('棚幅(cm)')
    shelf_depth = models.FloatField('棚奥行(cm)')
    segment_config = models.JSONField('段構成', default=dict)  # 段数と高さの設定
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '棚テンプレート'
        verbose_name_plural = '棚テンプレート一覧'
        ordering = ['name']

    def __str__(self):
        return self.name