import os
from typing import Optional, Tuple
import pandas as pd
from .models import ReportConfig, VarianceResult, AnomalyItem
from .data_loader import DataLoader
from .variance_calculator import VarianceCalculator
from .anomaly_detector import AnomalyDetector
from .markdown_reporter import MarkdownReporter
from .excel_reporter import ExcelReporter


class FinanceVarianceReportGenerator:
    """财务差异报告生成器主类"""

    def __init__(self, config: Optional[ReportConfig] = None):
        self.config = config or ReportConfig()
        self.data_loader = DataLoader()
        self.variance_calculator: Optional[VarianceCalculator] = None
        self.anomaly_detector = AnomalyDetector(self.config)
        self.markdown_reporter = MarkdownReporter(self.config)
        self.excel_reporter = ExcelReporter(self.config)

        self.budget_data = None
        self.actual_data = None
        self.variance_results = None
        self.variance_df = None
        self.account_summary = None
        self.period_summary = None
        self.anomalies = None
        self.anomalies_df = None

    def load_data(self, budget_path: str, actual_path: str,
                  file_type: str = 'csv',
                  budget_sheet: str | int = 0,
                  actual_sheet: str | int = 0) -> None:
        """
        加载预算和实际数据

        Args:
            budget_path: 预算表文件路径
            actual_path: 实际发生表文件路径
            file_type: 文件类型，'csv' 或 'excel'
            budget_sheet: Excel时的预算工作表名或索引
            actual_sheet: Excel时的实际工作表名或索引
        """
        if file_type.lower() == 'csv':
            self.budget_data, self.actual_data = self.data_loader.load_from_csv(
                budget_path, actual_path
            )
        elif file_type.lower() in ['excel', 'xlsx', 'xls']:
            self.budget_data, self.actual_data = self.data_loader.load_from_excel(
                budget_path, actual_path, budget_sheet, actual_sheet
            )
        else:
            raise ValueError(f"不支持的文件类型: {file_type}")

        self.variance_calculator = VarianceCalculator(
            self.budget_data, self.actual_data, self.config
        )

    def calculate(self) -> Tuple[list[VarianceResult], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        计算差异

        Returns:
            (差异结果列表, 差异DataFrame, 按科目汇总, 按期间汇总)
        """
        if self.variance_calculator is None:
            raise ValueError("请先调用 load_data 加载数据")

        self.variance_results = self.variance_calculator.calculate_variances()
        self.variance_df = self.variance_calculator.to_dataframe(self.variance_results)
        self.account_summary = self.variance_calculator.get_summary_by_account(self.variance_results)
        self.period_summary = self.variance_calculator.get_summary_by_period(self.variance_results)

        return self.variance_results, self.variance_df, self.account_summary, self.period_summary

    def detect_anomalies(self) -> Tuple[list[AnomalyItem], pd.DataFrame]:
        """
        检测异常

        Returns:
            (异常项列表, 异常DataFrame)
        """
        if self.variance_results is None:
            raise ValueError("请先调用 calculate 计算差异")

        self.anomalies = self.anomaly_detector.detect_anomalies(
            self.variance_results, self.variance_df
        )
        self.anomalies_df = self.anomaly_detector.anomalies_to_dataframe(self.anomalies)

        return self.anomalies, self.anomalies_df

    def generate_markdown(self, output_path: str) -> str:
        """
        生成 Markdown 报告

        Args:
            output_path: 输出文件路径

        Returns:
            报告内容
        """
        self._ensure_data_ready()

        return self.markdown_reporter.generate(
            self.variance_results,
            self.variance_df,
            self.account_summary,
            self.period_summary,
            self.anomalies,
            self.anomalies_df,
            output_path
        )

    def generate_excel(self, output_path: str) -> None:
        """
        生成 Excel 报告

        Args:
            output_path: 输出文件路径
        """
        self._ensure_data_ready()

        self.excel_reporter.generate(
            self.variance_results,
            self.variance_df,
            self.account_summary,
            self.period_summary,
            self.anomalies,
            self.anomalies_df,
            output_path
        )

    def generate_all(self, output_dir: str, filename_prefix: str = 'finance_variance_report') -> Tuple[str, str]:
        """
        生成所有格式的报告

        Args:
            output_dir: 输出目录
            filename_prefix: 文件名前缀

        Returns:
            (Markdown文件路径, Excel文件路径)
        """
        self._ensure_data_ready()

        os.makedirs(output_dir, exist_ok=True)

        md_path = os.path.join(output_dir, f'{filename_prefix}.md')
        xlsx_path = os.path.join(output_dir, f'{filename_prefix}.xlsx')

        self.generate_markdown(md_path)
        self.generate_excel(xlsx_path)

        return md_path, xlsx_path

    def run(self, budget_path: str, actual_path: str,
            output_dir: str, filename_prefix: str = 'finance_variance_report',
            file_type: str = 'csv') -> Tuple[str, str]:
        """
        一键运行完整流程

        Args:
            budget_path: 预算表文件路径
            actual_path: 实际发生表文件路径
            output_dir: 输出目录
            filename_prefix: 文件名前缀
            file_type: 文件类型

        Returns:
            (Markdown文件路径, Excel文件路径)
        """
        self.load_data(budget_path, actual_path, file_type)
        self.calculate()
        self.detect_anomalies()
        return self.generate_all(output_dir, filename_prefix)

    def _ensure_data_ready(self) -> None:
        """确保所有数据已准备好"""
        if self.variance_results is None:
            raise ValueError("请先调用 calculate 计算差异")
        if self.anomalies is None:
            raise ValueError("请先调用 detect_anomalies 检测异常")
