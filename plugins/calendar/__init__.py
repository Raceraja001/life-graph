"""Calendar connector: an ICS feed link, or Google Calendar over read-only OAuth.

Two sources behind one connector, chosen by the account's auth method:

- ``none`` — a calendar feed URL (Google's "Secret address in iCal format",
  Outlook, iCloud, Zoho …). The URL is the credential, so it is stored as the
  account secret. Each sync downloads the feed (conditional GET) and the
  runtime treats the result as the complete set for the window.
- ``oauth`` — the Google Calendar API with ``calendar.readonly``, incremental
  via ``syncToken``.

Read-only by construction: nothing here issues a write request.
"""

from plugins.calendar.connector import CalendarConnector

CONNECTOR = CalendarConnector()
