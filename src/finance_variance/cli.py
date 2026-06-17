import os
import sys
import click

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.finance_variance import ReportConfig
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
              help='分析起始期间，如"1月" (默认: 所有期间)')
@click.option('--end-period', default=None,
              help='分析结束期间，如"6月" (默认: 所有期间)')
def generate(budget, actual, output_dir, filename, file_type, company,
             title, threshold, top_n, start_period, end_period):
    """生成财务差异报告"""
    try:
        click.echo('🚀 开始生成财务差异报告...')

        config = ReportConfig(
            title=title,
            company_name=company,
            anomaly_threshold=threshold,
            top_n_anomalies=top_n,
            start_period=start_period,
            end_period=end_period
        )

        generator = FinanceVarianceReportGenerator(config)

        click.echo(f'📊 加载数据: {budget} 和 {actual}')
        generator.load_data(budget, actual, file_type)

        click.echo('🔢 计算差异...')
        generator.calculate()

        click.echo('🔍 检测异常...')
        anomalies, anomalies_df = generator.detect_anomalies()
        click.echo(f'   发现 {len(anomalies)} 个异常项')

        click.echo('📝 生成报告...')
        md_path, xlsx_path = generator.generate_all(output_dir, filename)

        click.echo('\n✅ 报告生成完成!')
        click.echo(f'   📄 Markdown: {md_path}')
        click.echo(f'   📊 Excel: {xlsx_path}')

    except Exception as e:
        click.echo(f'\n❌ 错误: {str(e)}', err=True)
        sys.exit(1)


@cli.command()
def version():
    """显示版本信息"""
    click.echo('财务差异报告生成器 v1.0.0')


if __name__ == '__main__':
    cli()
