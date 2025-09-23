# shelf/forms.py

from django import forms
from django.core.validators import MinValueValidator
from django.conf import settings
from .models import Shelf, ShelfSegment, ProductPlacement, Product


class ShelfCreateForm(forms.ModelForm):
    """棚作成フォーム"""
    
    class Meta:
        model = Shelf
        fields = ['name', 'width', 'depth', 'total_height', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '例: エンド陳列棚A'
            }),
            'width': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '120.0',
                'step': '0.1',
                'min': '10.0'
            }),
            'depth': forms.NumberInput(attrs={
                'class': 'form-control', 
                'placeholder': '40.0',
                'step': '0.1',
                'min': '10.0'
            }),
            'total_height': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '180.0',
                'step': '0.1',
                'min': '50.0'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': '棚の説明や設置場所を入力'
            }),
        }
        
    def clean_width(self):
        width = self.cleaned_data['width']
        if width < 30.0:
            raise forms.ValidationError('棚幅は30cm以上である必要があります。')
        if width > 300.0:
            raise forms.ValidationError('棚幅は300cm以下である必要があります。')
        return width
    
    def clean_total_height(self):
        height = self.cleaned_data['total_height']
        if height < 80.0:
            raise forms.ValidationError('棚高さは80cm以上である必要があります。')
        if height > 250.0:
            raise forms.ValidationError('棚高さは250cm以下である必要があります。')
        return height


class ShelfSegmentForm(forms.ModelForm):
    """段編集フォーム"""
    
    class Meta:
        model = ShelfSegment
        fields = ['height']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 設定から段高さの制限を取得
        min_height = getattr(settings, 'SHELF_SETTINGS', {}).get('MIN_SEGMENT_HEIGHT', 15.0)
        max_height = getattr(settings, 'SHELF_SETTINGS', {}).get('MAX_SEGMENT_HEIGHT', 60.0)
        
        self.fields['height'] = forms.FloatField(
            widget=forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'min': str(min_height),
                'max': str(max_height)
            }),
            min_value=min_height,
            max_value=max_height,
            label='段高さ (cm)'
        )
    
    def clean_height(self):
        height = self.cleaned_data['height']
        min_height = getattr(settings, 'SHELF_SETTINGS', {}).get('MIN_SEGMENT_HEIGHT', 15.0)
        max_height = getattr(settings, 'SHELF_SETTINGS', {}).get('MAX_SEGMENT_HEIGHT', 60.0)
        
        if height < min_height:
            raise forms.ValidationError(f'段高さは{min_height}cm以上である必要があります。')
        if height > max_height:
            raise forms.ValidationError(f'段高さは{max_height}cm以下である必要があります。')
        return height


class ProductPlacementForm(forms.ModelForm):
    """商品配置フォーム"""
    
    class Meta:
        model = ProductPlacement
        fields = ['product', 'x_position', 'face_count']
        
    def __init__(self, *args, **kwargs):
        segment = kwargs.pop('segment', None)
        super().__init__(*args, **kwargs)
        
        # 設定からフェース数の制限を取得
        max_face_count = getattr(settings, 'SHELF_SETTINGS', {}).get('MAX_FACE_COUNT', 20)
        
        self.fields['product'] = forms.ModelChoiceField(
            queryset=Product.objects.filter(is_active=True).order_by('name'),
            widget=forms.Select(attrs={'class': 'form-control'}),
            label='商品'
        )
        
        self.fields['x_position'] = forms.FloatField(
            widget=forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'min': '0.0',
                'placeholder': '0.0'
            }),
            min_value=0.0,
            label='X座標 (cm)'
        )
        
        self.fields['face_count'] = forms.IntegerField(
            widget=forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': str(max_face_count),
                'value': '1'
            }),
            min_value=1,
            max_value=max_face_count,
            label='フェース数'
        )
        
        # 段が指定されている場合、配置可能な商品のみ表示
        if segment:
            available_products = []
            for product in self.fields['product'].queryset:
                if segment.can_fit_product(product):
                    available_products.append(product.id)
            self.fields['product'].queryset = self.fields['product'].queryset.filter(id__in=available_products)
            
            # X座標の最大値を棚幅に設定
            self.fields['x_position'].widget.attrs['max'] = str(segment.shelf.width)
    
    def clean_face_count(self):
        face_count = self.cleaned_data['face_count']
        max_face_count = getattr(settings, 'SHELF_SETTINGS', {}).get('MAX_FACE_COUNT', 20)
        
        if face_count < 1:
            raise forms.ValidationError('フェース数は1以上である必要があります。')
        if face_count > max_face_count:
            raise forms.ValidationError(f'フェース数は{max_face_count}以下である必要があります。')
        return face_count
    
    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get('product')
        x_position = cleaned_data.get('x_position')
        face_count = cleaned_data.get('face_count')
        
        if product and x_position is not None and face_count:
            # 占有幅の計算
            occupied_width = product.width * face_count
            
            # X座標 + 占有幅が棚幅を超えないかチェック
            if hasattr(self, 'segment') and self.segment:
                if x_position + occupied_width > self.segment.shelf.width:
                    raise forms.ValidationError(
                        f'配置位置が棚幅を超えています。最大X座標: {self.segment.shelf.width - occupied_width:.1f}cm'
                    )
        
        return cleaned_data


