# Copyright (c) Streamlit Inc. (2018-2022) Snowflake Inc. (2022)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from datetime import timedelta
from typing import List, Optional, Union, cast
from urllib.parse import parse_qs, urlparse

import duckdb
from gspread import service_account_from_dict
from gspread.client import Client as GSpreadClient
from gspread.client import SpreadsheetNotFound
from gspread.spreadsheet import Spreadsheet
from gspread.worksheet import Worksheet
from gspread_dataframe import get_as_dataframe, set_with_dataframe
from gspread_formatting.dataframe import (
    format_with_dataframe as set_format_with_dataframe,
)
from numpy import ndarray
from pandas import DataFrame, read_csv
from sql_metadata import Parser
from streamlit.connections import ExperimentalBaseConnection
from streamlit.runtime.caching import cache_data
from streamlit.type_util import convert_anything_to_df, is_dataframe_compatible
from validators.url import url as validate_url
from validators.utils import ValidationError


class GSheetsClient(ABC):
    _optional_client: Optional[GSpreadClient] = None
    _spreadsheet: Optional[str] = None
    _worksheet: Optional[str] = None

    def __init__(self, secrets_dict: dict):
        self._spreadsheet = secrets_dict.pop("spreadsheet", None)
        self._worksheet = secrets_dict.pop("worksheet", None)
        if secrets_dict.get("type", None) == "service_account":
            self._optional_client = service_account_from_dict(secrets_dict)

    def set_default(
        self,
        spreadsheet: str,
        *,  # keyword-only arguments:
        worksheet: Optional[str] = None,
    ):
        self._spreadsheet = spreadsheet
        self._worksheet = worksheet

    @abstractmethod
    def read(
        self,
        *,  # keyword-only arguments:
        spreadsheet: Optional[str] = None,
        worksheet: Optional[Union[int, str]] = None,
        ttl: Optional[Union[int, timedelta, None]] = 3600,
        max_entries: Optional[Union[int, None]] = None,
        evaluate_formulas: bool = True,
        folder_id: Optional[str] = None,
        **options,
    ) -> DataFrame:
        raise NotImplementedError

    @abstractmethod
    def query(
        self,
        sql: str,
        *,  # keyword-only arguments:
        spreadsheet: Optional[str] = None,
        worksheet: Optional[Union[int, str]] = None,
        ttl: Optional[Union[int, timedelta, None]] = 3600,
        max_entries: Optional[Union[int, None]] = None,
        evaluate_formulas: bool = True,
        folder_id: Optional[str] = None,
        **options,
    ) -> DataFrame:
        raise NotImplementedError

    @abstractmethod
    def create(
        self,
        *,  # keyword-only arguments:
        spreadsheet: Optional[str] = None,
        worksheet: Optional[str] = None,
        data: Optional[Union[DataFrame, ndarray, List[list], List[dict]]] = None,
        folder_id: Optional[str] = None,
    ) -> DataFrame | None:
        raise NotImplementedError

    @abstractmethod
    def update(
        self,
        *,  # keyword-only arguments:
        spreadsheet: Optional[Union[str, Spreadsheet]] = None,
        worksheet: Optional[Union[str, int, Worksheet]] = None,
        data: Optional[Union[DataFrame, ndarray, List[list], List[dict]]] = None,
        folder_id: Optional[str] = None,
    ) -> DataFrame | None:
        raise NotImplementedError

    @abstractmethod
    def clear(
        self,
        *,  # keyword-only arguments:
        spreadsheet: Optional[Union[str, Spreadsheet]] = None,
        worksheet: Optional[Union[str, int, Worksheet]] = None,
        folder_id: Optional[str] = None,
    ) -> dict:
        raise NotImplementedError


