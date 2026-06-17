import os
import pandas as pd
from datetime import datetime
from typing import List, Optional
import xlsxwriter
from .models import ReportConfig, AnomalyItem, VarianceResult


class ExcelReporter:
    """Excel 格式报告生成器"""

    def __init__(self, config: Optional[ReportConfig] = None):
        self.config = config or ReportConfig()

    def generate(self,
                 variance_results: List[VarianceResult],
                 variance_df: pd.DataFrame,
                 account_summary: pd.DataFrame,
                 period_summary: pd.DataFrame,
                 anomalies: List[AnomalyItem],
                 anomalies_df: pd.DataFrame,
                 output_path: str) -> None:
        """
        生成 Excel 报告

        Args:
            variance_results: 详细差异计算结果
            variance_df: 差异数据DataFrame
            account_summary: 按科目汇总
            period_summary: 按期间汇总
            anomalies: 异常项列表
            anomalies_df: 异常项DataFrame
            output_path: 输出文件路径
        """
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
        """创建单元格格式"""
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
            'sub_header': workbook.add_format({
                'bold': True,
                'font_size': 11,
                'bg_color': '#F2F2F2',
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
            'favorable': workbook.add_format({
                'border': 1,
                'num_format': '+#,##0.00;-#,##0.00',
                'font_color': 'green',
                'bold': True
            }),
            'unfavorable': workbook.add_format({
                'border': 1,
                'num_format': '+#,##0.00;-#,##0.00',
                'font_color': 'red',
                'bold': True
            }),
            'favorable_pct': workbook.add_format({
                'border': 1,
                'num_format': '+0.00%;-0.00%',
                'font_color': 'green',
                'bold': True
            }),
            'unfavorable_pct': workbook.add_format({
                'border': 1,
                'num_format': '+0.00%;-0.00%',
                'font_color': 'red',
                'bold': True
            }),
            'label': workbook.add_format({
                'bold': True,
                'font_size': 11
            }),
            'good_status': workbook.add_format({
                'border': 1,
                'bg_color': '#C6EFCE',
                'font_color': '#006100',
                'bold': True
            }),
            'bad_status': workbook.add_format({
                'border': 1,
                'bg_color': '#FFC7CE',
                'font_color': '#9C0006',
                'bold': True
            }),
            'info': workbook.add_format({
                'italic': True,
                'font_color': '#808080'
            })
        }
        return formats

    def _create_cover_sheet(self, workbook: xlsxwriter.Workbook, formats: dict,
                            account_summary: pd.DataFrame, period_summary: pd.DataFrame) -> None:
        """创建封面/概览工作表"""
        worksheet = workbook.add_worksheet('报告概览')
        worksheet.set_column('A:A', 3)
        worksheet.set_column('B:B', 25)
        worksheet.set_column('C:C', 20)
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
        row += 2

        total_budget = account_summary['预算金额'].sum()
        total_actual = account_summary['实际金额'].sum()
        total_variance = account_summary['绝对差异'].sum()
        total_relative = (total_variance / total_budget * 100) if total_budget != 0 else 0

        worksheet.merge_range('B7:E7', '核心指标', formats['header'])
        row += 1

        kpi_data = [
            ('预算总额', total_budget, formats['normal']),
            ('实际总额', total_actual, formats['normal']),
            ('总差异', total_variance, formats['favorable'] if total_variance >= 0 else formats['unfavorable']),
            ('总差异率', total_relative / 100, formats['favorable_pct'] if total_variance >= 0 else formats['unfavorable_pct'])
        ]

        for i, (label, value, fmt) in enumerate(kpi_data):
            worksheet.write(row + i, 1, label, formats['label'])
            worksheet.write(row + i, 2, value, fmt)

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
        worksheet.write(row, 1, '3. 【待核实】标记的成因需人工确认', formats['info'])

    def _create_account_summary_sheet(self, workbook: xlsxwriter.Workbook, formats: dict,
                                      account_summary: pd.DataFrame) -> None:
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

            var_fmt = formats['favorable'] if row['绝对差异'] >= 0 else formats['unfavorable']
            worksheet.write(row_idx, 4, row['绝对差异'], var_fmt)

            pct_fmt = formats['favorable_pct'] if row['相对差异(%)'] >= 0 else formats['unfavorable_pct']
            worksheet.write(row_idx, 5, row['相对差异(%)'] / 100, pct_fmt)

        worksheet.freeze_panes(1, 2)
        worksheet.autofilter(0, 0, len(account_summary), len(headers) - 1)

    def _create_period_summary_sheet(self, workbook: xlsxwriter.Workbook, formats: dict,
                                     period_summary: pd.DataFrame) -> None:
        """创建期间汇总工作表"""
        worksheet = workbook.add_worksheet('期间趋势分析')

        headers = ['期间', '预算金额', '实际金额', '期间差异', '差异率', '累计偏离']
        col_widths = [10, 15, 15, 15, 12, 15]

        for i, (header, width) in enumerate(zip(headers, col_widths)):
            worksheet.write(0, i, header, formats['header'])
            worksheet.set_column(i, i, width)

        for row_idx, (_, row) in enumerate(period_summary.iterrows(), 1):
            worksheet.write(row_idx, 0, row['期间'], formats['text'])
            worksheet.write(row_idx, 1, row['预算金额'], formats['normal'])
            worksheet.write(row_idx, 2, row['实际金额'], formats['normal'])

            var_fmt = formats['favorable'] if row['绝对差异'] >= 0 else formats['unfavorable']
            worksheet.write(row_idx, 3, row['绝对差异'], var_fmt)

            pct_fmt = formats['favorable_pct'] if row['相对差异(%)'] >= 0 else formats['unfavorable_pct']
            worksheet.write(row_idx, 4, row['相对差异(%)'] / 100, pct_fmt)

            cum_fmt = formats['favorable'] if row['累计偏离'] >= 0 else formats['unfavorable']
            worksheet.write(row_idx, 5, row['累计偏离'], cum_fmt)

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

    def _create_anomalies_sheet(self, workbook: xlsxwriter.Workbook, formats: dict,
                                anomalies_df: pd.DataFrame) -> None:
        """创建异常分析工作表"""
        worksheet = workbook.add_worksheet('重大异常分析')

        worksheet.merge_range('A1:H1', f'重大异常分析（Top {len(anomalies_df)}）', formats['title'])
        worksheet.set_row(0, 30)

        worksheet.write('A2', f'异常阈值：{self.config.anomaly_threshold * 100:.0f}%', formats['info'])
        worksheet.write('B2', '说明：【待核实】标记的成因需人工核实确认', formats['info'])

        if anomalies_df.empty:
            worksheet.write('A4', '✅ 未发现超过阈值的异常项，整体表现平稳。', formats['good_status'])
            return

        headers = ['排名', '科目编码', '科目名称', '期间', '绝对差异', '相对差异', '影响分数', '差异类型', '成因分析（待核实）']
        col_widths = [6, 10, 18, 8, 15, 12, 10, 10, 40]

        for i, (header, width) in enumerate(zip(headers, col_widths)):
            worksheet.write(3, i, header, formats['header'])
            worksheet.set_column(i, i, width)

        for row_idx, (_, row) in enumerate(anomalies_df.iterrows(), 4):
            worksheet.write(row_idx, 0, row['排名'], formats['integer'])
            worksheet.write(row_idx, 1, row['科目编码'], formats['text'])
            worksheet.write(row_idx, 2, row['科目名称'], formats['text'])
            worksheet.write(row_idx, 3, row['期间'], formats['text'])

            var_fmt = formats['favorable'] if row['绝对差异'] >= 0 else formats['unfavorable']
            worksheet.write(row_idx, 4, row['绝对差异'], var_fmt)

            pct_fmt = formats['favorable_pct'] if row['相对差异(%)'] >= 0 else formats['unfavorable_pct']
            worksheet.write(row_idx, 5, row['相对差异(%)'] / 100, pct_fmt)

            worksheet.write(row_idx, 6, row['影响分数'], formats['normal'])

            type_fmt = formats['good_status'] if row['差异类型'] == '有利差异' else formats['bad_status']
            worksheet.write(row_idx, 7, row['差异类型'], type_fmt)

            worksheet.write(row_idx, 8, row['成因分析（待核实）'], formats['text'])

        worksheet.freeze_panes(4, 3)

        row = len(anomalies_df) + 5
        worksheet.merge_range(f'A{row}:I{row}', '行动建议', formats['header'])
        row += 1
        suggestions = [
            '1. 针对上述异常项，财务部门应协同业务部门核实具体原因',
            '2. 对于重大不利差异，需制定相应的改进措施和时间节点',
            '3. 对于重大有利差异，需总结经验并考虑是否调整后续预算',
            '4. 所有成因核实后，请更新本报告中的"成因分析"列'
        ]
        for i, suggestion in enumerate(suggestions):
            worksheet.write(row + i, 0, suggestion, formats['info'])

    def _create_cumulative_sheet(self, workbook: xlsxwriter.Workbook, formats: dict,
                                 variance_df: pd.DataFrame) -> None:
        """创建累计偏离分析工作表"""
        latest_period = variance_df['期间'].iloc[-1]
        latest_data = variance_df[variance_df['期间'] == latest_period].copy()
        latest_data = latest_data.sort_values('累计偏离', key=lambda x: x.abs(), ascending=False)

        worksheet = workbook.add_worksheet('累计偏离分析')

        worksheet.merge_range('A1:F1', f'累计偏离分析（截至 {latest_period}）', formats['title'])
        worksheet.set_row(0, 30)

        headers = ['科目编码', '科目名称', '累计预算', '累计实际', '累计偏离', '累计偏离率']
        col_widths = [12, 20, 15, 15, 15, 12]

        for i, (header, width) in enumerate(zip(headers, col_widths)):
            worksheet.write(2, i, header, formats['header'])
            worksheet.set_column(i, i, width)

        for row_idx, (_, row) in enumerate(latest_data.iterrows(), 3):
            worksheet.write(row_idx, 0, row['科目编码'], formats['text'])
            worksheet.write(row_idx, 1, row['科目名称'], formats['text'])
            worksheet.write(row_idx, 2, row['累计预算'], formats['normal'])
            worksheet.write(row_idx, 3, row['累计实际'], formats['normal'])

            var_fmt = formats['favorable'] if row['累计偏离'] >= 0 else formats['unfavorable']
            worksheet.write(row_idx, 4, row['累计偏离'], var_fmt)

            pct_fmt = formats['favorable_pct'] if row['累计相对偏离(%)'] >= 0 else formats['unfavorable_pct']
            worksheet.write(row_idx, 5, row['累计相对偏离(%)'] / 100, pct_fmt)

        worksheet.freeze_panes(3, 2)

    def _create_detailed_sheet(self, workbook: xlsxwriter.Workbook, formats: dict,
                               variance_df: pd.DataFrame) -> None:
        """创建详细差异数据表"""
        worksheet = workbook.add_worksheet('详细数据')

        headers = ['科目编码', '科目名称', '期间', '预算金额', '实际金额',
                   '绝对差异', '相对差异(%)', '累计预算', '累计实际', '累计偏离', '累计相对偏离(%)']
        col_widths = [12, 18, 8, 12, 12, 12, 12, 12, 12, 12, 14]

        for i, (header, width) in enumerate(zip(headers, col_widths)):
            worksheet.write(0, i, header, formats['header'])
            worksheet.set_column(i, i, width)

        for row_idx, (_, row) in enumerate(variance_df.iterrows(), 1):
            worksheet.write(row_idx, 0, row['科目编码'], formats['text'])
            worksheet.write(row_idx, 1, row['科目名称'], formats['text'])
            worksheet.write(row_idx, 2, row['期间'], formats['text'])
            worksheet.write(row_idx, 3, row['预算金额'], formats['normal'])
            worksheet.write(row_idx, 4, row['实际金额'], formats['normal'])

            abs_var_fmt = formats['favorable'] if row['绝对差异'] >= 0 else formats['unfavorable']
            worksheet.write(row_idx, 5, row['绝对差异'], abs_var_fmt)

            rel_var_fmt = formats['favorable_pct'] if row['相对差异(%)'] >= 0 else formats['unfavorable_pct']
            worksheet.write(row_idx, 6, row['相对差异(%)'] / 100, rel_var_fmt)

            worksheet.write(row_idx, 7, row['累计预算'], formats['normal'])
            worksheet.write(row_idx, 8, row['累计实际'], formats['normal'])

            cum_var_fmt = formats['favorable'] if row['累计偏离'] >= 0 else formats['unfavorable']
            worksheet.write(row_idx, 9, row['累计偏离'], cum_var_fmt)

            cum_rel_fmt = formats['favorable_pct'] if row['累计相对偏离(%)'] >= 0 else formats['unfavorable_pct']
            worksheet.write(row_idx, 10, row['累计相对偏离(%)'] / 100, cum_rel_fmt)

        worksheet.freeze_panes(1, 3)
        worksheet.autofilter(0, 0, len(variance_df), len(headers) - 1)
