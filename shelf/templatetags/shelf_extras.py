# shelf/templatetags/__init__.py
# 空ファイル

# shelf/templatetags/shelf_extras.py

from django import template

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
def display_width(product_width, scale=2.5):
    """商品の表示幅を計算する"""
    try:
        return float(product_width) * scale
    except (ValueError, TypeError):
        return 0