class GSheetsServiceAccountClient(GSheetsClient):
    def __init__(self, secrets_dict: dict):
        super().__init__(secrets_dict)
        self._client = cast(GSpreadClient, self._optional_client)

    def _open_spreadsheet(
        self,
        *,  # keyword-only arguments:
        spreadsheet: Optional[Union[str, Spreadsheet]] = None,
        folder_id: Optional[str] = None,
    ) -> Spreadsheet:
        if type(spreadsheet) is Spreadsheet:
            return spreadsheet

        if not spreadsheet and self._spreadsheet:
            spreadsheet = self._spreadsheet
        if not folder_id and self._worksheet:
            folder_id = self._worksheet

        try:
            if validate_url(spreadsheet):
                return self._client.open_by_url(url=spreadsheet)
            else:
                raise ValidationError(
                    "spreadsheet is not URL", arg_dict={"spreadsheet": spreadsheet}
                )
        except ValidationError:
            return self._client.open(title=spreadsheet, folder_id=folder_id)

    def _select_worksheet(
        self,
        *,  # keyword-only arguments:
        spreadsheet: Optional[Union[str, Spreadsheet]] = None,
        worksheet: Optional[Union[str, int, Worksheet]] = None,
        folder_id: Optional[str] = None,
    ) -> Worksheet:
        if type(worksheet) is Worksheet:
            return worksheet

        if not spreadsheet and self._spreadsheet:
            spreadsheet = self._spreadsheet
        if not folder_id and self._worksheet:
            folder_id = self._worksheet

        if isinstance(spreadsheet, str):
            spreadsheet = self._open_spreadsheet(
                spreadsheet=spreadsheet, folder_id=folder_id
            )

        if isinstance(worksheet, str):
            return spreadsheet.worksheet(worksheet)
        if not worksheet:
            worksheet = 0
        return spreadsheet.get_worksheet(worksheet)

    def read(
        self,
        *,  # keyword-only arguments:
        spreadsheet: Optional[str] = None,
        worksheet: Optional[Union[int, str]] = None,
        ttl: Optional[Union[int, timedelta, None]] = 3600,
        max_entries: Optional[Union[int, None]] = None,
        evaluate_formulas: bool = True,
        folder_id: Optional[str] = None,
        **options,
    ) -> DataFrame:
        if not spreadsheet and self._spreadsheet:
            spreadsheet = self._spreadsheet
        if not folder_id and self._worksheet:
            folder_id = self._worksheet

        @cache_data(ttl=ttl, max_entries=max_entries)
        def _get_as_dataframe(
            spreadsheet, folder_id, worksheet, evaluate_formulas, **options
        ):
            return get_as_dataframe(
                worksheet=self._select_worksheet(
                    spreadsheet=spreadsheet, folder_id=folder_id, worksheet=worksheet
                ),
                evaluate_formulas=evaluate_formulas,
                **options,
            )

        return _get_as_dataframe(
            spreadsheet,
            folder_id,
            worksheet,
            evaluate_formulas,
            **options,
        )

    def query(
        self,
        sql: str,
        *,  # keyword-only arguments:
        spreadsheet: Optional[str] = None,
        worksheet: Optional[Union[int, str]] = None,
        ttl: Optional[Union[int, timedelta, None]] = 3600,
        max_entries: Optional[Union[int, None]] = None,
        evaluate_formulas: bool = True,
        folder_id: Optional[str] = None,
        **options,
    ) -> DataFrame:
        if not spreadsheet and self._spreadsheet:
            spreadsheet = self._spreadsheet
        if not folder_id and self._worksheet:
            folder_id = self._worksheet

        @cache_data(ttl=ttl, max_entries=max_entries)
        def _query(sql, spreadsheet, folder_id, evaluate_formulas, **options):
            in_memory_db = duckdb.connect()
            for worksheet in Parser(sql).tables:
                df = DataFrame()
                create_table_sql = f'CREATE TABLE "{worksheet}" AS SELECT * FROM df'
                if not self._select_worksheet(
                    spreadsheet=spreadsheet, folder_id=folder_id, worksheet=worksheet
                ):
                    in_memory_db.sql(create_table_sql)
                    _ = df
                    continue
                df = self.read(
                    spreadsheet=spreadsheet,
                    folder_id=folder_id,
                    worksheet=worksheet,
                    ttl=ttl,
                    max_entries=max_entries,
                    evaluate_formulas=evaluate_formulas,
                    **options,
                )
                in_memory_db.sql(create_table_sql)
                _ = df
            return in_memory_db.sql(query=sql).to_df()

        return _query(sql, spreadsheet, folder_id, evaluate_formulas, **options)

    def create(
        self,
        *,  # keyword-only arguments:
        spreadsheet: Optional[str] = None,
        worksheet: Optional[str] = None,
        data: Optional[Union[DataFrame, ndarray, List[list], List[dict]]] = None,
        folder_id: Optional[str] = None,
    ) -> DataFrame | None:
        if not spreadsheet and self._spreadsheet:
            spreadsheet = self._spreadsheet
        else:
            raise ValueError("Spreadsheet must be specified")
        if not folder_id and self._worksheet:
            folder_id = self._worksheet

        try:
            new_spreadsheet = self._open_spreadsheet(
                spreadsheet=spreadsheet, folder_id=folder_id
            )
        except SpreadsheetNotFound:
            new_spreadsheet = self._client.create(
                title=spreadsheet, folder_id=folder_id
            )

        if is_dataframe_compatible(data):
            return_data = convert_anything_to_df(data)
        elif type(data) is ndarray:
            return_data = DataFrame.from_records(data)
        else:
            new_spreadsheet.add_worksheet(
                title=worksheet,
                rows=0,
                cols=0,
            )
            return None

        n_rows, n_cols = return_data.shape

        new_worksheet = new_spreadsheet.add_worksheet(
            title=worksheet, rows=n_rows, cols=n_cols
        )

        set_with_dataframe(new_worksheet, return_data)
        set_format_with_dataframe(
            new_worksheet, return_data, include_column_header=True
        )

        return return_data

    def update(
        self,
        *,  # keyword-only arguments:
        spreadsheet: Optional[Union[str, Spreadsheet]] = None,
        worksheet: Optional[Union[str, int, Worksheet]] = None,
        data: Optional[Union[DataFrame, ndarray, List[list], List[dict]]] = None,
        folder_id: Optional[str] = None,
    ) -> DataFrame | None:
        if not spreadsheet and self._spreadsheet:
            spreadsheet = self._spreadsheet
        if not folder_id and self._worksheet:
            folder_id = self._worksheet

        if isinstance(spreadsheet, str):
            spreadsheet = self._open_spreadsheet(
                spreadsheet=spreadsheet, folder_id=folder_id
            )

        worksheet = self._select_worksheet(
            spreadsheet=spreadsheet, folder_id=folder_id, worksheet=worksheet
        )

        if is_dataframe_compatible(data):
            data = convert_anything_to_df(data)
        elif type(data) is ndarray:
            data = DataFrame.from_records(data)
        else:
            return None

        if worksheet:
            self.clear(
                spreadsheet=spreadsheet,
                folder_id=folder_id,
                worksheet=worksheet,
            )
        set_with_dataframe(worksheet, data)
        set_format_with_dataframe(worksheet, data, include_column_header=True)
        return data

    def clear(
        self,
        *,  # keyword-only arguments:
        spreadsheet: Optional[Union[str, Spreadsheet]] = None,
        worksheet: Optional[Union[str, int, Worksheet]] = None,
        folder_id: Optional[str] = None,
    ) -> dict:
        return self._select_worksheet(
            spreadsheet=spreadsheet, worksheet=worksheet, folder_id=folder_id
        ).clear()


