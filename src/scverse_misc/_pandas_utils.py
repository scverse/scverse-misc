from collections.abc import Mapping
from contextlib import suppress

import pandas as pd


def try_convert_series_to_numpy_dtype(col: pd.Series) -> pd.Series:
    """Attempt to convert a :class:`~pandas.Series` to a non-nullable dtype.

    Args:
        col: The series to be converted.

    Returns:
        The converted series, `col` did not contain any :data:`~pandas.NA` values, the unmodified `col` otherwise.
    """
    with suppress(ValueError):
        match col.dtype:
            case pd.BooleanDtype():
                col = col.astype(bool)
            case pd.core.arrays.integer.IntegerDtype(type=dtype) | pd.core.arrays.floating.FloatingDtype(type=dtype):
                col = col.astype(dtype)
    return col


def try_convert_dataframe_to_numpy_dtypes(df: pd.DataFrame | Mapping[str, pd.Series]) -> pd.DataFrame:
    """Attempt to convert all columns of a :class:`~pandas.DataFrame` to their respective non-nullable dtype.

    Args:
        df: The dataframe to be converted.

    Returns:
        A new dataframe with each column of `df` that had a nullable dtype but did not contain any :data:`~pandas.NA`
        values converted to the corresponding non-nullable dtype.
    """
    new_cols = {}
    for colname, col in df.items():
        new_cols[colname] = try_convert_series_to_numpy_dtype(col)
    return pd.DataFrame(new_cols)
