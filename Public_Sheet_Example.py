import streamlit as st

st.subheader("📗 Google Sheets st.connection using Public URLs")

url = "https://docs.google.com/spreadsheets/d/1JDy9md2VZPz4JbYtRPJLs81_3jUK47nx6GYQjgU8qNY/edit?usp=sharing"

st.write("#### 1. Read public Google Worksheet as Pandas")

with st.echo():
    import streamlit as st

    from streamlit_gsheets import GSheetsConnection

    conn = st.connection("gsheets", type=GSheetsConnection)

    df = conn.read(spreadsheet=url, usecols=[0, 1])
    st.dataframe(df)
