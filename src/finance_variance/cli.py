import os
import sys
import click

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.finance_variance import ReportConfig, ExcelColorConfig
from src.finance_variance.report_generator import FinanceVarianceReportGenerator


@click.group()
def cli():
    """财务差异报告生成器"""
    pass


@cli.command()
@click.option('--budget', '-b', required=True, type=click.Path(exists=True),
              help='预算表文件路径 (CSV或Excel)')
@click.option('--actual', '-a', required=True, type=click.Path(exists=True),
              help='实际发生表文件路径 (CSV或Excel)')
@click.option('--output-dir', '-o', required=True, type=click.Path(),
              help='报告输出目录')
@click.option('--filename', '-f', default='finance_variance_report',
              help='输出文件名前缀 (默认: finance_variance_report)')
@click.option('--file-type', '-t', default='csv',
              type=click.Choice(['csv', 'excel']),
              help='输入文件类型 (默认: csv)')
@click.option('--company', default='示例公司',
              help='公司名称 (默认: 示例公司)')
@click.option('--title', default='财务差异分析报告',
              help='报告标题 (默认: 财务差异分析报告)')
@click.option('--threshold', default=0.10, type=float,
              help='异常阈值，相对差异百分比 (默认: 0.10，即10%)')
@click.option('--top-n', default=10, type=int,
              help='显示Top N异常 (默认: 10)')
@click.option('--start-period', default=None,
              help='分析起始期间，如"1月"、"2024年第1季度"、"2024年上半年" (默认: 所有期间)')
@click.option('--end-period', default=None,
              help='分析结束期间，如"6月"、"2024年第3季度"、"2025年下半年" (默认: 所有期间)')
@click.option('--cause-templates', default=None, type=click.Path(),
              help='成因模板YAML配置文件路径 (默认: config/cause_templates.yaml)')
@click.option('--separate-groups/--no-separate-groups', default=True,
              help='异常排序是否按超支/节省分组 (默认: 开启)')
@click.option('--color-level1', default=0.05, type=float,
              help='Excel颜色一级阈值 (默认: 0.05，即5%)')
@click.option('--color-level2', default=0.10, type=float,
              help='Excel颜色二级阈值 (默认: 0.10，即10%)')
@click.option('--color-level3', default=0.20, type=float,
              help='Excel颜色三级阈值 (默认: 0.20，即20%)')
