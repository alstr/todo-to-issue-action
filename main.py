# -*- coding: utf-8 -*-
"""Convert IDE TODOs to GitHub issues."""

import os
import requests
import re
import json
from time import sleep
from io import StringIO

base_url = 'https://api.github.com/repos/'


def main():
    repo = os.getenv('INPUT_REPO')
    before = os.getenv('INPUT_BEFORE')
    sha = os.getenv('INPUT_SHA')
    comment_marker = os.getenv('INPUT_COMMENT_MARKER')
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

        header_pattern = re.compile(r'(?<=diff\s--git\s).+')
        hunk_start_pattern = re.compile(r'((?<=^@@\s).+(?=\s@@))')
        line_num_pattern = re.compile(r'(?<=\+).+')
        addition_pattern = re.compile(r'(?<=^\+).*')
        deletion_pattern = re.compile(r'(?<=^-).*')
        todo_pattern = re.compile(r'(?<=' + label + r'\s).+')
        comment_pattern = re.compile(r'(?<=' + comment_marker + r'\s).+')

        new_issues = []
        closed_issues = []

        # Read the diff file one line at a time, checking for additions/deletions in each hunk.
        with StringIO(diff) as diff_file:
            curr_file = None
            recording = False
            line_counter = None

            for n, line in enumerate(diff_file):
                # First look for a diff header so we can determine the file the changes relate to.
                header_search = header_pattern.search(line)
                if header_search:
                    files = header_search.group(0).split(' ')
                    curr_file = files[1][2:]
                else:
                    # Look for hunks so we can get the line numbers for the changes.
                    hunk_search = hunk_start_pattern.search(line)
                    if hunk_search:
                        hunk = hunk_search.group(0)
                        line_nums = line_num_pattern.search(hunk).group(0).split(',')
                        hunk_start = int(line_nums[0])
                        line_counter = hunk_start
                    else:
                        # Look for additions and deletions (specifically TODOs) within each hunk.
                        addition_search = addition_pattern.search(line)
                        if addition_search:
                            addition = addition_search.group(0)
                            todo_search = todo_pattern.search(addition)
                            if todo_search:
                                # Start recording so we can capture multiline TODOs.
                                recording = True
                                todo = todo_search.group(0)
                                new_issue = {
                                    'labels': ['todo'],
                                    'todo': todo,
                                    'body': todo,
                                    'file': curr_file,
                                    'line_num': line_counter
                                }
                                new_issues.append(new_issue)
                            elif recording:
                                # If we are recording, check if the current line continues the last.
                                comment_search = comment_pattern.search(addition)
                                if comment_search:
                                    comment = comment_search.group(0).lstrip()
                                    last_issue = new_issues[len(new_issues) - 1]
                                    last_issue['body'] += '\n' + comment
                            line_counter += 1
                            continue
                        else:
                            deletion_search = deletion_pattern.search(line)
                            if deletion_search:
                                deletion = deletion_search.group(0)
                                todo_search = todo_pattern.search(deletion)
                                if todo_search:
                                    closed_issues.append(todo_search.group(0))
                            else:
                                line_counter += 1
                if recording:
                    recording = False

        # Create new issues for any newly added TODOs.
        issues_url = f'{base_url}{repo}/issues'
        issue_headers = {
            'Content-Type': 'application/json',
        }
        for issue in new_issues:
            title = issue['todo']
            # Truncate the title if it's longer than 50 chars.
            if len(title) > 50:
                title = title[:50] + '...'
            file = issue['file']
            line = issue['line_num']
            body = issue['body'] + '\n' + f'https://github.com/{repo}/blob/{sha}/{file}#L{line}'
            new_issue_body = {'title': title, 'body': body, 'labels': ['todo']}
            requests.post(url=issues_url, headers=issue_headers, params=params, data=json.dumps(new_issue_body))
            # Don't add too many issues too quickly.
            sleep(1)

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

                            issue_comment_url = f'{base_url}{repo}/issues/{issue_number}/comments'
                            body = {'body': f'Closed in {sha}'}
                            requests.post(issue_comment_url, headers=issue_headers, params=params,
                                          data=json.dumps(body))

                            # Don't update too many issues too quickly.
                            sleep(1)


if __name__ == "__main__":
    main()
