"""Email connector: IMAP with an app password, or Gmail over read-only OAuth.

- ``app_password`` — any IMAP server (Gmail: imap.gmail.com). Folders are
  opened with EXAMINE and bodies fetched with BODY.PEEK, through a client that
  refuses every mailbox-changing command.
- ``oauth`` — the Gmail API with ``gmail.readonly`` (IMAP over OAuth would need
  Google's full-mail scope, which would throw away the read-only guarantee).

Indexes INBOX and Sent (sender, subject, date, thread) and hands the newest
bodies to the core's local summariser. Bodies are never stored.
"""

from plugins.mail.connector import EmailConnector

CONNECTOR = EmailConnector()
