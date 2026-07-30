from google.oauth2 import service_account
from googleapiclient.discovery import build
from config.settings import Config

def get_calendar_service():
    SCOPES = ['https://www.googleapis.com/auth/calendar']
    creds_info = Config.get_google_creds_info()

    if creds_info:
        creds = service_account.Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    else:
        creds = service_account.Credentials.from_service_account_file('credentials.json', scopes=SCOPES)

    return build('calendar', 'v3', credentials=creds)

# Instance service yang siap dipakai
calendar_service = get_calendar_service()