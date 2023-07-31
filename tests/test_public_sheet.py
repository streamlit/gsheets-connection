from unittest.mock import mock_open, patch

import pandas as pd
import pytest
import streamlit as st
from pandas.testing import assert_frame_equal

from streamlit_gsheets import GSheetsConnection


@pytest.fixture
def expected_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": ["1/1/1975", "2/1/1975", "3/1/1975", "4/1/1975", "5/1/1975"],
            "births": [265775, 241045, 268849, 247455, 254545],
        }
    )


def test_read_public_sheet(expected_df: pd.DataFrame):
    url = "https://docs.google.com/spreadsheets/d/1JDy9md2VZPz4JbYtRPJLs81_3jUK47nx6GYQjgU8qNY/edit"

    conn = st.experimental_connection("connection_name", type=GSheetsConnection)

    df = conn.read(spreadsheet=url, usecols=[0, 1])

    assert_frame_equal(df.head(), expected_df)


def test_query_public_sheet():
    url = "https://docs.google.com/spreadsheets/d/1JDy9md2VZPz4JbYtRPJLs81_3jUK47nx6GYQjgU8qNY/edit"

    conn = st.experimental_connection("connection_name", type=GSheetsConnection)

    df = conn.query("select date from my_table where births = 265775", spreadsheet=url)

    assert len(df) == 1
    assert df["date"].values[0] == "1/1/1975"


def test_query_worksheet_public_sheet():
    url = "https://docs.google.com/spreadsheets/d/1JDy9md2VZPz4JbYtRPJLs81_3jUK47nx6GYQjgU8qNY/edit"
    worksheet = (
        1585633377  # Example 2, note that this is the gid, not the worksheet name
    )

    conn = st.experimental_connection("connection_name", type=GSheetsConnection)

    df = conn.query(
        "select date from my_table where births = 1000000",
        spreadsheet=url,
        worksheet=worksheet,
    )

    assert len(df) == 1
    assert df["date"].values[0] == "1/1/1975"


secrets_contents = """
[connections.test_connection_name]
spreadsheet = "https://docs.google.com/spreadsheets/d/1JDy9md2VZPz4JbYtRPJLs81_3jUK47nx6GYQjgU8qNY/edit"
"""


@patch("builtins.open", mock_open(read_data=secrets_contents))
def test_secrets_contents(expected_df):
    conn = st.experimental_connection("test_connection_name", type=GSheetsConnection)

    df = conn.read()

    assert_frame_equal(df.head(), expected_df)


def test_no_secrets_contents():
    conn = st.experimental_connection("other_connection_name", type=GSheetsConnection)

    with pytest.raises(ValueError):
        conn.read()
