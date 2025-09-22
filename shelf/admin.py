# shelf/admin.py

from django.contrib import admin
from django.utils.html import format_html
from .models import Product, Shelf, ShelfSegment, ProductPlacement, ShelfTemplate


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'maker', 'jan_code', 'width', 'height', 'depth', 'price', 'is_active']
    list_filter = ['maker', 'is_active', 'created_at']
    search_fields = ['name', 'maker', 'jan_code']
    list_editable = ['price', 'is_active']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('基本情報', {
            'fields': ('name', 'maker', 'jan_code', 'price', 'is_active')
        }),
        ('サイズ情報', {
            'fields': ('width', 'height', 'depth')
        }),
        ('画像', {
            'fields': ('image',)
        }),
        ('システム情報', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_active=True)


class ShelfSegmentInline(admin.TabularInline):
    model = ShelfSegment
    extra = 0
    fields = ['level', 'height', 'y_position', 'is_active']
    readonly_fields = ['y_position']


@admin.register(Shelf)
class ShelfAdmin(admin.ModelAdmin):
    list_display = ['name', 'width', 'depth', 'total_height', 'segment_count', 'total_products', 'is_active']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at', 'segment_count', 'total_products']
    inlines = [ShelfSegmentInline]
    
    fieldsets = (
        ('基本情報', {
            'fields': ('name', 'description', 'is_active')
        }),
        ('サイズ情報', {
            'fields': ('width', 'depth', 'total_height')
        }),
        ('統計情報', {
            'fields': ('segment_count', 'total_products'),
            'classes': ('collapse',)
        }),
        ('システム情報', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


class ProductPlacementInline(admin.TabularInline):
    model = ProductPlacement
    extra = 0
    fields = ['product', 'x_position', 'face_count', 'occupied_width', 'placement_order']
    readonly_fields = ['occupied_width']
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "product":
            kwargs["queryset"] = Product.objects.filter(is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(ShelfSegment)
class ShelfSegmentAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'shelf', 'level', 'height', 'available_width', 'placement_count']
    list_filter = ['shelf', 'is_active']
    search_fields = ['shelf__name']
    readonly_fields = ['y_position', 'available_width']
    inlines = [ProductPlacementInline]
    
    def available_width(self, obj):
        return f"{obj.available_width:.1f}cm"
    available_width.short_description = '利用可能幅'
    
    def placement_count(self, obj):
        return obj.placements.count()
    placement_count.short_description = '配置商品数'


@admin.register(ProductPlacement)
class ProductPlacementAdmin(admin.ModelAdmin):
    list_display = ['shelf', 'segment', 'product', 'x_position', 'face_count', 'occupied_width']
    list_filter = ['shelf', 'segment__level', 'product__maker']
    search_fields = ['shelf__name', 'product__name']
    readonly_fields = ['occupied_width', 'created_at', 'updated_at']
    
    fieldsets = (
        ('配置情報', {
            'fields': ('shelf', 'segment', 'product')
        }),
        ('位置・数量', {
            'fields': ('x_position', 'face_count', 'occupied_width', 'placement_order')
        }),
        ('システム情報', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "product":
            kwargs["queryset"] = Product.objects.filter(is_active=True)
        elif db_field.name == "shelf":
            kwargs["queryset"] = Shelf.objects.filter(is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(ShelfTemplate)
class ShelfTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'shelf_width', 'shelf_depth', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('基本情報', {
            'fields': ('name', 'description')
        }),
        ('棚サイズ', {
            'fields': ('shelf_width', 'shelf_depth')
        }),
        ('段構成', {
            'fields': ('segment_config',),
            'description': 'JSON形式で段構成を定義します。例: {"segments": [{"level": 1, "height": 30}, {"level": 2, "height": 35}]}'
        }),
        ('システム情報', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )