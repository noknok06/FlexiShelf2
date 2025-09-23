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
def display_width(product_width, scale=10.0):
    """
    商品の表示幅を計算する（JavaScript側と統一）
    scale=10.0 : 1cm = 10px（JavaScriptのCOORD_SCALEと統一）
    """
    try:
        return float(product_width) * scale
    except (ValueError, TypeError):
        return 0

@register.filter
def cm_to_px(value):
    """cm を px に変換（COORD_SCALE = 10 で統一）"""
    try:
        return float(value) * 10.0
    except (ValueError, TypeError):
        return 0

@register.filter
def px_to_cm(value):
    """px を cm に変換（COORD_SCALE = 10 で統一）"""
    try:
        return float(value) / 10.0
    except (ValueError, TypeError):
        return 0

@register.filter
def placement_width(placement):
    """配置の表示幅を正確に計算"""
    try:
        product_width_px = float(placement.product.width) * 10.0  # cm to px
        total_width_px = product_width_px * placement.face_count
        return total_width_px
    except (AttributeError, TypeError, ValueError):
        return 0

@register.filter
def placement_position(placement):
    """配置のX座標を表示座標に変換"""
    try:
        return float(placement.x_position) * 10.0  # cm to px
    except (AttributeError, TypeError, ValueError):
        return 0
