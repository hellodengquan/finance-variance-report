#!/usr/bin/env python3
"""测试脚本 - 验证财务差异报告生成器功能"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from src.finance_variance import ReportConfig
from src.finance_variance.report_generator import FinanceVarianceReportGenerator


def test_full_workflow():
    """测试完整工作流程"""
    print("=" * 60)
    print("🧪 开始测试财务差异报告生成器")
    print("=" * 60)

    base_dir = os.path.dirname(__file__)
    budget_path = os.path.join(base_dir, 'data', 'budget.csv')
    actual_path = os.path.join(base_dir, 'data', 'actual.csv')
    output_dir = os.path.join(base_dir, 'output')

    config = ReportConfig(
        title="2025年度财务差异分析报告",
        company_name="示例科技有限公司",
        anomaly_threshold=0.10,
        top_n_anomalies=10
    )

    print(f"\n📁 预算文件: {budget_path}")
    print(f"📁 实际文件: {actual_path}")
    print(f"📤 输出目录: {output_dir}")

    generator = FinanceVarianceReportGenerator(config)

    print("\n" + "-" * 60)
    print("📊 步骤1: 加载数据")
    print("-" * 60)
    generator.load_data(budget_path, actual_path, 'csv')
    print(f"   预算期间: {generator.budget_data.periods}")
    print(f"   预算科目数: {len(generator.budget_data.account_codes)}")
    print(f"   实际期间: {generator.actual_data.periods}")
    print(f"   实际科目数: {len(generator.actual_data.account_codes)}")
    print("   ✅ 数据加载成功")

    print("\n" + "-" * 60)
    print("🔢 步骤2: 计算差异")
    print("-" * 60)
    variance_results, variance_df, account_summary, period_summary = generator.calculate()
    print(f"   差异记录数: {len(variance_results)}")
    print(f"   科目汇总行数: {len(account_summary)}")
    print(f"   期间汇总行数: {len(period_summary)}")

    total_budget = account_summary['预算金额'].sum()
    total_actual = account_summary['实际金额'].sum()
    total_variance = account_summary['绝对差异'].sum()
    print(f"\n   预算总额: ¥{total_budget:,.2f}")
    print(f"   实际总额: ¥{total_actual:,.2f}")
    print(f"   总差异: ¥{total_variance:,.2f}")
    print(f"   总差异率: {total_variance/total_budget*100:.2f}%")
    print("   ✅ 差异计算成功")

    print("\n" + "-" * 60)
    print("🔍 步骤3: 检测异常")
    print("-" * 60)
    anomalies, anomalies_df = generator.detect_anomalies()
    print(f"   发现异常项数: {len(anomalies)}")

    if not anomalies_df.empty:
        print("\n   Top 5 异常项:")
        for _, row in anomalies_df.head(5).iterrows():
            sign = "+" if row['绝对差异'] >= 0 else ""
            print(f"     {row['排名']}. {row['科目名称']} ({row['期间']}): "
                  f"{sign}¥{row['绝对差异']:,.0f} ({sign}{row['相对差异(%)']:.2f}%) "
                  f"- {row['差异类型']}")
    print("   ✅ 异常检测成功")

    print("\n" + "-" * 60)
    print("📝 步骤4: 生成 Markdown 报告")
    print("-" * 60)
    md_path = os.path.join(output_dir, 'finance_variance_report.md')
    md_content = generator.generate_markdown(md_path)
    print(f"   文件路径: {md_path}")
    print(f"   文件大小: {os.path.getsize(md_path):,} bytes")
    print("   ✅ Markdown 报告生成成功")

    print("\n" + "-" * 60)
    print("📊 步骤5: 生成 Excel 报告")
    print("-" * 60)
    xlsx_path = os.path.join(output_dir, 'finance_variance_report.xlsx')
    generator.generate_excel(xlsx_path)
    print(f"   文件路径: {xlsx_path}")
    print(f"   文件大小: {os.path.getsize(xlsx_path):,} bytes")
    print("   ✅ Excel 报告生成成功")

    print("\n" + "=" * 60)
    print("🎉 所有测试通过!")
    print("=" * 60)

    print(f"\n📄 生成的文件:")
    print(f"   1. {md_path}")
    print(f"   2. {xlsx_path}")

    return True


def test_partial_period():
    """测试部分期间分析"""
    print("\n" + "=" * 60)
    print("🧪 测试部分期间分析（1月-6月）")
    print("=" * 60)

    base_dir = os.path.dirname(__file__)
    budget_path = os.path.join(base_dir, 'data', 'budget.csv')
    actual_path = os.path.join(base_dir, 'data', 'actual.csv')
    output_dir = os.path.join(base_dir, 'output')

    config = ReportConfig(
        title="2025年上半年财务差异分析报告",
        company_name="示例科技有限公司",
        start_period="1月",
        end_period="6月",
        anomaly_threshold=0.10,
        top_n_anomalies=5
    )

    generator = FinanceVarianceReportGenerator(config)
    generator.load_data(budget_path, actual_path, 'csv')
    generator.calculate()
    generator.detect_anomalies()

    md_path, xlsx_path = generator.generate_all(
        output_dir, 'finance_variance_report_h1'
    )

    print(f"   ✅ 上半年报告生成完成")
    print(f"   📄 Markdown: {md_path}")
    print(f"   📊 Excel: {xlsx_path}")

    return True


if __name__ == '__main__':
    try:
        success = test_full_workflow()
        if success:
            test_partial_period()
        print("\n✨ 所有测试完成!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
