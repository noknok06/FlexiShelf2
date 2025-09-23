from django.core.management.base import BaseCommand
from shelf.models import Shelf, ProductPlacement, round_decimal
from collections import defaultdict

class Command(BaseCommand):
    help = '棚の整合性を総合的に検証する'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--shelf-id',
            type=int,
            help='特定の棚のみ検証',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='詳細な情報を表示',
        )
    
    def handle(self, *args, **options):
        shelves = Shelf.objects.filter(is_active=True)
        
        if options['shelf_id']:
            shelves = shelves.filter(id=options['shelf_id'])
        
        total_issues = 0
        
        for shelf in shelves:
            self.stdout.write(f"\n{'='*50}")
            self.stdout.write(f"棚: {shelf.name}")
            self.stdout.write(f"サイズ: {shelf.width} × {shelf.depth} × {shelf.total_height}cm")
            self.stdout.write(f"{'='*50}")
            
            issues = self.validate_shelf(shelf, options['verbose'])
            total_issues += len(issues)
            
            if issues:
                self.stdout.write(
                    self.style.WARNING(f"⚠️  {len(issues)}個の問題を発見:")
                )
                for issue in issues:
                    self.stdout.write(f"  • {issue}")
            else:
                self.stdout.write(self.style.SUCCESS("✅ 問題なし"))
        
        self.stdout.write(f"\n{'='*50}")
        if total_issues > 0:
            self.stdout.write(
                self.style.WARNING(f"総合結果: {total_issues}個の問題が見つかりました")
            )
            self.stdout.write("\n修正方法:")
            self.stdout.write("  python manage.py fix_overlaps --shelf-id <ID> --strategy compact")
            self.stdout.write("  python manage.py debug_coordinates --fix")
        else:
            self.stdout.write(self.style.SUCCESS("総合結果: すべての棚が正常です"))
    
    def validate_shelf(self, shelf, verbose=False):
        """単一棚の検証"""
        issues = []
        
        # 段の検証
        segments = shelf.segments.filter(is_active=True).order_by('level')
        
        if verbose:
            self.stdout.write(f"\n段情報: {segments.count()}段")
        
        for segment in segments:
            segment_issues = self.validate_segment(segment, verbose)
            issues.extend(segment_issues)
        
        # 棚全体の統計
        total_placements = ProductPlacement.objects.filter(shelf=shelf).count()
        total_products = sum(
            p.face_count for p in ProductPlacement.objects.filter(shelf=shelf)
        )
        
        if verbose:
            self.stdout.write(f"\n統計:")
            self.stdout.write(f"  配置数: {total_placements}")
            self.stdout.write(f"  商品数: {total_products}")
        
        return issues
    
    def validate_segment(self, segment, verbose=False):
        """単一段の検証"""
        issues = []
        placements = segment.placements.all().order_by('x_position')
        
        if verbose:
            self.stdout.write(f"\n段{segment.level} (高さ: {segment.height}cm):")
            self.stdout.write(f"  配置商品: {placements.count()}個")
        
        # 各配置の検証
        ranges = []
        for placement in placements:
            # 幅の整合性チェック
            calculated_width = placement.product.get_occupied_width(placement.face_count)
            if abs(calculated_width - placement.occupied_width) > 0.1:
                issues.append(
                    f"段{segment.level}: {placement.product.name} "
                    f"幅不整合 (計算値: {calculated_width:.1f}cm, "
                    f"保存値: {placement.occupied_width:.1f}cm)"
                )
            
            # 高さチェック
            if placement.product.height > segment.height:
                issues.append(
                    f"段{segment.level}: {placement.product.name} "
                    f"高さ超過 (商品: {placement.product.height}cm > "
                    f"段: {segment.height}cm)"
                )
            
            # 棚幅チェック
            end_position = placement.x_position + placement.occupied_width
            if end_position > segment.shelf.width:
                issues.append(
                    f"段{segment.level}: {placement.product.name} "
                    f"棚幅超過 (終了位置: {end_position:.1f}cm > "
                    f"棚幅: {segment.shelf.width}cm)"
                )
            
            # 重複チェック用の範囲記録
            start = round_decimal(placement.x_position)
            end = round_decimal(start + placement.occupied_width)
            ranges.append({
                'placement': placement,
                'start': start,
                'end': end
            })
            
            if verbose:
                self.stdout.write(
                    f"    {placement.product.name}: "
                    f"{start:.1f}-{end:.1f}cm ({placement.face_count}フェース)"
                )
        
        # 重複チェック
        overlaps = self.find_range_overlaps(ranges)
        for overlap in overlaps:
            issues.append(
                f"段{segment.level}: 重複 - "
                f"{overlap['placement1'].product.name} と "
                f"{overlap['placement2'].product.name}"
            )
        
        # 利用率計算
        if verbose:
            used_width = sum(p.occupied_width for p in placements)
            utilization = (used_width / segment.shelf.width) * 100 if segment.shelf.width > 0 else 0
            self.stdout.write(f"  利用率: {utilization:.1f}% ({used_width:.1f}/{segment.shelf.width}cm)")
        
        return issues
    
    def find_range_overlaps(self, ranges):
        """範囲の重複を検出"""
        overlaps = []
        tolerance = 0.05
        
        for i, range1 in enumerate(ranges):
            for j, range2 in enumerate(ranges[i+1:], i+1):
                if (range1['end'] > range2['start'] + tolerance and 
                    range1['start'] < range2['end'] - tolerance):
                    overlaps.append({
                        'placement1': range1['placement'],
                        'placement2': range2['placement'],
                        'overlap_start': max(range1['start'], range2['start']),
                        'overlap_end': min(range1['end'], range2['end'])
                    })
        
        return overlaps
