"""表格数据清洗辅助函数。"""

from typing import TypeVar


RowT = TypeVar("RowT")


def normalize_table_rows(rows: list[RowT]) -> list[RowT]:
    """预留表格行清洗入口，后续可在此统一做空值与格式标准化。"""
    return rows
