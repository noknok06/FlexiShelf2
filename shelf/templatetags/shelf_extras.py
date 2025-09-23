# shelf/templatetags/shelf_extras.py

from django import template
from django.conf import settings

register = template.Library()

@register.filter
def make_list(value):
    """数値を範囲のリストに変換する"""
    try:
        num = int(value)
        return range(num)
    except (ValueError, TypeError):
        return []

@register.filter  
def mul(value, arg):
    """乗算フィルター"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def display_width(product_width, scale=None):
    """商品の表示幅を計算する（設定から倍率を取得）"""
    try:
        if scale is None:
            scale = getattr(settings, 'SHELF_DISPLAY_SCALE', 2)
        return float(product_width) * scale
    except (ValueError, TypeError):
        return 0

@register.filter
def display_height(product_height, scale=None):
    """商品の表示高さを計算する（設定から倍率を取得）"""
    try:
        if scale is None:
            scale = getattr(settings, 'SHELF_DISPLAY_SCALE', 2)
        return float(product_height) * scale
    except (ValueError, TypeError):
        return 0

@register.filter
def to_display_scale(value):
    """cm値を表示サイズ（px）に変換する"""
    try:
        scale = getattr(settings, 'SHELF_DISPLAY_SCALE', 2)
        return float(value) * scale
    except (ValueError, TypeError):
        return 0

@register.filter
def from_display_scale(value):
    """表示サイズ（px）をcm値に変換する"""
    try:
        scale = getattr(settings, 'SHELF_DISPLAY_SCALE', 2)
        return float(value) / scale
    except (ValueError, TypeError):
        return 0