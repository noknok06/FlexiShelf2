# shelf/models.py

from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal


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
        return max(0, self.shelf.width - used_width)

    def can_fit_product(self, product, face_count=1):
        """商品が配置可能かチェック"""
        required_width = product.width * face_count
        return (product.height <= self.height and 
                required_width <= self.available_width)


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
        # 占有幅を自動計算
        self.occupied_width = self.product.width * self.face_count
        super().save(*args, **kwargs)

    def clean(self):
        """配置制約のバリデーション"""
        from django.core.exceptions import ValidationError
        
        errors = []
        
        # 高さチェック
        if self.product.height > self.segment.height:
            errors.append("商品高さが段高さを超えています")
        
        # 幅チェック
        required_width = self.product.width * self.face_count
        if self.x_position + required_width > self.shelf.width:
            errors.append("段幅を超える配置です")
        
        # 重複チェック（自分以外の配置と重複しないかチェック）
        overlapping_placements = ProductPlacement.objects.filter(
            segment=self.segment
        ).exclude(pk=self.pk if self.pk else None)
        
        for placement in overlapping_placements:
            if self._check_overlap(placement):
                errors.append(f"他の商品「{placement.product.name}」と重複しています")
                break
        
        if errors:
            raise ValidationError(errors)

    def _check_overlap(self, other_placement):
        """他の配置との重複をチェック"""
        self_start = self.x_position
        self_end = self.x_position + (self.product.width * self.face_count)
        other_start = other_placement.x_position
        other_end = other_placement.x_position + other_placement.occupied_width
        
        return not (self_end <= other_start or other_end <= self_start)


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