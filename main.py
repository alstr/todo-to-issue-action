# -*- coding: utf-8 -*-
"""Convert IDE TODOs to GitHub issues."""

import os
import requests
import re
import json
from time import sleep
from io import StringIO
from ruamel.yaml import YAML
import hashlib

base_url = 'https://api.github.com/repos/'


def main():
    repo = os.getenv('INPUT_REPO')
    before = os.getenv('INPUT_BEFORE')
    sha = os.getenv('INPUT_SHA')
    comment_marker = os.getenv('INPUT_COMMENT_MARKER')
    label = os.getenv('INPUT_LABEL')
    token = os.getenv('INPUT_TOKEN')
    close_issues = os.getenv('INPUT_CLOSE_ISSUES') == 'true'
    auto_p = os.getenv('INPUT_AUTO_P') == 'true'
    line_break = '\n\n' if auto_p else '\n'

    # Load a file so we can see what language each file is written in and apply highlighting later.
    languages_url = 'https://raw.githubusercontent.com/github/linguist/master/lib/linguist/languages.yml'
    languages_request = requests.get(url=languages_url)
    languages_dict = None
    if languages_request.status_code == 200:
        languages_data = languages_request.text
        yaml = YAML(typ='safe')
        languages_dict = yaml.load(languages_data)

    # Get the current issues so we can check we're not duplicating any, and so we can close any that have been removed.
    def get_current_issues(page=1):
        params = {
            'per_page': 100,
            'page': page,
            'state': 'open',
            'labels': 'todo'
        }
        list_issues_request = requests.get(issues_url, headers=issue_headers, params=params)
        if list_issues_request.status_code == 200:
            current_issues.extend(list_issues_request.json())
            links = list_issues_request.links
            if 'next' in links:
                get_current_issues(page + 1)

    issues_url = f'{base_url}{repo}/issues'
    issue_headers = {
        'Content-Type': 'application/json',
        'Authorization': f'token {token}'
    }
    current_issues = []
    get_current_issues()

    # Start to compare the latest and previous commit, to find any added or removed TODOs.
    diff_url = f'{base_url}{repo}/compare/{before}...{sha}'
    diff_headers = {
        'Accept': 'application/vnd.github.v3.diff',
        'Authorization': f'token {token}'
    }
    diff_request = requests.get(url=diff_url, headers=diff_headers)
    if diff_request.status_code == 200:
        diff = diff_request.text

        header_pattern = re.compile(r'(?<=diff\s--git\s).+')
        hunk_start_pattern = re.compile(r'((?<=^@@\s).+(?=\s@@))')
        line_num_pattern = re.compile(r'(?<=\+).+')
        addition_pattern = re.compile(r'(?<=^\+).*')
        deletion_pattern = re.compile(r'(?<=^-).*')
        todo_pattern = re.compile(r'(?<=' + label + r'[(\s:]).+')
        identifier_pattern = re.compile(r'.+(?=\))')
        title_pattern = re.compile(r'(?<=\)[\s:]).+')
        comment_pattern = re.compile(r'(?<=' + comment_marker + r'\s).+')
        labels_pattern = re.compile(r'(?<=labels:).+')
        assignees_pattern = re.compile(r'(?<=assignees:).+')
        milestone_pattern = re.compile(r'(?<=milestone:).+')

        new_issues = []
        closed_issues = []
        lines = []
        curr_issue = None

        # Read the diff file one line at a time, checking for additions/deletions in each hunk.
        with StringIO(diff) as diff_file:
            curr_file = None
            previous_line_was_todo = False
            line_counter = None

            # Used to check if the line passed in is a continuation of the previous line, returning True/False.
            # If True, the current issue is updated with the extra details from this line.
            def process_line(next_line):
                if previous_line_was_todo:
                    if next_line.strip() == comment_marker:
                        curr_issue['body'] += line_break
                        return True
                    comment_search = comment_pattern.search(next_line)
                    if comment_search:
                        comment = comment_search.group(0).lstrip()
                        labels_search = labels_pattern.search(comment, re.IGNORECASE)
                        if labels_search:
                            labels = labels_search.group(0).lstrip().replace(', ', ',')
                            labels = list(filter(None, labels.split(',')))
                            curr_issue['labels'].extend(labels)
                        else:
                            assignees_search = assignees_pattern.search(comment, re.IGNORECASE)
                            if assignees_search:
                                assignees = assignees_search.group(0).lstrip().replace(', ', ',')
                                assignees = list(filter(None, assignees.split(',')))
                                curr_issue['assignees'] = assignees
                            else:
                                milestone_search = milestone_pattern.search(comment, re.IGNORECASE)
                                if milestone_search:
                                    milestone = milestone_search.group(0).strip()
                                    if milestone.isdigit():
                                        curr_issue['milestone'] = int(milestone)
                                else:
                                    curr_issue['body'] += line_break + comment
                        return True
                return False

            for n, line in enumerate(diff_file):
                # First look for a diff header so we can determine the file the changes relate to.
                encoded_line = line.encode('utf-8')
                cleaned_line = encoded_line.rstrip(b'\r\n').decode('utf-8')

                header_search = header_pattern.search(cleaned_line)
                if header_search:
                    files = header_search.group(0).split(' ')
                    curr_file = files[1][2:]
                    line_counter = None
                else:
                    # Look for hunks so we can get the line numbers for the changes.
                    hunk_search = hunk_start_pattern.search(cleaned_line)
                    if hunk_search:
                        if curr_issue:
                            curr_issue['hunk'] = lines
                            new_issues.append(curr_issue)
                            curr_issue = None

                        lines = []
                        hunk = hunk_search.group(0)
                        line_nums = line_num_pattern.search(hunk).group(0).split(',')
                        hunk_start = int(line_nums[0])
                        line_counter = hunk_start
                    else:
                        # Look for additions and deletions (specifically TODOs) within each hunk.
                        addition_search = addition_pattern.search(cleaned_line)
                        if addition_search:
                            lines.append(cleaned_line[1:])
                            addition = addition_search.group(0)
                            todo_search = todo_pattern.search(addition, re.IGNORECASE)
                            if todo_search:
                                # A new item was found. Start recording so we can capture multiline TODOs.
                                previous_line_was_todo = True
                                todo = todo_search.group(0).lstrip()
                                identifier_search = identifier_pattern.search(todo)
                                title_search = title_pattern.search(todo)
                                if identifier_search and title_search:
                                    todo = f'[{identifier_search.group(0)}] {title_search.group(0).lstrip()}'
                                elif identifier_search:
                                    todo = identifier_search.group(0)  # Shouldn't really arise.
                                elif title_search:
                                    todo = title_search.group(0)  # Shouldn't really arise.

                                if curr_issue:
                                    curr_issue['hunk'] = lines
                                    new_issues.append(curr_issue)

                                curr_issue = {
                                    'labels': ['todo'],
                                    'todo': todo,
                                    'body': todo,
                                    'file': curr_file,
                                    'line_num': line_counter
                                }
                                line_counter += 1
                                continue
                            else:
                                # This line isn't a new item. Let's check if it continues from the previous line.
                                line_processed = process_line(addition)
                                if line_processed:
                                    line_counter += 1
                                    continue
                            if line_counter is not None:
                                line_counter += 1
                        else:
                            deletion_search = deletion_pattern.search(cleaned_line)
                            if deletion_search:
                                deletion = deletion_search.group(0)
                                todo_search = todo_pattern.search(deletion, re.IGNORECASE)
                                if todo_search:
                                    closed_issues.append(todo_search.group(0).lstrip())
                            else:
                                lines.append(cleaned_line[1:])
                                # Let's check if this line continues from a previous deletion.
                                line_processed = process_line(cleaned_line)
                                if line_processed:
                                    line_counter += 1
                                    continue
                                if line_counter is not None:
                                    line_counter += 1
                if previous_line_was_todo:
                    previous_line_was_todo = False

            if curr_issue:
                curr_issue['hunk'] = lines
                new_issues.append(curr_issue)

        # Create new issues for any newly added TODOs.
        print('Start creating issues')
        for i, issue in enumerate(new_issues):
            title = issue['todo']
            # Truncate the title if it's longer than 80 chars.
            if len(title) > 80:
                title = title[:80] + '...'
            file = issue['file']
            line = issue['line_num']
            body = issue['body'] + '\n\n' + f'https://github.com/{repo}/blob/{sha}/{file}#L{line}'
            if 'hunk' in issue:
                hunk = issue['hunk']
                hunk.pop(0)

                file_name, extension = os.path.splitext(os.path.basename(file))
                markdown_language = None
                if languages_dict:
                    for language in languages_dict:
                        if ('extensions' in languages_dict[language]
                                and extension in languages_dict[language]['extensions']):
                            markdown_language = languages_dict[language]['ace_mode']
                if markdown_language:
                    body += '\n\n' + '```' + markdown_language + '\n' + '\n'.join(hunk) + '\n' + '```'
                else:
                    body += '\n\n' + '```' + '\n'.join(hunk) + '\n' + '```'

            # Check if the current issue already exists - if so, skip it.
            issue_id = hashlib.sha1(body.encode('utf-8')).hexdigest()
            body += '\n\n' + issue_id
            for current_issue in current_issues:
                if issue_id in current_issue['body']:
                    print(f'Skipping issue {i + 1} of {len(new_issues)} (already exists)')
                    break
            else:
                new_issue_body = {'title': title, 'body': body, 'labels': issue['labels']}

                # We need to check if any assignees/milestone specified exist, otherwise issue creation will fail.
                if 'assignees' in issue:
                    valid_assignees = []
                    for assignee in issue['assignees']:
                        assignee_url = f'{base_url}{repo}/assignees/{assignee}'
                        assignee_request = requests.get(url=assignee_url, headers=issue_headers)
                        if assignee_request.status_code == 204:
                            valid_assignees.append(assignee)
                        else:
                            print('Assignee doesn\'t exist! Dropping this assignee!')
                    new_issue_body['assignees'] = valid_assignees

                if 'milestone' in issue:
                    milestone_number = issue['milestone']
                    milestone_url = f'{base_url}{repo}/milestones/{milestone_number}'
                    milestone_request = requests.get(url=milestone_url, headers=issue_headers)
                    if milestone_request.status_code == 200:
                        new_issue_body['milestone'] = issue['milestone']
                    else:
                        print('Milestone doesn\'t exist! Dropping this parameter!')

                new_issue_request = requests.post(url=issues_url, headers=issue_headers,
                                                  data=json.dumps(new_issue_body))
                print(f'Creating issue {i + 1} of {len(new_issues)}')
                if new_issue_request.status_code == 201:
                    print('Issue created')
                else:
                    print('Issue could not be created')
                # Don't add too many issues too quickly.
                sleep(1)
        print('Creating issues complete')

        # Close issues for removed TODOs if this is enabled.
        if close_issues:
            print('Start closing issues')
            for i, closed_issue in enumerate(closed_issues):
                title = closed_issue
                matched = 0
                issue_number = None
                # Compare the title of each closed issue with each issue in the issues list.
                for current_issue in current_issues:
                    if current_issue['body'].startswith(title):
                        matched += 1
                        # If there are multiple issues with similar titles, don't try and close any.
                        if matched > 1:
                            print(f'Skipping issue {i + 1} of {len(closed_issues)} (multiple matches)')
                            break
                        issue_number = current_issue['number']
                else:
                    if issue_number is None:
                        continue
                    # The titles match, so we will try and close the issue.
                    update_issue_url = f'{base_url}{repo}/issues/{issue_number}'
                    body = {'state': 'closed'}
                    requests.patch(update_issue_url, headers=issue_headers, data=json.dumps(body))

                    issue_comment_url = f'{base_url}{repo}/issues/{issue_number}/comments'
                    body = {'body': f'Closed in {sha}'}
                    update_issue_request = requests.post(issue_comment_url, headers=issue_headers,
                                                         data=json.dumps(body))
                    print(f'Closing issue {i + 1} of {len(closed_issues)}')
                    if update_issue_request.status_code == 201:
                        print('Issue closed')
                    else:
                        print('Issue could not be closed')
                    # Don't update too many issues too quickly.
                    sleep(1)
            print('Closing issues complete')


if __name__ == "__main__":
    main()