class ProductSearchForm(forms.Form):
    """商品検索フォーム"""
    query = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '商品名またはメーカー名で検索',
            'autocomplete': 'off'
        }),
        label='商品検索'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['query'].required = False


class ProductCreateForm(forms.ModelForm):
    """商品作成フォーム（最小限）"""
    
    class Meta:
        model = Product
        fields = ['name', 'maker', 'jan_code', 'width', 'height', 'depth', 'price', 'image']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '例: コカ・コーラ 500ml'
            }),
            'maker': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '例: コカ・コーラ'
            }),
            'jan_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '13桁のJANコード'
            }),
            'width': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'min': '0.1',
                'placeholder': '6.5'
            }),
            'height': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1', 
                'min': '0.1',
                'placeholder': '19.5'
            }),
            'depth': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'min': '0.1', 
                'placeholder': '6.5'
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.00',
                'placeholder': '150.00'
            }),
            'image': forms.FileInput(attrs={
                'class': 'form-control'
            }),
        }
    
    def clean_jan_code(self):
        jan_code = self.cleaned_data.get('jan_code')
        if jan_code and len(jan_code) != 13:
            raise forms.ValidationError('JANコードは13桁である必要があります。')
        if jan_code and not jan_code.isdigit():
            raise forms.ValidationError('JANコードは数字のみである必要があります。')
        return jan_code
    
    def clean_width(self):
        width = self.cleaned_data['width']
        if width <= 0:
            raise forms.ValidationError('幅は0より大きい値である必要があります。')
        if width > 100:
            raise forms.ValidationError('幅は100cm以下である必要があります。')
        return width
    
    def clean_height(self):
        height = self.cleaned_data['height']
        if height <= 0:
            raise forms.ValidationError('高さは0より大きい値である必要があります。')
        if height > 100:
            raise forms.ValidationError('高さは100cm以下である必要があります。')
        return height


class ShelfDisplaySettingsForm(forms.Form):
    """棚表示設定フォーム（管理者用）"""
    display_scale = forms.IntegerField(
        label='表示倍率 (1cm = N px)',
        min_value=1,
        max_value=10,
        initial=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'help_text': '1cm あたりのピクセル数を設定'
        })
    )
    
    grid_snap_size = forms.IntegerField(
        label='グリッドスナップサイズ (px)',
        min_value=5,
        max_value=50,
        initial=20,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'help_text': 'グリッドスナップ時の最小単位'
        })
    )
    
    min_segment_height = forms.FloatField(
        label='最小段高さ (cm)',
        min_value=10.0,
        max_value=30.0,
        initial=15.0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.1'
        })
    )
    
    max_segment_height = forms.FloatField(
        label='最大段高さ (cm)',
        min_value=40.0,
        max_value=100.0,
        initial=60.0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.1'
        })
    )
    
    max_face_count = forms.IntegerField(
        label='最大フェース数',
        min_value=5,
        max_value=50,
        initial=20,
        widget=forms.NumberInput(attrs={
            'class': 'form-control'
        })
    )