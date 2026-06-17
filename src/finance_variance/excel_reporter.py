import os
import math
import pandas as pd
from datetime import datetime
from typing import List, Optional, Dict
import xlsxwriter
from .models import ReportConfig, ExcelColorConfig, AnomalyItem, VarianceResult


class ExcelReporter:
    """Excel 格式报告生成器"""

    def __init__(self, config: Optional[ReportConfig] = None):
        self.config = config or ReportConfig()
        self.color_cfg: ExcelColorConfig = self.config.excel_color_config

    def generate(self,
                 variance_results: List[VarianceResult],
                 variance_df: pd.DataFrame,
                 account_summary: pd.DataFrame,
                 period_summary: pd.DataFrame,
                 anomalies: List[AnomalyItem],
                 anomalies_df: pd.DataFrame,
                 output_path: str) -> None:
        """生成 Excel 报告"""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        workbook = xlsxwriter.Workbook(output_path, {'nan_inf_to_errors': True})

        formats = self._create_formats(workbook)

        self._create_cover_sheet(workbook, formats, account_summary, period_summary)
        self._create_account_summary_sheet(workbook, formats, account_summary)
        self._create_period_summary_sheet(workbook, formats, period_summary)
        self._create_anomalies_sheet(workbook, formats, anomalies_df)

        if self.config.include_cumulative:
            self._create_cumulative_sheet(workbook, formats, variance_df)

        self._create_detailed_sheet(workbook, formats, variance_df)

        workbook.close()

    def _create_formats(self, workbook: xlsxwriter.Workbook) -> dict:
        """创建单元格格式，接入ExcelColorConfig三档阈值"""
        cc = self.color_cfg

        def make_variance_format(bg_color, font_color, is_pct=False):
            base = {
                'border': 1,
                'bg_color': bg_color,
                'font_color': font_color,
                'bold': True
            }
            if is_pct:
                base['num_format'] = '+0.00%;-0.00%'
            else:
                base['num_format'] = '+#,##0.00;-#,##0.00'
            return workbook.add_format(base)

        formats = {
            'title': workbook.add_format({
                'bold': True,
                'font_size': 18,
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': '#1F4E78',
                'font_color': 'white'
            }),
            'header': workbook.add_format({
                'bold': True,
                'font_size': 12,
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': '#D9E1F2',
                'border': 1
            }),
            'normal': workbook.add_format({
                'border': 1,
                'num_format': '#,##0.00'
            }),
            'integer': workbook.add_format({
                'border': 1,
                'num_format': '#,##0'
            }),
            'percent': workbook.add_format({
                'border': 1,
                'num_format': '0.00%'
            }),
            'text': workbook.add_format({
                'border': 1,
                'text_wrap': True
            }),
            'label': workbook.add_format({
                'bold': True,
                'font_size': 11
            }),
            'info': workbook.add_format({
                'italic': True,
                'font_color': '#808080'
            }),
            'neutral': workbook.add_format({
                'border': 1,
                'num_format': '+#,##0.00;-#,##0.00',
                'bg_color': cc.neutral_bg,
                'font_color': cc.neutral_font
            }),
            'neutral_pct': workbook.add_format({
                'border': 1,
                'num_format': '+0.00%;-0.00%',
                'bg_color': cc.neutral_bg,
                'font_color': cc.neutral_font
            }),

            'favorable_level1': make_variance_format(cc.favorable_level1_bg, cc.favorable_level1_font, False),
            'favorable_level2': make_variance_format(cc.favorable_level2_bg, cc.favorable_level2_font, False),
            'favorable_level3': make_variance_format(cc.favorable_level3_bg, cc.favorable_level3_font, False),
            'favorable_level1_pct': make_variance_format(cc.favorable_level1_bg, cc.favorable_level1_font, True),
            'favorable_level2_pct': make_variance_format(cc.favorable_level2_bg, cc.favorable_level2_font, True),
            'favorable_level3_pct': make_variance_format(cc.favorable_level3_bg, cc.favorable_level3_font, True),

            'unfavorable_level1': make_variance_format(cc.unfavorable_level1_bg, cc.unfavorable_level1_font, False),
            'unfavorable_level2': make_variance_format(cc.unfavorable_level2_bg, cc.unfavorable_level2_font, False),
            'unfavorable_level3': make_variance_format(cc.unfavorable_level3_bg, cc.unfavorable_level3_font, False),
            'unfavorable_level1_pct': make_variance_format(cc.unfavorable_level1_bg, cc.unfavorable_level1_font, True),
            'unfavorable_level2_pct': make_variance_format(cc.unfavorable_level2_bg, cc.unfavorable_level2_font, True),
            'unfavorable_level3_pct': make_variance_format(cc.unfavorable_level3_bg, cc.unfavorable_level3_font, True),

            'good_status': workbook.add_format({
                'border': 1,
                'bg_color': cc.favorable_level2_bg,
                'font_color': cc.favorable_level2_font,
                'bold': True
            }),
            'bad_status': workbook.add_format({
                'border': 1,
                'bg_color': cc.unfavorable_level2_bg,
                'font_color': cc.unfavorable_level2_font,
                'bold': True
            })
        }

        self._formats_cache = formats
        return formats

    def _get_variance_format(self, relative_variance: Optional[float], is_pct: bool = False):
        """根据相对差异获取对应的格式（三档颜色分级）"""
        fmt_key = self.color_cfg.get_format_key(relative_variance)

        suffix = '_pct' if is_pct else ''
        if is_pct:
            full_key = fmt_key + suffix
            if full_key in self._formats_cache:
                return self._formats_cache[full_key]
        else:
            if fmt_key in self._formats_cache:
                return self._formats_cache[fmt_key]

        return self._formats_cache.get('neutral_pct' if is_pct else 'neutral')

    def _create_cover_sheet(self, workbook, formats, account_summary, period_summary):
        """创建封面/概览工作表"""
        worksheet = workbook.add_worksheet('报告概览')
        worksheet.set_column('A:A', 3)
        worksheet.set_column('B:B', 25)
        worksheet.set_column('C:C', 25)
        worksheet.set_column('D:D', 30)

        worksheet.merge_range('B2:E2', self.config.title, formats['title'])
        worksheet.set_row(1, 40)

        row = 4
        now = datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')
        worksheet.write(row, 1, '公司名称', formats['label'])
        worksheet.write(row, 2, self.config.company_name)
        row += 1
        worksheet.write(row, 1, '生成时间', formats['label'])
        worksheet.write(row, 2, now)
        row += 1

        period_info = "全年"
        if self.config.start_period and self.config.end_period:
            period_info = f"{self.config.start_period} 至 {self.config.end_period}"
        elif self.config.start_period:
            period_info = f"{self.config.start_period} 起"
        elif self.config.end_period:
            period_info = f"截至 {self.config.end_period}"

        worksheet.write(row, 1, '分析期间', formats['label'])
        worksheet.write(row, 2, period_info)
        row += 1
        worksheet.write(row, 1, '异常阈值', formats['label'])
        worksheet.write(row, 2, f"{self.config.anomaly_threshold * 100:.0f}%")
        row += 1
        worksheet.write(row, 1, '颜色分级阈值', formats['label'])
        worksheet.write(row, 2,
                        f"一级: ±{self.color_cfg.level1_threshold*100:.0f}% / "
                        f"二级: ±{self.color_cfg.level2_threshold*100:.0f}% / "
                        f"三级: ±{self.color_cfg.level3_threshold*100:.0f}%")
        row += 2

        total_budget = account_summary['预算金额'].sum()
        total_actual = account_summary['实际金额'].sum()
        total_variance = account_summary['绝对差异'].sum()
        total_relative_variance = (total_variance / total_budget) if total_budget != 0 else None

        worksheet.merge_range('B7:E7', '核心指标', formats['header'])
        row += 1

        kpi_data = [
            ('预算总额', total_budget, formats['normal']),
            ('实际总额', total_actual, formats['normal']),
            ('总差异', total_variance,
             self._get_variance_format(total_relative_variance, False)),
            ('总差异率', total_relative_variance,
             self._get_variance_format(total_relative_variance, True))
        ]

        for i, (label, value, fmt) in enumerate(kpi_data):
            worksheet.write(row + i, 1, label, formats['label'])
            worksheet.write(row + i, 2, value if value is not None else 'N/A', fmt)

        row += len(kpi_data) + 2
        worksheet.merge_range(f'B{row}:E{row}', '科目差异分布', formats['header'])
        row += 1

        favorable_count = len(account_summary[account_summary['绝对差异'] > 0])
        unfavorable_count = len(account_summary[account_summary['绝对差异'] < 0])
        on_track_count = len(account_summary[account_summary['绝对差异'] == 0])

        worksheet.write(row, 1, '✅ 有利差异科目', formats['label'])
        worksheet.write(row, 2, favorable_count, formats['good_status'])
        row += 1
        worksheet.write(row, 1, '⚠️ 不利差异科目', formats['label'])
        worksheet.write(row, 2, unfavorable_count, formats['bad_status'])
        row += 1
        worksheet.write(row, 1, '➖ 预算持平科目', formats['label'])
        worksheet.write(row, 2, on_track_count, formats['normal'])

        row += 3
        worksheet.merge_range(f'B{row}:E{row}', '说明', formats['header'])
        row += 1
        worksheet.write(row, 1, '1. 绝对差异 = 实际金额 - 预算金额', formats['info'])
        row += 1
        worksheet.write(row, 1, '2. 相对差异 = 绝对差异 / 预算金额 × 100%', formats['info'])
        row += 1
        worksheet.write(row, 1, f'3. 颜色分级：0~±{self.color_cfg.level1_threshold*100:.0f}% 正常色；'
                                f'±{self.color_cfg.level1_threshold*100:.0f}%~±{self.color_cfg.level2_threshold*100:.0f}% 浅色；'
                                f'±{self.color_cfg.level2_threshold*100:.0f}%~±{self.color_cfg.level3_threshold*100:.0f}% 中色；'
                                f'>±{self.color_cfg.level3_threshold*100:.0f}% 深色', formats['info'])
        row += 1
        worksheet.write(row, 1, '4. 【待核实】标记的成因需人工确认', formats['info'])

    def _create_account_summary_sheet(self, workbook, formats, account_summary):
        """创建科目汇总工作表"""
        worksheet = workbook.add_worksheet('科目差异汇总')

        headers = ['科目编码', '科目名称', '预算金额', '实际金额', '绝对差异', '相对差异']
        col_widths = [12, 20, 15, 15, 15, 12]

        for i, (header, width) in enumerate(zip(headers, col_widths)):
            worksheet.write(0, i, header, formats['header'])
            worksheet.set_column(i, i, width)

        for row_idx, (_, row) in enumerate(account_summary.iterrows(), 1):
            worksheet.write(row_idx, 0, row['科目编码'], formats['text'])
            worksheet.write(row_idx, 1, row['科目名称'], formats['text'])
            worksheet.write(row_idx, 2, row['预算金额'], formats['normal'])
            worksheet.write(row_idx, 3, row['实际金额'], formats['normal'])

            rel_var = None
            if pd.notna(row.get('相对差异(%)')):
                rv = row['相对差异(%)']
                if isinstance(rv, (int, float)) and not math.isnan(rv) and not math.isinf(rv):
                    rel_var = rv / 100

            worksheet.write(row_idx, 4, row['绝对差异'],
                            self._get_variance_format(rel_var, False))
            worksheet.write(row_idx, 5, rel_var if rel_var is not None else 'N/A',
                            self._get_variance_format(rel_var, True))

        worksheet.freeze_panes(1, 2)
        worksheet.autofilter(0, 0, len(account_summary), len(headers) - 1)

    def _create_period_summary_sheet(self, workbook, formats, period_summary):
        """创建期间汇总工作表"""
        worksheet = workbook.add_worksheet('期间趋势分析')

        headers = ['期间', '预算金额', '实际金额', '期间差异', '差异率', '累计偏离']
        col_widths = [14, 15, 15, 15, 12, 15]

        for i, (header, width) in enumerate(zip(headers, col_widths)):
            worksheet.write(0, i, header, formats['header'])
            worksheet.set_column(i, i, width)

        for row_idx, (_, row) in enumerate(period_summary.iterrows(), 1):
            worksheet.write(row_idx, 0, row['期间'], formats['text'])
            worksheet.write(row_idx, 1, row['预算金额'], formats['normal'])
            worksheet.write(row_idx, 2, row['实际金额'], formats['normal'])

            rel_var = None
            if pd.notna(row.get('相对差异(%)')):
                rv = row['相对差异(%)']
                if isinstance(rv, (int, float)) and not math.isnan(rv) and not math.isinf(rv):
                    rel_var = rv / 100

            cum_rel_var = None
            if row['累计偏离'] != 0 and row['预算金额'] != 0:
                cum_rel_var = row['累计偏离'] / (row['预算金额'] + 1)

            worksheet.write(row_idx, 3, row['绝对差异'],
                            self._get_variance_format(rel_var, False))
            worksheet.write(row_idx, 4, rel_var if rel_var is not None else 'N/A',
                            self._get_variance_format(rel_var, True))
            worksheet.write(row_idx, 5, row['累计偏离'],
                            self._get_variance_format(cum_rel_var, False))

        worksheet.freeze_panes(1, 1)

        chart = workbook.add_chart({'type': 'line'})
        chart.add_series({
            'name': '预算金额',
            'categories': ['期间趋势分析', 1, 0, len(period_summary), 0],
            'values': ['期间趋势分析', 1, 1, len(period_summary), 1],
            'line': {'color': 'blue'}
        })
        chart.add_series({
            'name': '实际金额',
            'categories': ['期间趋势分析', 1, 0, len(period_summary), 0],
            'values': ['期间趋势分析', 1, 2, len(period_summary), 2],
            'line': {'color': 'green'}
        })
        chart.set_title({'name': '预算 vs 实际 趋势图'})
        chart.set_x_axis({'name': '期间'})
        chart.set_y_axis({'name': '金额'})
        chart.set_style(11)

        worksheet.insert_chart(0, 7, chart, {'x_scale': 1.5, 'y_scale': 1.5})

    def _create_anomalies_sheet(self, workbook, formats, anomalies_df):
        """创建异常分析工作表"""
        worksheet = workbook.add_worksheet('重大异常分析')

        if '分组' in anomalies_df.columns:
            has_group = True
            headers = ['排名', '分组', '科目编码', '科目名称', '期间', '绝对差异', '相对差异', '影响分数', '差异类型', '成因分析（待核实）']
            col_widths = [6, 16, 10, 18, 10, 15, 12, 10, 10, 40]
        else:
            has_group = False
            headers = ['排名', '科目编码', '科目名称', '期间', '绝对差异', '相对差异', '影响分数', '差异类型', '成因分析（待核实）']
            col_widths = [6, 10, 18, 10, 15, 12, 10, 10, 40]

        worksheet.merge_range(0, 0, 0, len(headers) - 1,
                              f'重大异常分析（Top {len(anomalies_df)}）', formats['title'])
        worksheet.set_row(0, 30)

        worksheet.write(1, 0,
                        f'异常阈值：{self.config.anomaly_threshold * 100:.0f}%；'
                        f'异常分组：{"超支/节省分开排序" if self.config.separate_anomaly_groups else "综合排序"}',
                        formats['info'])
        worksheet.write(1, 1, '说明：【待核实】标记的成因需人工核实确认', formats['info'])

        if anomalies_df.empty:
            worksheet.write(3, 0, '✅ 未发现超过阈值的异常项，整体表现平稳。', formats['good_status'])
            return

        for i, (header, width) in enumerate(zip(headers, col_widths)):
            worksheet.write(3, i, header, formats['header'])
            worksheet.set_column(i, i, width)

        for row_idx, (_, row) in enumerate(anomalies_df.iterrows(), 4):
            col = 0
            worksheet.write(row_idx, col, row['排名'], formats['integer'])
            col += 1
            if has_group:
                worksheet.write(row_idx, col, row['分组'], formats['text'])
                col += 1
            worksheet.write(row_idx, col, row['科目编码'], formats['text'])
            col += 1
            worksheet.write(row_idx, col, row['科目名称'], formats['text'])
            col += 1
            worksheet.write(row_idx, col, row['期间'], formats['text'])
            col += 1

            rel_var = None
            if pd.notna(row.get('相对差异(%)')):
                rv = row['相对差异(%)']
                if isinstance(rv, (int, float)) and not math.isnan(rv) and not math.isinf(rv):
                    rel_var = rv / 100

            worksheet.write(row_idx, col, row['绝对差异'],
                            self._get_variance_format(rel_var, False))
            col += 1
            worksheet.write(row_idx, col, rel_var if rel_var is not None else 'N/A',
                            self._get_variance_format(rel_var, True))
            col += 1
            worksheet.write(row_idx, col, row['影响分数'], formats['normal'])
            col += 1

            type_fmt = formats['good_status'] if row['差异类型'] == '有利差异' else formats['bad_status']
            worksheet.write(row_idx, col, row['差异类型'], type_fmt)
            col += 1
            worksheet.write(row_idx, col, row['成因分析（待核实）'], formats['text'])

        worksheet.freeze_panes(4, 3 + (1 if has_group else 0))

    def _create_cumulative_sheet(self, workbook, formats, variance_df):
        """创建累计偏离分析工作表"""
        latest_period = variance_df['期间'].iloc[-1]
        latest_data = variance_df[variance_df['期间'] == latest_period].copy()
        latest_data = latest_data.sort_values('累计偏离', key=lambda x: x.abs(), ascending=False)

        worksheet = workbook.add_worksheet('累计偏离分析')

        headers = ['科目编码', '科目名称', '累计预算', '累计实际', '累计偏离', '累计偏离率']
        col_widths = [12, 20, 15, 15, 15, 12]

        worksheet.merge_range(0, 0, 0, len(headers) - 1,
                              f'累计偏离分析（截至 {latest_period}）', formats['title'])
        worksheet.set_row(0, 30)

        for i, (header, width) in enumerate(zip(headers, col_widths)):
            worksheet.write(2, i, header, formats['header'])
            worksheet.set_column(i, i, width)

        for row_idx, (_, row) in enumerate(latest_data.iterrows(), 3):
            worksheet.write(row_idx, 0, row['科目编码'], formats['text'])
            worksheet.write(row_idx, 1, row['科目名称'], formats['text'])
            worksheet.write(row_idx, 2, row['累计预算'], formats['normal'])
            worksheet.write(row_idx, 3, row['累计实际'], formats['normal'])

            cum_rel_var = None
            if pd.notna(row.get('累计相对偏离(%)')):
                rv = row['累计相对偏离(%)']
                if isinstance(rv, (int, float)) and not math.isnan(rv) and not math.isinf(rv):
                    cum_rel_var = rv / 100

            worksheet.write(row_idx, 4, row['累计偏离'],
                            self._get_variance_format(cum_rel_var, False))
            worksheet.write(row_idx, 5, cum_rel_var if cum_rel_var is not None else 'N/A',
                            self._get_variance_format(cum_rel_var, True))

        worksheet.freeze_panes(3, 2)

    def _create_detailed_sheet(self, workbook, formats, variance_df):
        """创建详细差异数据表"""
        worksheet = workbook.add_worksheet('详细数据')

        headers = ['科目编码', '科目名称', '期间', '预算金额', '实际金额',
                   '绝对差异', '相对差异(%)', '累计预算', '累计实际', '累计偏离', '累计相对偏离(%)']
        col_widths = [12, 18, 10, 12, 12, 12, 12, 12, 12, 12, 14]

        for i, (header, width) in enumerate(zip(headers, col_widths)):
            worksheet.write(0, i, header, formats['header'])
            worksheet.set_column(i, i, width)

        for row_idx, (_, row) in enumerate(variance_df.iterrows(), 1):
            worksheet.write(row_idx, 0, row['科目编码'], formats['text'])
            worksheet.write(row_idx, 1, row['科目名称'], formats['text'])
            worksheet.write(row_idx, 2, row['期间'], formats['text'])
            worksheet.write(row_idx, 3, row['预算金额'], formats['normal'])
            worksheet.write(row_idx, 4, row['实际金额'], formats['normal'])

            rel_var = None
            if pd.notna(row.get('相对差异(%)')):
                rv = row['相对差异(%)']
                if isinstance(rv, (int, float)) and not math.isnan(rv) and not math.isinf(rv):
                    rel_var = rv / 100

            worksheet.write(row_idx, 5, row['绝对差异'],
                            self._get_variance_format(rel_var, False))
            worksheet.write(row_idx, 6, rel_var if rel_var is not None else 'N/A',
                            self._get_variance_format(rel_var, True))

            worksheet.write(row_idx, 7, row['累计预算'], formats['normal'])
            worksheet.write(row_idx, 8, row['累计实际'], formats['normal'])

            cum_rel_var = None
            if pd.notna(row.get('累计相对偏离(%)')):
                rv = row['累计相对偏离(%)']
                if isinstance(rv, (int, float)) and not math.isnan(rv) and not math.isinf(rv):
                    cum_rel_var = rv / 100

            worksheet.write(row_idx, 9, row['累计偏离'],
                            self._get_variance_format(cum_rel_var, False))
            worksheet.write(row_idx, 10, cum_rel_var if cum_rel_var is not None else 'N/A',
                            self._get_variance_format(cum_rel_var, True))

        worksheet.freeze_panes(1, 3)
        worksheet.autofilter(0, 0, len(variance_df), len(headers) - 1)
