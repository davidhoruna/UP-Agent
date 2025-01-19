import datetime
import os.path
import logging
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/calendar"]

class CalendarManager:
    def __init__(self):
        self.creds = None
        self.service = None
    
    def authenticate(self) -> bool:
        try:
            if os.path.exists("token.json"):
                self.creds = Credentials.from_authorized_user_file("token.json", SCOPES)
            
            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    self.creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        "credentials.json", SCOPES
                    )
                    self.creds = flow.run_local_server(port=0)
                
                with open("token.json", "w") as token:
                    token.write(self.creds.to_json())
            
            self.service = build("calendar", "v3", credentials=self.creds)
            return True
            
        except Exception as e:
            logging.error(f"Authentication error: {e}")
            return False

    def add_event(self, title: str, description: str, start_time: datetime.datetime, 
                 duration_hours: int = 2) -> tuple[bool, str]:
        """Add an event to Google Calendar.
        
        Args:
            title: Event title
            description: Event description
            start_time: Event start time as datetime object
            duration_hours: Event duration in hours
            
        Returns:
            Tuple of (success: bool, result: str)
        """
        if not self.creds:
            if not self.authenticate():
                return False, "Authentication failed"

        try:
            end_time = start_time + datetime.timedelta(hours=duration_hours)
            
            event = {
                'summary': title,
                'description': description,
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': 'America/Lima',
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': 'America/Lima',
                },
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 24 * 60},
                        {'method': 'popup', 'minutes': 60},
                    ],
                },
            }

            event = self.service.events().insert(calendarId='primary', body=event).execute()
            return True, f"Event created: {event.get('htmlLink')}"

        except HttpError as e:
            error_message = f"Calendar API error: {str(e)}"
            logging.error(error_message)
            return False, error_message
        except Exception as e:
            error_message = f"Unexpected error: {str(e)}"
            logging.error(error_message)
            return False, error_message

    def get_events(self, start_date: datetime.datetime, 
                  max_results: int = 10) -> tuple[bool, list]:
        """Get upcoming events from calendar.
        
        Args:
            start_date: Start date to look for events
            max_results: Maximum number of events to return
            
        Returns:
            Tuple of (success: bool, events: list)
        """
        if not self.creds:
            if not self.authenticate():
                return False, []

        try:
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=start_date.isoformat() + 'Z',
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            return True, events_result.get('items', [])

        except Exception as e:
            logging.error(f"Error getting events: {e}")
            return False, []
