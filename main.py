# -*- coding: utf-8 -*-
"""Convert IDE TODOs to GitHub issues."""

import os
import requests
import re
import json
from time import sleep


base_url = 'https://api.github.com/repos/'


def main():
    repo = os.getenv('INPUT_REPO')
    before = os.getenv('INPUT_BEFORE')
    sha = os.getenv('INPUT_SHA')
    label = os.getenv('INPUT_LABEL')
    params = {
        'access_token': os.getenv('INPUT_TOKEN')
    }

    # Let's compare the last two pushed commits.
    diff_url = f'{base_url}{repo}/compare/{before}...{sha}'
    diff_headers = {
        'Accept': 'application/vnd.github.v3.diff'
    }

    diff_request = requests.get(url=diff_url, headers=diff_headers, params=params)
    if diff_request.status_code == 200:
        diff = diff_request.text

        # Check for additions in the diff.
        addition_pattern = re.compile(r'(?<=^\+).*', re.MULTILINE)
        additions = addition_pattern.findall(diff)
        new_issues = []

        # Filter the additions down to newly added TODOs.
        for addition in additions:
            todo_pattern = re.compile(r'(?<=' + label + r'\s).*')
            todos = todo_pattern.search(addition)
            if todos:
                new_issues.append(todos.group(0))

        # Create new issues for any newly added TODOs.
        issues_url = f'{base_url}{repo}/issues'
        issue_headers = {
            'Content-Type': 'application/json',
        }
        for issue in new_issues:
            title = issue
            # Truncate the title if it's longer than 50 chars.
            if len(title) > 50:
                title = issue[:50] + '...'
            new_issue_body = {'title': title, 'body': issue, 'labels': ['todo']}
            requests.post(url=issues_url, headers=issue_headers, params=params, data=json.dumps(new_issue_body))
            # Don't add too many issues too quickly.
            sleep(1)

        # Check for deletions in the diff.
        deletion_pattern = re.compile(r'(?<=^-).*', re.MULTILINE)
        deletions = deletion_pattern.findall(diff)
        closed_issues = []

        # Filter the deletions down to removed TODOs.
        for deletion in deletions:
            todo_pattern = re.compile(r'(?<=' + label + r'\s).*')
            todos = todo_pattern.search(deletion)
            if todos:
                closed_issues.append(todos.group(0))

        if len(closed_issues) > 0:
            # Get the list of current issues.
            list_issues_request = requests.get(issues_url, headers=issue_headers, params=params)
            if list_issues_request.status_code == 200:
                current_issues = list_issues_request.json()
                for closed_issue in closed_issues:
                    title = closed_issue
                    if len(title) > 50:
                        title = closed_issue[:50] + '...'

                    # Compare the title of each closed issue with each issue in the issues list.
                    for current_issue in current_issues:
                        if current_issue['title'] == title:
                            # The titles match, so we will try and close the issue.
                            issue_number = current_issue['number']

                            update_issue_url = f'{base_url}{repo}/issues/{issue_number}'
                            body = {'state': 'closed'}
                            requests.patch(update_issue_url, headers=issue_headers, params=params,
                                           data=json.dumps(body))
                            # Don't update too many issues too quickly.
                            sleep(1)


if __name__ == "__main__":
    main()
