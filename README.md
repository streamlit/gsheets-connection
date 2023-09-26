# Streamlit GSheetsConnection

Connect to public or private Google Sheets from your Streamlit app. Powered by `st.experimental_connection()` and [gspread](https://github.com/burnash/gspread).

GSheets Connection works in two modes:

- in Read Only mode, using publicly shared Spreadsheet URLs (Read Only mode)
- CRUD operations support mode, with Authentication using Service Account. In order to use Service Account mode you need to enable Google Drive and Google Sheets API in [Google Developers Console](https://console.developers.google.com/).
  Follow **Initial setup for CRUD mode** section in order to authenticate your Streamlit app first.

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://st-gsheets.streamlit.app/)

## Install

```sh
pip install st-gsheets-connection
```

## Minimal example: publicly shared spreadsheet (read-only)

```python
# example/st_app.py

import streamlit as st
from streamlit_gsheets import GSheetsConnection

url = "https://docs.google.com/spreadsheets/d/1JDy9md2VZPz4JbYtRPJLs81_3jUK47nx6GYQjgU8qNY/edit?usp=sharing"

conn = st.experimental_connection("gsheets", type=GSheetsConnection)

data = conn.read(spreadsheet=url, usecols=[0, 1])
st.dataframe(data)
```

## Service account / CRUD example

### Initial setup for private spreadsheet and/or CRUD mode

1. Setup `.streamlit/secrets.toml` inside your Streamlit app root directory,
   check out [Secret management documentation](https://docs.streamlit.io/streamlit-community-cloud/get-started/deploy-an-app/connect-to-data-sources/secrets-management) for references.
2. [Enable API Access for a Project](https://docs.gspread.org/en/v5.7.1/oauth2.html#enable-api-access-for-a-project)
   - Head to [Google Developers Console](https://console.developers.google.com/) and create a new project (or select the one you already have).
   - In the box labeled “Search for APIs and Services”, search for “Google Drive API” and enable it.
   - In the box labeled “Search for APIs and Services”, search for “Google Sheets API” and enable it.
3. [Using Service Account](https://docs.gspread.org/en/v5.7.1/oauth2.html#for-bots-using-service-account)
   - Enable API Access for a Project if you haven’t done it yet.
   - Go to “APIs & Services > Credentials” and choose “Create credentials > Service account key”.
   - Fill out the form
   - Click “Create” and “Done”.
   - Press “Manage service accounts” above Service Accounts.
   - Press on ⋮ near recently created service account and select “Manage keys” and then click on “ADD KEY > Create new key”.
   - Select JSON key type and press “Create”.

You will automatically download a JSON file with credentials. It may look like this:

```
{
    "type": "service_account",
    "project_id": "api-project-XXX",
    "private_key_id": "2cd … ba4",
    "private_key": "-----BEGIN PRIVATE KEY-----\nNrDyLw … jINQh/9\n-----END PRIVATE KEY-----\n",
    "client_email": "473000000000-yoursisdifferent@developer.gserviceaccount.com",
    "client_id": "473 … hd.apps.googleusercontent.com",
    ...
}
```

Remember the path to the downloaded credentials file. Also, in the next step you’ll need the value of client_email from this file.

- **:red[Very important!]** Go to your spreadsheet and share it with a client_email from the step above. Just like you do with any other Google account. If you don’t do this, you’ll get a `gspread.exceptions.SpreadsheetNotFound` exception when trying to access this spreadsheet from your application or a script.

4. Inside `streamlit/secrets.toml` place `service_account` configuration from downloaded JSON file, in the following format (where `gsheets` is your `st.connection` name):

```
# .streamlit/secrets.toml

[connections.gsheets]
spreadsheet = "<spreadsheet-name-or-url>"
worksheet = "<worksheet-gid-or-folder-id>"  # worksheet GID is used when using Public Spreadsheet URL, when usign service_account it will be picked as folder_id
type = ""  # leave empty when using Public Spreadsheet URL, when using service_account -> type = "service_account"
project_id = ""
private_key_id = ""
private_key = ""
client_email = ""
client_id = ""
auth_uri = ""
token_uri = ""
auth_provider_x509_cert_url = ""
client_x509_cert_url = ""
```

### Code

```python
# example/st_app_gsheets_using_service_account.py

import streamlit as st
from streamlit_gsheets import GSheetsConnection

st.title("Read Google Sheet as DataFrame")

conn = st.experimental_connection("gsheets", type=GSheetsConnection)
df = conn.read(worksheet="Example 1")

st.dataframe(df)
```

```toml
# .streamlit/secrets.toml

[connections.gsheets]
spreadsheet = "<spreadsheet-name-or-url>"
worksheet = "<worksheet-gid-or-folder-id>"  # worksheet GID is used when using Public Spreadsheet URL, when usign service_account it will be picked as folder_id
type = ""  # leave empty when using Public Spreadsheet URL, when using service_account -> type = "service_account"
project_id = ""
private_key_id = ""
private_key = ""
client_email = ""
client_id = ""
auth_uri = ""
token_uri = ""
auth_provider_x509_cert_url = ""
client_x509_cert_url = ""
```

```txt
# requirements.txt

streamlit==1.22
git+https://github.com/streamlit/gsheets-connection
pandasql  # this is for example/st_app.py only
```

## Full example

Check gsheets_connection/example directory for full example of the usage.

## Q&A

- > Does this work with a public spreadsheet without the authentication details? Or only a private spreadsheet?

  GSheets Connection works in two modes:

  - in Read Only mode, using publicly shared Spreadsheet URLs (Read Only mode)
  - CRUD operations support mode, with Authentication using Service Account. In order to use Service Account mode you need to enable Google Drive and Google Sheets API in [Google Developers Console](https://console.developers.google.com/).
    Follow **Initial setup for CRUD mode** section in order to authenticate your Streamlit app first.
