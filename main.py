# -*- coding: utf-8 -*-
"""Convert IDE TODOs to GitHub issues."""

import os
import re
from time import sleep
from io import StringIO
import itertools
import operator
from collections import defaultdict
import sys

from Client import Client
from GitHubClient import GitHubClient
from LineStatus import LineStatus
from LocalClient import LocalClient
from TodoParser import TodoParser

def process_diff(diff, client=Client(), insert_issue_urls=False, parser=TodoParser(), output=sys.stdout):
    # Parse the diff for TODOs and create an Issue object for each.
    raw_issues = parser.parse(diff)
    # This is a simple, non-perfect check to filter out any TODOs that have just been moved.
    # It looks for items that appear in the diff as both an addition and deletion.
    # It is based on the assumption that TODOs will not have identical titles in identical files.
    # That is about as good as we can do for TODOs without issue URLs.
    issues_to_process = []
    for values, similar_issues_iter in itertools.groupby(raw_issues, key=operator.attrgetter('title', 'file_name',
                                                                                        'markdown_language')):
        similar_issues = list(similar_issues_iter)
        if (len(similar_issues) == 2 and all(issue.issue_url is None for issue in similar_issues)
                and ((similar_issues[0].status == LineStatus.ADDED
                        and similar_issues[1].status == LineStatus.DELETED)
                    or (similar_issues[1].status == LineStatus.ADDED
                        and similar_issues[0].status == LineStatus.DELETED))):
            print(f'Issue "{values[0]}" appears as both addition and deletion. '
                    f'Assuming this issue has been moved so skipping.', file=output)
            continue
        issues_to_process.extend(similar_issues)

    # If a TODO with an issue URL is updated, it may appear as both an addition and a deletion.
    # We need to ignore the deletion so it doesn't update then immediately close the issue.
    # First store TODOs based on their status.
    todos_status = defaultdict(lambda: {'added': False, 'deleted': False})

    # Populate the status dictionary based on the issue URL.
    for raw_issue in issues_to_process:
        if raw_issue.issue_url:  # Ensuring we're dealing with TODOs that have an issue URL.
            if raw_issue.status == LineStatus.ADDED:
                todos_status[raw_issue.issue_url]['added'] = True
            elif raw_issue.status == LineStatus.DELETED:
                todos_status[raw_issue.issue_url]['deleted'] = True

    # Determine which issues are both added and deleted.
    update_and_close_issues = set()

    for _issue_url, _status in todos_status.items():
        if _status['added'] and _status['deleted']:
            update_and_close_issues.add(_issue_url)

    # Remove issues from issues_to_process if they are both to be updated and closed (i.e., ignore deletions).
    issues_to_process = [issue for issue in issues_to_process if
                            not (issue.issue_url in update_and_close_issues and issue.status == LineStatus.DELETED)]

    # Cycle through the Issue objects and create or close a corresponding GitHub issue for each.
    for j, raw_issue in enumerate(sorted(reversed(sorted(issues_to_process, key = operator.attrgetter('start_line'))), key = operator.attrgetter('file_name'))):
        print(f"Processing issue {j + 1} of {len(issues_to_process)}: '{raw_issue.title}' @ {raw_issue.file_name}:{raw_issue.start_line}", file=output)
        if raw_issue.status == LineStatus.ADDED:
            status_code, new_issue_number = client.create_issue(raw_issue)
            if status_code == 201:
                print(f'Issue created: #{new_issue_number} @ {client.get_issue_url(new_issue_number)}', file=output)
                # Don't insert URLs for comments. Comments do not get updated.
                if insert_issue_urls and not (raw_issue.ref and raw_issue.ref.startswith('#')):
                    line_number = raw_issue.start_line - 1
                    with open(raw_issue.file_name, 'r') as issue_file:
                        file_lines = issue_file.readlines()
                    if line_number < len(file_lines):
                        # Duplicate the line to retain the comment syntax.
                        old_line = file_lines[line_number]
                        remove = fr'(?i:{raw_issue.identifier}).*{raw_issue.title}'
                        insert = f'Issue URL: {client.get_issue_url(new_issue_number)}'
                        new_line = re.sub(remove, insert, old_line)
                        # make sure the above operation worked as intended
                        if new_line != old_line:
                            # Check if the URL line already exists, if so abort.
                            if line_number == len(file_lines) - 1 or file_lines[line_number + 1] != new_line:
                                file_lines.insert(line_number + 1, new_line)
                                with open(raw_issue.file_name, 'w') as issue_file:
                                    issue_file.writelines(file_lines)
                                print('Issue URL successfully inserted', file=output)
                        else:
                            print('ERROR: Issue URL was NOT successfully inserted', file=output)
            elif status_code == 200:
                print(f'Issue updated: #{new_issue_number} @ {client.get_issue_url(new_issue_number)}', file=output)
            else:
                print('Issue could not be created', file=output)
        elif raw_issue.status == LineStatus.DELETED and os.getenv('INPUT_CLOSE_ISSUES', 'true') == 'true':
            if raw_issue.ref and raw_issue.ref.startswith('#'):
                print('Issue looks like a comment, will not attempt to close.', file=output)
                continue
            status_code = client.close_issue(raw_issue)
            if status_code in [200, 201]:
                print('Issue closed', file=output)
            else:
                print('Issue could not be closed', file=output)
        # Stagger the requests to be on the safe side.
        sleep(1)

if __name__ == "__main__":
    client: Client | None = None
    # Try to create a basic client for communicating with the remote version control server, automatically initialised with environment variables.
    try:
        # try to build a GitHub client
        client = GitHubClient()
    except EnvironmentError:
        # don't immediately give up
        pass
    # if needed, fall back to using a local client for testing
    client = client or LocalClient()

    # Get the diff from the last pushed commit.
    last_diff = client.get_last_diff()

    # process the diff
    if last_diff:
        # Check to see if we should insert the issue URL back into the linked TODO.
        insert_issue_urls = os.getenv('INPUT_INSERT_ISSUE_URLS', 'false') == 'true'

        process_diff(StringIO(last_diff), client, insert_issue_urls)
