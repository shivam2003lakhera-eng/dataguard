import json

import pandas as pd

from app.connectors.base import BaseConnector
from app.connectors.file_utils import resolve_safe_path
from app.core.exceptions import InvalidSourceDataError


class JsonConnector(BaseConnector):
    """Reads a JSON file from the approved input directory."""

    allowed_extensions = {".json"}

    def __init__(self, relative_path: str, records_key: str | None = None) -> None:
        self.relative_path = relative_path
        self.records_key = records_key

    def read(self) -> pd.DataFrame:
        path = resolve_safe_path(self.relative_path, self.allowed_extensions)
        try:
            with path.open(encoding="utf-8") as file:
                content = json.load(file)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise InvalidSourceDataError(
                "JSON file could not be parsed.", {"path": self.relative_path}
            ) from exc

        records = self._select_records(content)
        return pd.json_normalize(records)

    def _select_records(self, content) -> list[dict]:
        if self.records_key is not None:
            if not isinstance(content, dict) or self.records_key not in content:
                raise InvalidSourceDataError(
                    "records_key was not found in the JSON file.",
                    {"records_key": self.records_key},
                )
            content = content[self.records_key]

        if not isinstance(content, list) or not all(
            isinstance(item, dict) for item in content
        ):
            raise InvalidSourceDataError(
                "JSON must contain a list of records (objects).",
                {"path": self.relative_path},
            )
        return content