class UnsupportedOperationException(Exception):
    pass


class GSheetsPublicSpreadsheetClient(GSheetsClient):
    def _get_download_as_csv_url(
        self,
        *,  # keyword-only arguments:
        spreadsheet: str,
        worksheet: str | int | None = None,
    ) -> str:
        validation_failure = ValidationError(
            "spreadsheet validation failure",
            arg_dict={"spreadsheet": spreadsheet},
        )
        try:
            if validate_url(spreadsheet):  # type: ignore
                r = re.compile(r"\/d\/.+?(?=\/)")
                found_ids = r.findall(spreadsheet)
                if len(found_ids) < 1:
                    raise validation_failure
                key = found_ids[0][3:]
                parsed_url = urlparse(spreadsheet)
                parsed_qs = parse_qs(parsed_url.query)  # type: ignore
                frag = parsed_url.fragment
                gid_re = re.compile(r"gid=\w+")
                found_gids = gid_re.findall(frag)  # type: ignore
                final_gid = None
                if len(found_gids) > 0:
                    final_gid = found_gids[0][4:]
                elif parsed_qs.get("gid", []) and len(parsed_qs.get("gid", [])) > 0:  # type: ignore
                    final_gid = parsed_qs.get("gid", [""])[0]  # type: ignore
                if worksheet:
                    final_gid = worksheet
                url = f"https://docs.google.com/spreadsheet/ccc?key={key}&output=csv"
                if final_gid:
                    return f"{url}&gid={final_gid}"
                return url
            else:
                raise validation_failure
        except (ValidationError, TypeError):
            url = (
                f"https://docs.google.com/spreadsheet/ccc?key={spreadsheet}&output=csv"
            )
            if worksheet:
                return f"{url}&gid={worksheet}"
            return url

    def read(
        self,
        *,  # keyword-only arguments:
        spreadsheet: Optional[str] = None,
        worksheet: Optional[Union[int, str]] = None,
        ttl: Optional[Union[int, timedelta, None]] = 3600,
        max_entries: Optional[Union[int, None]] = None,
        **options,
    ) -> DataFrame:
        spreadsheet = spreadsheet or self._spreadsheet

        if not spreadsheet:
            raise ValueError("Spreadsheet must be specified")

        if not worksheet and self._worksheet:
            worksheet = self._worksheet
        url = self._get_download_as_csv_url(
            spreadsheet=spreadsheet, worksheet=worksheet
        )

        @cache_data(ttl=ttl, max_entries=max_entries)
        def _get_as_dataframe(url: str, **options) -> DataFrame:
            return read_csv(url, **options)

        for arg in ["evaluate_formulas", "folder_id"]:
            options.pop(arg, None)

        return _get_as_dataframe(url, **options)

    def query(
        self,
        sql: str,
        *,  # keyword-only arguments:
        spreadsheet: Optional[str] = None,
        worksheet: Optional[Union[int, str]] = None,
        ttl: Optional[Union[int, timedelta, None]] = 3600,
        max_entries: Optional[Union[int, None]] = None,
        **options,
    ) -> DataFrame:
        spreadsheet = spreadsheet or self._spreadsheet
        worksheet = worksheet or self._worksheet

        if not spreadsheet:
            raise ValueError("Spreadsheet must be specified")

        url = self._get_download_as_csv_url(
            spreadsheet=spreadsheet, worksheet=worksheet
        )

        @cache_data(ttl=ttl, max_entries=max_entries)
        def _query(sql: str, url: str, **options):
            in_memory_db = duckdb.connect()
            for worksheet in Parser(sql).tables:
                df = read_csv(url, **options)
                create_table_sql = f'CREATE TABLE "{worksheet}" AS SELECT * FROM df'
                in_memory_db.sql(create_table_sql)
                _ = df
            return in_memory_db.sql(query=sql).to_df()

        for arg in ["evaluate_formulas", "folder_id"]:
            options.pop(arg, None)

        return _query(sql, url, **options)

    def create(
        self,
        *,
        spreadsheet: Optional[str] = None,
        worksheet: Optional[str] = None,
        data: Optional[Union[DataFrame, ndarray, List[list], List[dict]]] = None,
        folder_id: Optional[str] = None,
    ) -> DataFrame:
        raise UnsupportedOperationException(
            "Use Service Account authentication to enable CRUD methods on your Spreadsheets."
        )

    def update(
        self,
        *,
        spreadsheet: Optional[Union[str, Spreadsheet]] = None,
        worksheet: Optional[Union[str, int, Worksheet]] = None,
        data: Optional[Union[DataFrame, ndarray, List[list], List[dict]]] = None,
        folder_id: Optional[str] = None,
    ) -> DataFrame:
        raise UnsupportedOperationException(
            "Public Spreadsheet cannot be written to, "
            "use Service Account authentication to enable CRUD methods on your Spreadsheets."
        )

    def clear(
        self,
        *,
        spreadsheet: Optional[Union[str, Spreadsheet]] = None,
        worksheet: Optional[Union[str, int, Worksheet]] = None,
        folder_id: Optional[str] = None,
    ):
        raise UnsupportedOperationException(
            "Public Spreadsheet cannot be cleared, "
            "use Service Account authentication to enable CRUD methods on your Spreadsheets."
        )


