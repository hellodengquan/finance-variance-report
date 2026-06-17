import os
import pandas as pd
from typing import Optional
from .models import FinancialData


class DataLoader:
    """财务数据加载器"""

    @staticmethod
    def load_from_csv(budget_path: str, actual_path: str) -> tuple[FinancialData, FinancialData]:
        """
        从CSV文件加载预算和实际数据

        Args:
            budget_path: 预算表CSV文件路径
            actual_path: 实际发生表CSV文件路径

        Returns:
            (预算数据, 实际数据)
        """
        budget_df = DataLoader._read_csv(budget_path)
        actual_df = DataLoader._read_csv(actual_path)

        DataLoader._validate_data(budget_df, actual_df)

        return FinancialData(budget_df), FinancialData(actual_df)

    @staticmethod
    def load_from_excel(budget_path: str, actual_path: str,
                        budget_sheet: str = 0, actual_sheet: str = 0) -> tuple[FinancialData, FinancialData]:
        """
        从Excel文件加载预算和实际数据

        Args:
            budget_path: 预算表Excel文件路径
            actual_path: 实际发生表Excel文件路径
            budget_sheet: 预算表工作表名或索引
            actual_sheet: 实际表工作表名或索引

        Returns:
            (预算数据, 实际数据)
        """
        budget_df = DataLoader._read_excel(budget_path, budget_sheet)
        actual_df = DataLoader._read_excel(actual_path, actual_sheet)

        DataLoader._validate_data(budget_df, actual_df)

        return FinancialData(budget_df), FinancialData(actual_df)

    @staticmethod
    def _read_csv(file_path: str) -> pd.DataFrame:
        """读取CSV文件"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        df = pd.read_csv(file_path, dtype={'科目编码': str})
        return df

    @staticmethod
    def _read_excel(file_path: str, sheet_name: str | int = 0) -> pd.DataFrame:
        """读取Excel文件"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        df = pd.read_excel(file_path, sheet_name=sheet_name, dtype={'科目编码': str})
        return df

    @staticmethod
    def _validate_data(budget_df: pd.DataFrame, actual_df: pd.DataFrame) -> None:
        """验证数据格式和一致性"""
        required_columns = ['科目编码', '科目名称']

        for col in required_columns:
            if col not in budget_df.columns:
                raise ValueError(f"预算表缺少必要列: {col}")
            if col not in actual_df.columns:
                raise ValueError(f"实际表缺少必要列: {col}")

        budget_periods = [col for col in budget_df.columns if col not in required_columns]
        actual_periods = [col for col in actual_df.columns if col not in required_columns]

        if not budget_periods:
            raise ValueError("预算表未包含任何期间数据列")
        if not actual_periods:
            raise ValueError("实际表未包含任何期间数据列")

        if set(budget_periods) != set(actual_periods):
            raise ValueError(
                f"预算表和实际表的期间列不一致\n"
                f"预算表期间: {budget_periods}\n"
                f"实际表期间: {actual_periods}"
            )

        budget_accounts = set(budget_df['科目编码'].astype(str))
        actual_accounts = set(actual_df['科目编码'].astype(str))

        if budget_accounts != actual_accounts:
            missing_in_actual = budget_accounts - actual_accounts
            missing_in_budget = actual_accounts - budget_accounts
            raise ValueError(
                f"预算表和实际表的科目编码不一致\n"
                f"预算表有但实际表没有: {missing_in_actual}\n"
                f"实际表有但预算表没有: {missing_in_budget}"
            )
