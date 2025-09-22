from django.core.management.base import BaseCommand
from django.db import transaction
from shelf.models import Shelf, ShelfSegment, Product, ProductPlacement
from decimal import Decimal


class Command(BaseCommand):
    help = 'サンプルの棚割りデータを作成します'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='既存のサンプルデータを削除してから作成',
        )
    
    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('既存サンプルデータを削除中...')
            Shelf.objects.filter(name__startswith='サンプル').delete()
            Product.objects.filter(jan_code__startswith='SAMPLE').delete()
        
        with transaction.atomic():
            # サンプル商品作成
            products = self.create_sample_products()
            self.stdout.write(f'{len(products)}個のサンプル商品を作成しました')
            
            # サンプル棚作成
            shelf = self.create_sample_shelf()
            self.stdout.write(f'サンプル棚「{shelf.name}」を作成しました')
            
            # サンプル配置作成
            placements = self.create_sample_placements(shelf, products)
            self.stdout.write(f'{len(placements)}個の商品配置を作成しました')
        
        self.stdout.write(
            self.style.SUCCESS(
                'サンプルデータの作成が完了しました。'
                'http://127.0.0.1:8000/shelf/ でご確認ください。'
            )
        )
    
    def create_sample_products(self):
        """サンプル商品を作成"""
        products_data = [
            ('コカ・コーラ 500ml', 'コカ・コーラ', 6.5, 20.5, 6.5, 150),
            ('ペプシコーラ 500ml', 'サントリー', 6.5, 20.5, 6.5, 140),
            ('いろはす 555ml', 'コカ・コーラ', 6.0, 21.0, 6.0, 110),
            ('ポカリスエット 500ml', '大塚製薬', 6.8, 19.5, 6.8, 160),
            ('ポテトチップス うすしお', 'カルビー', 18.0, 23.0, 8.0, 158),
            ('キットカット ミニ', 'ネスレ', 10.5, 15.0, 3.5, 298),
        ]
        
        products = []
        for i, (name, maker, width, height, depth, price) in enumerate(products_data):
            product, created = Product.objects.get_or_create(
                name=name,
                defaults={
                    'maker': maker,
                    'jan_code': f'SAMPLE{i+1:06d}',
                    'width': width,
                    'height': height,
                    'depth': depth,
                    'price': Decimal(str(price)),
                }
            )
            products.append(product)
        
        return products
    
    def create_sample_shelf(self):
        """サンプル棚を作成"""
        shelf, created = Shelf.objects.get_or_create(
            name='サンプル棚（ドリンクコーナー）',
            defaults={
                'width': 120.0,
                'depth': 45.0,
                'total_height': 180.0,
                'description': 'ドリンクとお菓子のサンプル棚割り',
            }
        )
        
        if created:
            # 段を作成（4段構成）
            segment_heights = [40, 35, 35, 40]
            y_position = 0
            
            for level, height in enumerate(segment_heights, 1):
                ShelfSegment.objects.create(
                    shelf=shelf,
                    level=level,
                    height=height,
                    y_position=y_position
                )
                y_position += height
        
        return shelf
    
    def create_sample_placements(self, shelf, products):
        """サンプル商品配置を作成"""
        segments = shelf.segments.order_by('level')
        placements = []
        
        # 段1（最下段）: 重い商品（ドリンク類）
        segment1 = segments[0]
        x_pos = 5.0
        for product in products[:4]:  # ドリンク4種
            placement = ProductPlacement.objects.create(
                shelf=shelf,
                segment=segment1,
                product=product,
                x_position=x_pos,
                face_count=3,  # 3フェース
            )
            placements.append(placement)
            x_pos += product.width * 3 + 2  # 商品間隔2cm
        
        # 段2: お菓子類
        if len(segments) > 1:
            segment2 = segments[1]
            x_pos = 10.0
            for product in products[4:]:  # お菓子類
                placement = ProductPlacement.objects.create(
                    shelf=shelf,
                    segment=segment2,
                    product=product,
                    x_position=x_pos,
                    face_count=2,  # 2フェース
                )
                placements.append(placement)
                x_pos += product.width * 2 + 3
        
        return placements