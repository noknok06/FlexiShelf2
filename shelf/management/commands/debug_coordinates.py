import os
import django
from django.core.management.base import BaseCommand
from shelf.models import ProductPlacement

class Command(BaseCommand):
    help = 'デバッグ: 座標の整合性をチェック'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='不整合を自動修正する',
        )
        parser.add_argument(
            '--shelf-id',
            type=int,
            help='特定の棚のみチェック',
        )
    
    def handle(self, *args, **options):
        placements = ProductPlacement.objects.all()
        
        if options['shelf_id']:
            placements = placements.filter(shelf_id=options['shelf_id'])
        
        issues = []
        
        for placement in placements:
            # 占有幅の整合性チェック
            calculated_width = placement.product.get_occupied_width(placement.face_count)
            stored_width = placement.occupied_width
            
            if abs(calculated_width - stored_width) > 0.1:
                issue = {
                    'type': 'width_mismatch',
                    'placement': placement,
                    'calculated': calculated_width,
                    'stored': stored_width
                }
                issues.append(issue)
                
                if options['fix']:
                    placement.occupied_width = calculated_width
                    placement.save()
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'修正: {placement} 幅 {stored_width} → {calculated_width}'
                        )
                    )
            
            # 重複チェック
            overlapping = placement._find_overlapping_placement()
            if overlapping:
                issue = {
                    'type': 'overlap',
                    'placement': placement,
                    'overlapping_with': overlapping
                }
                issues.append(issue)
        
        # 結果の表示
        if issues:
            self.stdout.write(self.style.WARNING(f'{len(issues)}個の問題を発見:'))
            
            for issue in issues:
                if issue['type'] == 'width_mismatch':
                    self.stdout.write(
                        f"  幅不整合: {issue['placement']} "
                        f"計算値={issue['calculated']:.1f}cm "
                        f"保存値={issue['stored']:.1f}cm"
                    )
                elif issue['type'] == 'overlap':
                    self.stdout.write(
                        f"  重複: {issue['placement']} と "
                        f"{issue['overlapping_with']} が重複"
                    )
        else:
            self.stdout.write(self.style.SUCCESS('問題なし: すべての座標が正常です'))
            
        return f'チェック完了: {len(issues)}個の問題'