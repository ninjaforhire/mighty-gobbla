import os.path
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# The ID and range of a sample spreadsheet.
SPREADSHEET_ID = '1nikwHHkeeaikq_CdIrRZKYqBfj4cW_mgitO_9WUlGXM'

class GSheetsClient:
    def __init__(self, credentials_path='credentials.json', token_path='token.json'):
        self.creds = None
        if os.path.exists(token_path):
            self.creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        # If there are no (valid) credentials available, let the user log in.
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    credentials_path, SCOPES)
                self.creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(token_path, 'w') as token:
                token.write(self.creds.to_json())

        self.service = build('sheets', 'v4', credentials=self.creds)

    def get_sheet_data(self, sheet_range='Sheet1!A:C'):
        """Gets data from the sheet."""
        try:
            sheet = self.service.spreadsheets()
            result = sheet.values().get(spreadsheetId=SPREADSHEET_ID,
                                        range=sheet_range).execute()
            return result.get('values', [])
        except HttpError as err:
            print(err)
            return []

    def append_rows(self, values, sheet_range='Sheet1!A:C'):
        """Appends rows to the sheet."""
        try:
            body = {
                'values': values
            }
            result = self.service.spreadsheets().values().append(
                spreadsheetId=SPREADSHEET_ID, range=sheet_range,
                valueInputOption='USER_ENTERED', body=body).execute()
            return result
        except HttpError as err:
            print(err)
            return None

    def clear_sheet(self, sheet_range='Sheet1!A:Z'):
        """Clears the sheet content."""
        try:
            result = self.service.spreadsheets().values().clear(
                spreadsheetId=SPREADSHEET_ID, range=sheet_range).execute()
            return result
        except HttpError as err:
            print(err)
            return None

    def update_rows(self, values, sheet_range='Sheet1!A:C'):
        """Updates rows in the sheet."""
        try:
            body = {
                'values': values
            }
            result = self.service.spreadsheets().values().update(
                spreadsheetId=SPREADSHEET_ID, range=sheet_range,
                valueInputOption='USER_ENTERED', body=body).execute()
            return result
        except HttpError as err:
            print(err)
            return None

if __name__ == '__main__':
    # Test connection
    client = GSheetsClient()
    data = client.get_sheet_data()
    print(f"Read {len(data)} rows from sheet.")
