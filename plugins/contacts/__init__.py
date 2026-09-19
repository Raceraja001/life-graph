"""Contacts connector: Google Contacts over read-only OAuth, or a vCard export.

Two sources behind one connector, chosen by the account's auth method:

- ``oauth`` — the Google People API with ``contacts.readonly`` and
  ``contacts.other.readonly``: saved contacts plus "Other contacts" (addresses
  Google keeps from mail), incremental via sync tokens.
- ``file`` — a ``.vcf`` export imported from Settings. Each import replaces the
  account's contacts; the file itself is not kept.

Which contact fields a cloud audience may see is the account's
``cloud_fields`` setting (``connectors/exposure.py``). Read-only by
construction: nothing here issues a write request.
"""

from plugins.contacts.connector import ContactsConnector

CONNECTOR = ContactsConnector()
