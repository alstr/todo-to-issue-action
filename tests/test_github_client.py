import io
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace

from GitHubClient import GitHubClient


class CloseIssueAmbiguousMatchTest(unittest.TestCase):
    """Regression tests for GitHubClient.close_issue's ambiguous-match path.

    When a removed TODO matches more than one existing open issue (same title),
    close_issue deliberately skips closure and prints each candidate so the run
    log shows why. The existing issues come from the GitHub REST API
    (GitHubClient._get_existing_issues), whose issue objects expose ``html_url``
    (``web_url`` is a GitLab-only field). Printing the GitLab field crashed the
    whole TODOs workflow with ``KeyError: 'web_url'``.
    """

    @staticmethod
    def _client_with_issues(existing_issues):
        # Bypass __init__ (it performs network calls in _get_existing_issues /
        # _get_milestones); close_issue only needs existing_issues and the
        # class-level max_issue_title_length.
        client = GitHubClient.__new__(GitHubClient)
        client.existing_issues = existing_issues
        return client

    def test_ambiguous_match_does_not_crash_and_skips_closure(self):
        title = 'Remove auth-proxy when Cilium supports native forward auth'
        # Two open issues share the title and carry only the GitHub field
        # (html_url) — no web_url key, so the pre-fix code raised KeyError.
        existing_issues = [
            {'title': title, 'number': 11,
             'html_url': 'https://github.com/o/r/issues/11'},
            {'title': title, 'number': 22,
             'html_url': 'https://github.com/o/r/issues/22'},
        ]
        client = self._client_with_issues(existing_issues)
        removed_todo = SimpleNamespace(issue_number=None, title=title)

        output = io.StringIO()
        with redirect_stdout(output):
            result = client.close_issue(removed_todo)

        # Ambiguous match must skip closure (no issue closed -> None) ...
        self.assertIsNone(result)
        log = output.getvalue()
        # ... and the diagnostic must list each ambiguous candidate by its URL.
        self.assertIn('ambiguous match', log)
        self.assertIn('https://github.com/o/r/issues/11', log)
        self.assertIn('https://github.com/o/r/issues/22', log)


if __name__ == '__main__':
    unittest.main()
