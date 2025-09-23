from django.core.management.base import BaseCommand
from django.db import transaction
from shelf.models import Shelf, ProductPlacement
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = '棚の配置をリセットして再配置する'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--shelf-id',
            type=int,
            required=True,
            help='リセットする棚のID',
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='確認なしで実行',
        )
    
    def handle(self, *args, **options):
        shelf_id = options['shelf_id']
        
        try:
            shelf = Shelf.objects.get(id=shelf_id)
        except Shelf.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'棚ID {shelf_id} が見つかりません')
            )
            return
        
        # 現在の配置状況を表示
        placements = ProductPlacement.objects.filter(shelf=shelf)
        self.stdout.write(f"\n棚「{shelf.name}」の現在の配置:")
        self.stdout.write(f"配置商品数: {placements.count()}個")
        
        for segment in shelf.segments.all().order_by('level'):
            segment_placements = placements.filter(segment=segment)
            self.stdout.write(
                f"  段{segment.level}: {segment_placements.count()}個"
            )
            for placement in segment_placements:
                self.stdout.write(
                    f"    - {placement.product.name} "
                    f"({placement.x_position:.1f}cm, {placement.face_count}フェース)"
                )
        
        # 確認
        if not options['confirm']:
            response = input(f"\n棚「{shelf.name}」の全配置を削除しますか? [y/N]: ")
            if response.lower() != 'y':
                self.stdout.write("キャンセルしました")
                return
        
        # 削除実行
        with transaction.atomic():
            deleted_count = placements.count()
            placements.delete()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'棚「{shelf.name}」から {deleted_count} 個の配置を削除しました'
                )
            )
        
        # 推奨される次のステップ
        self.stdout.write(
            self.style.WARNING(
                "\n推奨される次のステップ:\n"
                "1. ブラウザで棚割り画面を開く\n"
                "2. 商品を手動で再配置する\n"
                "3. または create_sample_shelf コマンドでサンプルデータを再作成"
            )
        )
