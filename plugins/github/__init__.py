"""GitHub connector: what is waiting on the user in code.

Pull requests where their review is requested, their own open pull requests
(CI, review decision, mergeable) and issues assigned to them, from one GraphQL
query every 15 minutes (docs/specs/connector-github.md).

Credential: a read-only fine-grained personal access token (auth ``token``),
one account per GitHub identity or organisation. A classic token that can
write is refused. Titles and status only: no code, diffs, descriptions or
comments are ever fetched.
"""

from plugins.github.connector import GitHubConnector

CONNECTOR = GitHubConnector()
