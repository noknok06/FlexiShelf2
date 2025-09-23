from django.core.management.base import BaseCommand
from django.db import transaction
from shelf.models import Shelf, ShelfSegment, ProductPlacement, round_decimal
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = '重複している商品配置を自動修正する'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--shelf-id',
            type=int,
            help='特定の棚のみ修正',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='実際には修正せず、修正内容のみ表示',
        )
        parser.add_argument(
            '--strategy',
            type=str,
            default='compact',
            choices=['compact', 'spread', 'delete_duplicates'],
            help='修正戦略: compact(詰める), spread(分散), delete_duplicates(重複削除)',
        )
    
    def handle(self, *args, **options):
        shelves = Shelf.objects.filter(is_active=True)
        
        if options['shelf_id']:
            shelves = shelves.filter(id=options['shelf_id'])
        
        total_fixed = 0
        
        for shelf in shelves:
            self.stdout.write(f"\n=== 棚: {shelf.name} ===")
            fixed_count = self.fix_shelf_overlaps(shelf, options)
            total_fixed += fixed_count
        
        self.stdout.write(
            self.style.SUCCESS(f'\n修正完了: 合計 {total_fixed} 個の重複を解決しました')
        )
    
    def fix_shelf_overlaps(self, shelf, options):
        """棚内の重複を修正"""
        fixed_count = 0
        
        for segment in shelf.segments.filter(is_active=True).order_by('level'):
            self.stdout.write(f"\n段{segment.level} ({segment.height}cm高):")
            
            placements = list(segment.placements.all().order_by('x_position'))
            if len(placements) < 2:
                self.stdout.write("  配置商品が1個以下のためスキップ")
                continue
            
            overlaps = self.find_overlaps_in_segment(placements)
            
            if not overlaps:
                self.stdout.write("  重複なし")
                continue
            
            self.stdout.write(f"  {len(overlaps)}個の重複を発見")
            
            if options['strategy'] == 'compact':
                fixed = self.fix_overlaps_compact(segment, placements, options['dry_run'])
            elif options['strategy'] == 'spread':
                fixed = self.fix_overlaps_spread(segment, placements, options['dry_run'])
            elif options['strategy'] == 'delete_duplicates':
                fixed = self.fix_overlaps_delete(segment, overlaps, options['dry_run'])
            
            fixed_count += fixed
        
        return fixed_count
    
    def find_overlaps_in_segment(self, placements):
        """段内の重複を検出"""
        overlaps = []
        tolerance = 0.05
        
        for i, placement1 in enumerate(placements):
            start1 = round_decimal(placement1.x_position)
            end1 = round_decimal(start1 + placement1.occupied_width)
            
            for j, placement2 in enumerate(placements[i+1:], i+1):
                start2 = round_decimal(placement2.x_position)
                end2 = round_decimal(start2 + placement2.occupied_width)
                
                # 重複判定
                if (end1 > start2 + tolerance) and (start1 < end2 - tolerance):
                    overlap_start = max(start1, start2)
                    overlap_end = min(end1, end2)
                    overlap_width = overlap_end - overlap_start
                    
                    overlaps.append({
                        'placement1': placement1,
                        'placement2': placement2,
                        'overlap_start': overlap_start,
                        'overlap_end': overlap_end,
                        'overlap_width': overlap_width,
                        'range1': f'{start1:.1f}-{end1:.1f}',
                        'range2': f'{start2:.1f}-{end2:.1f}',
                    })
        
        return overlaps
    
    def fix_overlaps_compact(self, segment, placements, dry_run):
        """重複を詰めて解決（左詰め戦略）"""
        self.stdout.write("  戦略: 左詰めで重複解決")
        
        if dry_run:
            self.stdout.write("  [DRY RUN] 実際の修正は行いません")
        
        # X座標順にソート
        sorted_placements = sorted(placements, key=lambda p: p.x_position)
        fixed_count = 0
        current_x = 0
        
        with transaction.atomic():
            for placement in sorted_placements:
                original_x = placement.x_position
                new_x = round_decimal(max(current_x, 0))
                
                if abs(new_x - original_x) > 0.1:  # 移動が必要
                    self.stdout.write(
                        f"    {placement.product.name}: {original_x:.1f}cm → {new_x:.1f}cm"
                    )
                    
                    if not dry_run:
                        placement.x_position = new_x
                        placement.save()
                    
                    fixed_count += 1
                
                current_x = new_x + placement.occupied_width + 0.1  # 0.1cmの間隔を追加
                
                # 棚幅チェック
                if current_x > segment.shelf.width:
                    self.stdout.write(
                        self.style.WARNING(
                            f"    警告: {placement.product.name} が棚幅を超えます"
                        )
                    )
        
        return fixed_count
    
    def fix_overlaps_spread(self, segment, placements, dry_run):
        """重複を分散して解決"""
        self.stdout.write("  戦略: 均等分散で重複解決")
        
        if dry_run:
            self.stdout.write("  [DRY RUN] 実際の修正は行いません")
        
        # 利用可能幅を計算
        total_width = sum(p.occupied_width for p in placements)
        available_width = segment.shelf.width
        
        if total_width > available_width:
            self.stdout.write(
                self.style.ERROR(
                    f"    エラー: 総占有幅({total_width:.1f}cm) > 棚幅({available_width:.1f}cm)"
                )
            )
            return 0
        
        # 間隔を計算
        if len(placements) > 1:
            total_gap = available_width - total_width
            gap_per_item = total_gap / len(placements)
        else:
            gap_per_item = 0
        
        sorted_placements = sorted(placements, key=lambda p: p.x_position)
        fixed_count = 0
        current_x = gap_per_item / 2  # 最初の間隔
        
        with transaction.atomic():
            for placement in sorted_placements:
                original_x = placement.x_position
                new_x = round_decimal(current_x)
                
                if abs(new_x - original_x) > 0.1:
                    self.stdout.write(
                        f"    {placement.product.name}: {original_x:.1f}cm → {new_x:.1f}cm"
                    )
                    
                    if not dry_run:
                        placement.x_position = new_x
                        placement.save()
                    
                    fixed_count += 1
                
                current_x += placement.occupied_width + gap_per_item
        
        return fixed_count
    
    def fix_overlaps_delete(self, segment, overlaps, dry_run):
        """重複商品を削除して解決"""
        self.stdout.write("  戦略: 重複商品削除")
        
        if dry_run:
            self.stdout.write("  [DRY RUN] 実際の削除は行いません")
        
        deleted_count = 0
        deleted_placements = set()
        
        for overlap in overlaps:
            # より後ろにある商品を削除対象とする
            placement1 = overlap['placement1']
            placement2 = overlap['placement2']
            
            if placement1.x_position < placement2.x_position:
                to_delete = placement2
            else:
                to_delete = placement1
            
            if to_delete.id not in deleted_placements:
                self.stdout.write(
                    f"    削除対象: {to_delete.product.name} "
                    f"(位置: {to_delete.x_position:.1f}cm)"
                )
                
                if not dry_run:
                    to_delete.delete()
                
                deleted_placements.add(to_delete.id)
                deleted_count += 1
        
        return deleted_count