def generate(budget, actual, output_dir, filename, file_type, company,
             title, threshold, top_n, start_period, end_period,
             cause_templates, separate_groups,
             color_level1, color_level2, color_level3):
    """生成财务差异报告"""
    try:
        click.echo('🚀 开始生成财务差异报告...')

        color_config = ExcelColorConfig(
            level1_threshold=color_level1,
            level2_threshold=color_level2,
            level3_threshold=color_level3
        )

        config = ReportConfig(
            title=title,
            company_name=company,
            anomaly_threshold=threshold,
            top_n_anomalies=top_n,
            start_period=start_period,
            end_period=end_period,
            cause_templates_path=cause_templates,
            separate_anomaly_groups=separate_groups,
            excel_color_config=color_config
        )

        generator = FinanceVarianceReportGenerator(config)

        click.echo(f'📊 加载数据: {budget} 和 {actual}')
        generator.load_data(budget, actual, file_type)

        click.echo('🔢 计算差异...')
        generator.calculate()

        click.echo('🔍 检测异常...')
        anomalies, anomalies_df = generator.detect_anomalies()
        click.echo(f'   发现 {len(anomalies)} 个异常项')
        if separate_groups and '分组' in anomalies_df.columns:
            bad = anomalies_df[anomalies_df['分组'] == '超支组']
            good = anomalies_df[anomalies_df['分组'] == '节省组']
            click.echo(f'   ├─ 超支组（不利）: {len(bad)} 个')
            click.echo(f'   └─ 节省组（有利）: {len(good)} 个')

        click.echo('📝 生成报告...')
        md_path, xlsx_path = generator.generate_all(output_dir, filename)

        click.echo('\n✅ 报告生成完成!')
        click.echo(f'   📄 Markdown: {md_path}')
        click.echo(f'   📊 Excel: {xlsx_path}')

    except Exception as e:
        click.echo(f'\n❌ 错误: {str(e)}', err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.option('--template-path', '-p', default=None, type=click.Path(),
              help='模板文件路径 (默认: config/cause_templates.yaml)')
def init_cause_templates(template_path):
    """生成默认成因模板YAML文件，供运营自定义"""
    import yaml
    default_path = template_path or os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        'config', 'cause_templates.yaml'
    )
    os.makedirs(os.path.dirname(default_path), exist_ok=True)

    default_templates = {
        'revenue_unfavorable': [
            '【待核实】市场需求下降，实际销量低于预期',
            '【待核实】产品定价策略调整，客单价下降',
            '【待核实】主要客户流失或订单延迟确认',
            '【待核实】季节性因素影响本期收入确认'
        ],
        'revenue_favorable': [
            '【待核实】市场推广活动效果超预期，新增客户贡献显著',
            '【待核实】高毛利产品销售占比提升',
            '【待核实】本期确认了往期延迟的大额订单',
            '【待核实】产品成功提价且销量未受明显影响'
        ],
        'cost_unfavorable': [
            '【待核实】原材料价格上涨超出预算',
            '【待核实】产能利用率不足导致单位固定成本上升',
            '【待核实】一次性费用支出或预算外开支',
            '【待核实】人员成本增加（新增编制/加班/奖金）'
        ],
        'cost_favorable': [
            '【待核实】供应链优化或集中采购降低了原材料成本',
            '【待核实】费用管控措施见效，各项开支节约',
            '【待核实】部分预算内项目延期至下期执行',
            '【待核实】产能利用率提升摊薄了单位固定成本'
        ],
        'excel_colors': {
            'level1_threshold': 0.05,
            'level2_threshold': 0.10,
            'level3_threshold': 0.20,
            'favorable_level1_bg': '#E8F5E9',
            'favorable_level1_font': '#2E7D32',
            'favorable_level2_bg': '#A5D6A7',
            'favorable_level2_font': '#1B5E20',
            'favorable_level3_bg': '#43A047',
            'favorable_level3_font': '#FFFFFF',
            'unfavorable_level1_bg': '#FFEBEE',
            'unfavorable_level1_font': '#C62828',
            'unfavorable_level2_bg': '#EF9A9A',
            'unfavorable_level2_font': '#7F0000',
            'unfavorable_level3_bg': '#E53935',
            'unfavorable_level3_font': '#FFFFFF',
            'neutral_bg': '#FFFFFF',
            'neutral_font': '#212121',
        },
        'note': (
            '运营自定义说明：合法键为 revenue_unfavorable / revenue_favorable / '
            'cost_unfavorable / cost_favorable / excel_colors。'
            '键名拼写错误会产生警告。Excel 颜色请使用 6 位 HEX。'
        )
    }

    with open(default_path, 'w', encoding='utf-8') as f:
        yaml.dump(default_templates, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    click.echo(f'✅ 默认配置（成因模板 + Excel 企业色）已生成: {default_path}')
    click.echo('📝 运营团队可直接编辑此文件自定义成因与配色，无需修改代码。')


@cli.command()
def version():
    """显示版本信息"""
    click.echo('财务差异报告生成器 v1.2.0')
    click.echo('')
    click.echo('v1.2.0 补丁更新:')
    click.echo('  • 调整: inf / None 统一语义为 NaN，pandas 列类型一致 (展示层通过 budget/actual 判读 ∞%/N/A)')
    click.echo('  • 新增: 超支/节省合并 Top-N 接口，客户端一次取完整异常列表，附 get_anomaly_groups()')
    click.echo('  • 新增: YAML 字段名校验加严，未知键产生警告 (防止运营写错字段后静默降级)')
    click.echo('  • 新增: Excel 颜色 HEX 全部挪到 YAML excel_colors 节，运营可改企业色')
    click.echo('  • 新增: 多期日期解析支持「上半年」「下半年」「H1」「H2」「YYYY年上半年」等格式')
    click.echo('')
    click.echo('v1.1.0 补丁更新:')
    click.echo('  • 修复: 相对差异公式 budget=0 时避免 ZeroDivisionError')
    click.echo('  • 新增: 异常排序拆分超支/节省两组，分别按金额排序')
    click.echo('  • 新增: 成因占位符挪到 YAML 配置，支持运营自定义')
    click.echo('  • 新增: Excel 单元格颜色阈值三档可调（config 配置）')
    click.echo('  • 新增: 多期日期解析支持 "YYYY 第 Q 季度" 文本格式')


if __name__ == '__main__':
    cli()