class GSheetsConnection(ExperimentalBaseConnection[GSheetsClient], GSheetsClient):
    def _connect(self, **kwargs) -> GSheetsClient:
        """Reads st.connection .streamlit/secrets.toml and returns GSheets
        client based on them."""
        secrets_dict = self._secrets.to_dict()
        if secrets_dict.get("type", None) == "service_account":
            return GSheetsServiceAccountClient(secrets_dict)
        return GSheetsPublicSpreadsheetClient(secrets_dict)

    @property
    def client(self) -> GSheetsClient:
        """Returns GSheets client instance."""
        return self._instance

    def read(
        self,
        *,
        spreadsheet: Optional[str] = None,
        worksheet: Optional[Union[int, str]] = None,
        ttl: Optional[Union[int, timedelta, None]] = 3600,
        max_entries: Optional[Union[int, None]] = None,
        evaluate_formulas: bool = True,
        folder_id: Optional[str] = None,
        **options,
    ) -> DataFrame:
        """Returns the worksheet contents as a DataFrame.

        Parameters
        ------------
        spreadsheet: str:
            When you're using Service Account its spreadsheet name, otherwise its public spreadsheet URL.
            Defaults to None. If None .streamlit/secrets.toml spreadsheet variable is used.
        worksheet: str or int
            When you're using Public Spreadsheet URL its GID of Worksheet you'd like to read.
            When you're using Service Account its worksheet name or worksheet index.
            Defaults to None. If none .streamlit/secrets.toml worksheet variable is used.
        evaluate_formulas: bool
            When you're using Public Spreadsheet URL evaluate_formulas is ignored.
            When you're using Service Account if True, get the value of a cell after formula evaluation,
            otherwise get the formula itself if present. Defaults to True.
        ttl : float or timedelta or None
            The maximum number of seconds to keep an entry in the cache, or
            None if cache entries should not expire. The default is None.
            Note that ttl is incompatible with ``persist="disk"`` - ``ttl`` will be
            ignored if ``persist`` is specified. Defaults to 3600 (1 hour).
        max_entries : int or None
            The maximum number of entries to keep in the cache, or None
            for an unbounded cache. (When a new entry is added to a full cache,
            the oldest cached entry will be removed.) The default is None.
        folder_id: Google API Folder id, Optional
            Optional folder_id where your spreadsheet resides.
        options: "pandas.io.parsers.TextParser"
            All the options for pandas.io.parsers.TextParser,
                according to the version of pandas that is installed.
                (Note: TextParser supports only the default 'python' parser engine,
                not the C engine.

        Returns
        -----------
        df: pandas.DataFrame.
        """
        return self.client.read(
            spreadsheet=spreadsheet,
            worksheet=worksheet,
            ttl=ttl,
            max_entries=max_entries,
            evaluate_formulas=evaluate_formulas,
            folder_id=folder_id,
            **options,
        )

    def query(
        self,
        sql: str,
        *,
        spreadsheet: Optional[str] = None,
        worksheet: Optional[Union[int, str]] = None,
        ttl: Optional[Union[int, timedelta, None]] = 3600,
        max_entries: Optional[Union[int, None]] = None,
        evaluate_formulas: bool = True,
        folder_id: Optional[str] = None,
        **options,
    ) -> DataFrame:
        """Run SQL query against spreadsheet. Worksheet name should be used as
        Table name inside double quotes. Use Worksheet name as target in SQL
        queries. When using Public Spreadsheet URL you can only select
        worksheet using GID passed as worksheet parameter.

        For example: select * from "Example 1" limit 10

        Parameters
        ------------
        sql: str:
            SQL query which will query your spreadsheet.
        spreadsheet: str:
            When you're using Service Account its spreadsheet name, otherwise its public spreadsheet URL.
            Defaults to None. If None .streamlit/secrets.toml spreadsheet variable is used.
        worksheet: str or int
            When you're using Public Spreadsheet URL its GID of Worksheet you'd like to read.
            When you're using Service Account its worksheet name or worksheet index.
            Defaults to None. If none .streamlit/secrets.toml worksheet variable is used.
        evaluate_formulas: bool
            When you're using Public Spreadsheet URL evaluate_formulas is ignored.
            When you're using Service Account if True, get the value of a cell after formula evaluation,
            otherwise get the formula itself if present. Defaults to True.
        ttl : float or timedelta or None
            The maximum number of seconds to keep an entry in the cache, or
            None if cache entries should not expire. The default is None.
            Note that ttl is incompatible with ``persist="disk"`` - ``ttl`` will be
            ignored if ``persist`` is specified. Defaults to 3600 (1 hour).
        max_entries : int or None
            The maximum number of entries to keep in the cache, or None
            for an unbounded cache. (When a new entry is added to a full cache,
            the oldest cached entry will be removed.) The default is None.
        folder_id: Google API Folder id, Optional
            Optional folder_id where your spreadsheet resides.
        options: "pandas.io.parsers.TextParser"
            All the options for pandas.io.parsers.TextParser,
                according to the version of pandas that is installed.
                (Note: TextParser supports only the default 'python' parser engine,
                not the C engine.

        Returns
        -----------
        df: pandas.DataFrame.
        """
        return self.client.query(
            sql=sql,
            spreadsheet=spreadsheet,
            worksheet=worksheet,
            ttl=ttl,
            max_entries=max_entries,
            evaluate_formulas=evaluate_formulas,
            folder_id=folder_id,
            **options,
        )

    def create(
        self,
        *,
        spreadsheet: Optional[str] = None,
        worksheet: Optional[str] = None,
        data: Optional[Union[DataFrame, ndarray, List[list], List[dict]]] = None,
        folder_id: Optional[str] = None,
    ) -> DataFrame | None:
        """Creates Google Worksheet and initializes it with provided data.

        Parameters
        ------------
        spreadsheet: str:
            When you're using Service Account its spreadsheet name, otherwise its public spreadsheet URL.
            Defaults to None. If None .streamlit/secrets.toml spreadsheet variable is used.
        worksheet: str or int
            When you're using Public Spreadsheet URL its GID of Worksheet you'd like to read.
            When you're using Service Account its worksheet name or worksheet index.
            Defaults to None. If none .streamlit/secrets.toml worksheet variable is used.
        data: DataFrame | ndarray | List[list] | List[dict]
            Your worksheet will be populated with provided Data.
            Supports DataFrame or data which is DataFrame compatible
            (will be converted to DataFrame on the fly).
        folder_id: Google API Folder id, Optional
            Optional folder_id where your spreadsheet resides.

        Returns
        -----------
        df: pandas.DataFrame.
        """
        return self.client.create(
            spreadsheet=spreadsheet, worksheet=worksheet, data=data, folder_id=folder_id
        )

    def update(
        self,
        *,
        spreadsheet: Optional[Union[str, Spreadsheet]] = None,
        worksheet: Optional[Union[str, int, Worksheet]] = None,
        data: Optional[Union[DataFrame, ndarray, List[list], List[dict]]] = None,
        folder_id: Optional[str] = None,
    ) -> DataFrame | None:
        """Updates Google Worksheet with provided data.

        Parameters
        ------------
        spreadsheet: str:
            When you're using Service Account its spreadsheet name, otherwise its public spreadsheet URL.
            Defaults to None. If None .streamlit/secrets.toml spreadsheet variable is used.
        worksheet: str or int
            When you're using Public Spreadsheet URL its GID of Worksheet you'd like to read.
            When you're using Service Account its worksheet name or worksheet index.
            Defaults to None. If none .streamlit/secrets.toml worksheet variable is used.
        data: DataFrame | ndarray | List[list] | List[dict]
            Your worksheet will be populated with provided Data.
            Supports DataFrame or data which is DataFrame compatible
            (will be converted to DataFrame on the fly).
        folder_id: Google API Folder id, Optional
            Optional folder_id where your spreadsheet resides.

        Returns
        -----------
        df: pandas.DataFrame.
        """
        return self.client.update(
            spreadsheet=spreadsheet, worksheet=worksheet, data=data, folder_id=folder_id
        )

    def clear(
        self,
        *,
        spreadsheet: Optional[Union[str, Spreadsheet]] = None,
        worksheet: Optional[Union[str, int, Worksheet]] = None,
        folder_id: Optional[str] = None,
    ) -> dict:
        """Clears a worksheet from a spreadsheet.

        Parameters
        ------------
        spreadsheet: str:
            When you're using Service Account its spreadsheet name, otherwise its public spreadsheet URL.
            Defaults to None. If None .streamlit/secrets.toml spreadsheet variable is used.
        worksheet: str or int
            When you're using Public Spreadsheet URL its GID of Worksheet you'd like to read.
            When you're using Service Account its worksheet name or worksheet index.
            Defaults to None. If none .streamlit/secrets.toml worksheet variable is used.
        folder_id: Google API Folder id, Optional
            Optional folder_id where your spreadsheet resides.


        Return
        -----------
        response: dict
            Google API GSpread clear response.
        """
        return self.client.clear(
            spreadsheet=spreadsheet, worksheet=worksheet, folder_id=folder_id
        )

    def set_default(
        self,
        spreadsheet: str,
        *,  # keyword-only arguments:
        worksheet: Optional[str] = None,
    ):
        """Sets default spreadsheet and worksheet, if spreadsheet/worksheet
        values were defined in .streamlit/secrets.toml overrides them.

        Parameters
        ------------
        spreadsheet: str:
            When you're using Service Account its spreadsheet name, otherwise its public spreadsheet URL.
            Defaults to None. If None .streamlit/secrets.toml spreadsheet variable is used.
        worksheet: str or int
            When you're using Public Spreadsheet URL its GID of Worksheet you'd like to read.
            When you're using Service Account its worksheet name or worksheet index.
            Defaults to None. If none .streamlit/secrets.toml worksheet variable is used.
        """
        return self.client.set_default(spreadsheet=spreadsheet, worksheet=worksheet)

    def _repr_html_(self) -> str:
        module_name = getattr(self, "__module__", None)
        class_name = type(self).__name__
        if self._connection_name:
            name = f"`{self._connection_name}` "
            if len(self._secrets) > 0:
                cfg = f"""- Configured from `[connections.{self._connection_name}]`
                """
            else:
                cfg = ""
        else:
            name = ""
            cfg = ""
        md = f"""
        ---
        **st.connection {name}built from `{module_name}.{class_name}`**
        {cfg}
        - Learn more using `st.help()`
        ---
        """
        return md
