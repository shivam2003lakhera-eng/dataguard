import pandas as pd
from pandas.errors import EmptyDataError, ParserError

from app.connectors.base import BaseConnector
from app.connectors.file_utils import resolve_safe_path
from app.core.exceptions import InvalidSourceDataError


class CsvConnector(BaseConnector):
    """Reads a CSV file from the approved input directory."""

    allowed_extensions = {".csv"}

    def __init__(self, relative_path: str) -> None:
        self.relative_path = relative_path

    def read(self):
        path = resolve_safe_path(self.relative_path, self.allowed_extensions)
        try:
            return pd.read_csv(path, dtype=str)
        except EmptyDataError as exc:
            raise InvalidSourceDataError(
                "CSV file is empty.", {"path": self.relative_path}
            ) from exc
        except (ParserError, UnicodeDecodeError) as exc:
            raise InvalidSourceDataError(
                "CSV file could not be parsed.", {"path": self.relative_path}
            ) from exc