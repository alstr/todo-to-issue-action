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
from enum import Enum
import itertools
import operator


class LineStatus(Enum):
    """Represents the status of a line in a diff file."""
    ADDED = 0
    DELETED = 1
    UNCHANGED = 2


class Issue(object):
    """Basic Issue model for collecting the necessary info to send to GitHub."""

    def __init__(self, title, labels, assignees, milestone, user_projects, org_projects, body, hunk, file_name,
                 start_line, markdown_language, status):
        self.title = title
        self.labels = labels
        self.assignees = assignees
        self.milestone = milestone
        self.user_projects = user_projects
        self.org_projects = org_projects
        self.body = body
        self.hunk = hunk
        self.file_name = file_name
        self.start_line = start_line
        self.markdown_language = markdown_language
        self.status = status


class GitHubClient(object):
    """Basic client for getting the last diff and creating/closing issues."""
    existing_issues = []
    base_url = 'https://api.github.com/'
    repos_url = f'{base_url}repos/'

    def __init__(self):
        self.repo = os.getenv('INPUT_REPO')
        self.before = os.getenv('INPUT_BEFORE')
        self.sha = os.getenv('INPUT_SHA')
        self.commits = json.loads(os.getenv('INPUT_COMMITS'))
        self.diff_url = os.getenv('INPUT_DIFF_URL')
        self.token = os.getenv('INPUT_TOKEN')
        self.issues_url = f'{self.repos_url}{self.repo}/issues'
        self.issue_headers = {
            'Content-Type': 'application/json',
            'Authorization': f'token {self.token}'
        }
        auto_p = os.getenv('INPUT_AUTO_P', 'true') == 'true'
        self.line_break = '\n\n' if auto_p else '\n'
        # Retrieve the existing repo issues now so we can easily check them later.
        self._get_existing_issues()
        self.auto_assign = os.getenv('INPUT_AUTO_ASSIGN', 'false') == 'true'
        self.actor = os.getenv('INPUT_ACTOR')

    def get_timestamp(self, commit):
        return commit.get('timestamp')

    def get_last_diff(self):
        """Get the last diff."""
        if self.diff_url:
            # Diff url was directly passed in config, likely due to this being a PR
            diff_url = self.diff_url
        elif self.before != '0000000000000000000000000000000000000000':
            # There is a valid before SHA to compare with, or this is a release being created
            diff_url = f'{self.repos_url}{self.repo}/compare/{self.before}...{self.sha}'
        elif len(self.commits) == 1:
            # There is only one commit
            diff_url = f'{self.repos_url}{self.repo}/commits/{self.sha}'
        else: 
            # There are several commits: compare with the oldest one
            oldest = sorted(self.commits, key=self.get_timestamp)[0]['id']
            diff_url = f'{self.repos_url}{self.repo}/compare/{oldest}...{self.sha}'    
        
        diff_headers = {
            'Accept': 'application/vnd.github.v3.diff',
            'Authorization': f'token {self.token}'
        }
        diff_request = requests.get(url=diff_url, headers=diff_headers)
        if diff_request.status_code == 200:
            return diff_request.text
        raise Exception('Could not retrieve diff. Operation will abort.')

    def _get_existing_issues(self, page=1):
        """Populate the existing issues list."""
        params = {
            'per_page': 100,
            'page': page,
            'state': 'open',
            'labels': 'todo'
        }
        list_issues_request = requests.get(self.issues_url, headers=self.issue_headers, params=params)
        if list_issues_request.status_code == 200:
            self.existing_issues.extend(list_issues_request.json())
            links = list_issues_request.links
            if 'next' in links:
                self._get_existing_issues(page + 1)

    def create_issue(self, issue):
        """Create a dict containing the issue details and send it to GitHub."""
        title = issue.title
        if len(title) > 80:
            # Title is too long.
            title = title[:80] + '...'
        url_to_line = f'https://github.com/{self.repo}/blob/{self.sha}/{issue.file_name}#L{issue.start_line}'
        formatted_issue_body = self.line_break.join(issue.body)
        body = (formatted_issue_body + '\n\n'
                + url_to_line + '\n\n'
                + '```' + issue.markdown_language + '\n'
                + issue.hunk + '\n'
                + '```')

        # Check if the current issue already exists - if so, skip it.
        # The below is a simple and imperfect check.
        issue_id = hashlib.sha1(body.encode('utf-8')).hexdigest()
        body += '\n\n' + issue_id
        for existing_issue in self.existing_issues:
            if issue_id in existing_issue['body']:
                # The issue_id matching means the issue issues are identical.
                print(f'Skipping issue (already exists).')
                return
            else:
                # There may be cases (rebasing) where a different SHA means the above comparison is False but the
                # issue is otherwise identical.
                # For now, if an issue already exists with the same title and file name, we will ignore it.
                # This should cover most use cases. Long term we should improve how the action handles rebasing.
                existing_issue_body = existing_issue['body']
                issue_exists = (formatted_issue_body in existing_issue_body
                                and issue.file_name in existing_issue_body
                                and issue.markdown_language in existing_issue_body)
                if issue_exists:
                    print(f'Skipping issue (already exists).')
                    return

        new_issue_body = {'title': title, 'body': body, 'labels': issue.labels}

        # We need to check if any assignees/milestone specified exist, otherwise issue creation will fail.
        valid_assignees = []
        if len(issue.assignees) == 0 and self.auto_assign:
            valid_assignees.append(self.actor)
        for assignee in issue.assignees:
            assignee_url = f'{self.repos_url}{self.repo}/assignees/{assignee}'
            assignee_request = requests.get(url=assignee_url, headers=self.issue_headers)
            if assignee_request.status_code == 204:
                valid_assignees.append(assignee)
            else:
                print(f'Assignee {assignee} does not exist! Dropping this assignee!')
        new_issue_body['assignees'] = valid_assignees

        if issue.milestone:
            milestone_url = f'{self.repos_url}{self.repo}/milestones/{issue.milestone}'
            milestone_request = requests.get(url=milestone_url, headers=self.issue_headers)
            if milestone_request.status_code == 200:
                new_issue_body['milestone'] = issue.milestone
            else:
                print(f'Milestone {issue.milestone} does not exist! Dropping this parameter!')

        new_issue_request = requests.post(url=self.issues_url, headers=self.issue_headers,
                                          data=json.dumps(new_issue_body))

        # Check if we should assign this issue to any projects.
        if new_issue_request.status_code == 201 and (len(issue.user_projects) > 0 or len(issue.org_projects) > 0):
            issue_json = new_issue_request.json()
            issue_id = issue_json['id']

            if len(issue.user_projects) > 0:
                self.add_issue_to_projects(issue_id, issue.user_projects, 'user')
            if len(issue.org_projects) > 0:
                self.add_issue_to_projects(issue_id, issue.org_projects, 'org')

        return new_issue_request.status_code

    def close_issue(self, issue):
        """Check to see if this issue can be found on GitHub and if so close it."""
        matched = 0
        issue_number = None
        for existing_issue in self.existing_issues:
            # This is admittedly a simple check that may not work in complex scenarios, but we can't deal with them yet.
            if existing_issue['title'] == issue.title:
                matched += 1
                # If there are multiple issues with similar titles, don't try and close any.
                if matched > 1:
                    print(f'Skipping issue (multiple matches)')
                    break
                issue_number = existing_issue['number']
        else:
            # The titles match, so we will try and close the issue.
            update_issue_url = f'{self.repos_url}{self.repo}/issues/{issue_number}'
            body = {'state': 'closed'}
            requests.patch(update_issue_url, headers=self.issue_headers, data=json.dumps(body))

            issue_comment_url = f'{self.repos_url}{self.repo}/issues/{issue_number}/comments'
            body = {'body': f'Closed in {self.sha}'}
            update_issue_request = requests.post(issue_comment_url, headers=self.issue_headers,
                                                 data=json.dumps(body))
            return update_issue_request.status_code
        return None

    def add_issue_to_projects(self, issue_id, projects, projects_type):
        """Attempt to add this issue to the specified user or organisation projects."""
        projects_secret = os.getenv('INPUT_PROJECTS_SECRET', None)
        if not projects_secret:
            print('You need to create and set PROJECTS_SECRET to use projects')
            return
        projects_headers = {
            'Accept': 'application/vnd.github.inertia-preview+json',
            'Authorization': f'token {projects_secret}'
        }

        # Loop through all the projects that we should assign this issue to.
        for i, project in enumerate(projects):
            print(f'Adding issue to {projects_type} project {i + 1} of {len(projects)}')
            project = project.replace(' / ', '/')
            try:
                entity_name, project_name, column_name = project.split('/')
            except ValueError:
                print('Invalid project syntax')
                continue
            entity_name = entity_name.strip()
            project_name = project_name.strip()
            column_name = column_name.strip()

            if projects_type == 'user':
                projects_url = f'{self.base_url}users/{entity_name}/projects'
            elif projects_type == 'org':
                projects_url = f'{self.base_url}orgs/{entity_name}/projects'
            else:
                return

            # We need to use the project name to get its ID.
            projects_request = requests.get(url=projects_url, headers=projects_headers)
            if projects_request.status_code == 200:
                projects_json = projects_request.json()
                for project_dict in projects_json:
                    if project_dict['name'].lower() == project_name.lower():
                        project_id = project_dict['id']
                        break
                else:
                    print('Project does not exist, skipping')
                    continue
            else:
                print('An error occurred, skipping')
                continue

            # Use the project ID and column name to get the column ID.
            columns_url = f'{self.base_url}projects/{project_id}/columns'
            columns_request = requests.get(url=columns_url, headers=projects_headers)
            if columns_request.status_code == 200:
                columns_json = columns_request.json()
                for column_dict in columns_json:
                    if column_dict['name'].lower() == column_name.lower():
                        column_id = column_dict['id']
                        break
                else:
                    print('Column does not exist, skipping')
                    continue
            else:
                print('An error occurred, skipping')
                continue

            # Use the column ID to assign the issue to the project.
            new_card_url = f'{self.base_url}projects/columns/{column_id}/cards'
            new_card_body = {
                'content_id': int(issue_id),
                'content_type': 'Issue'
            }
            new_card_request = requests.post(url=new_card_url, headers=projects_headers,
                                             data=json.dumps(new_card_body))
            if new_card_request.status_code == 201:
                print('Issue card added to project')
            else:
                print('Issue card could not be added to project')


class TodoParser(object):
    """Parser for extracting information from a given diff file."""
    FILE_HUNK_PATTERN = r'(?<=diff)(.*?)(?=diff\s--git\s)'
    HEADER_PATTERN = r'(?<=--git).*?(?=$\n(index|new|deleted))'
    LINE_PATTERN = r'^.*$'
    FILENAME_PATTERN = re.compile(r'(?<=a/).+?(?=\sb/)')
    LINE_NUMBERS_PATTERN = re.compile(r'@@[\d\s,\-+]*\s@@.*')
    LINE_NUMBERS_INNER_PATTERN = re.compile(r'@@[\d\s,\-+]*\s@@')
    ADDITION_PATTERN = re.compile(r'(?<=^\+).*')
    DELETION_PATTERN = re.compile(r'(?<=^-).*')
    REF_PATTERN = re.compile(r'.+?(?=\))')
    LABELS_PATTERN = re.compile(r'(?<=labels:\s).+')
    ASSIGNEES_PATTERN = re.compile(r'(?<=assignees:\s).+')
    MILESTONE_PATTERN = re.compile(r'(?<=milestone:\s).+')
    USER_PROJECTS_PATTERN = re.compile(r'(?<=user projects:\s).+')
    ORG_PROJECTS_PATTERN = re.compile(r'(?<=org projects:\s).+')

    def __init__(self):
        # We could support more identifiers later quite easily.
        self.identifier = 'TODO'
        self.languages_dict = None

        # Load the languages data for ascertaining file types.
        languages_url = 'https://raw.githubusercontent.com/github/linguist/master/lib/linguist/languages.yml'
        languages_request = requests.get(url=languages_url)
        if languages_request.status_code == 200:
            languages_data = languages_request.text
            yaml = YAML(typ='safe')
            self.languages_dict = yaml.load(languages_data)
        else:
            raise Exception('Cannot retrieve languages data. Operation will abort.')

        # Load the comment syntax data for identifying comments.
        syntax_url = 'https://raw.githubusercontent.com/alstr/todo-to-issue-action/master/syntax.json'
        syntax_request = requests.get(url=syntax_url)
        if syntax_request.status_code == 200:
            self.syntax_dict = syntax_request.json()
        else:
            raise Exception('Cannot retrieve syntax data. Operation will abort.')

    # noinspection PyTypeChecker
    def parse(self, diff_file):
        issues = []

        # The parser works by gradually breaking the diff file down into smaller and smaller segments.
        # At each level relevant information is extracted.

        # First separate the diff into sections for each changed file.
        file_hunks = re.finditer(self.FILE_HUNK_PATTERN, diff_file.read(), re.DOTALL)
        last_end = None
        extracted_file_hunks = []
        for i, file_hunk in enumerate(file_hunks):
            extracted_file_hunks.append(file_hunk.group(0))
            last_end = file_hunk.end()
        diff_file.seek(0)
        extracted_file_hunks.append(diff_file.read()[last_end:])
        diff_file.close()

        code_blocks = []
        prev_block = None
        # Iterate through each section extracted above.
        for hunk in extracted_file_hunks:
            # Extract the file information so we can figure out the markdown language and comment syntax.
            header_search = re.search(self.HEADER_PATTERN, hunk, re.MULTILINE)
            if not header_search:
                continue
            files = header_search.group(0)

            filename_search = re.search(self.FILENAME_PATTERN, files)
            if not filename_search:
                continue
            curr_file = filename_search.group(0)
            if self._should_ignore(curr_file):
                continue
            curr_markers, curr_markdown_language = self._get_file_details(curr_file)
            if not curr_markers or not curr_markdown_language:
                print(f'Could not check {curr_file} for TODOs as this language is not yet supported by default.')
                continue

            # Break this section down into individual changed code blocks.
            line_numbers = re.finditer(self.LINE_NUMBERS_PATTERN, hunk)
            for i, line_numbers in enumerate(line_numbers):
                line_numbers_inner_search = re.search(self.LINE_NUMBERS_INNER_PATTERN, line_numbers.group(0))
                line_numbers_str = line_numbers_inner_search.group(0).strip('@@ -')
                start_line = line_numbers_str.split(' ')[1].strip('+')
                start_line = int(start_line.split(',')[0])

                # Put this information into a temporary dict for simplicity.
                block = {
                    'file': curr_file,
                    'markers': curr_markers,
                    'markdown_language': curr_markdown_language,
                    'start_line': start_line,
                    'hunk': hunk,
                    'hunk_start': line_numbers.end(),
                    'hunk_end': None
                }

                prev_index = len(code_blocks) - 1
                # Set the end of the last code block based on the start of this one.
                if prev_block and prev_block['file'] == block['file']:
                    code_blocks[prev_index]['hunk_end'] = line_numbers.start()
                    code_blocks[prev_index]['hunk'] = (prev_block['hunk']
                                                       [prev_block['hunk_start']:line_numbers.start()])
                elif prev_block:
                    code_blocks[prev_index]['hunk'] = prev_block['hunk'][prev_block['hunk_start']:]

                code_blocks.append(block)
                prev_block = block

        if len(code_blocks) > 0:
            last_index = len(code_blocks) - 1
            last_block = code_blocks[last_index]
            code_blocks[last_index]['hunk'] = last_block['hunk'][last_block['hunk_start']:]

        # Now for each code block, check for comments, then those comments for TODOs.
        for block in code_blocks:
            for marker in block['markers']:
                # Check if there are line or block comments.
                if marker['type'] == 'line':
                    comment_pattern = r'(^[+\-\s]\s*' + marker['pattern'] + '.+$)'
                    comments = re.finditer(comment_pattern, block['hunk'], re.MULTILINE)
                    extracted_comments = []
                    prev_comment = None
                    for i, comment in enumerate(comments):
                        if i == 0 or self.identifier in comment.group(0):
                            extracted_comments.append([comment])
                        else:
                            if comment.start() == prev_comment.end() + 1:
                                extracted_comments[len(extracted_comments) - 1].append(comment)
                        prev_comment = comment
                    for comment in extracted_comments:
                        issue = self._extract_issue_if_exists(comment, marker, block)
                        if issue:
                            issues.append(issue)
                else:
                    comment_pattern = (r'(?:[+\-\s]\s*' + marker['pattern']['start'] + r'.*?'
                                       + marker['pattern']['end'] + ')')
                    comments = re.finditer(comment_pattern, block['hunk'], re.DOTALL)
                    extracted_comments = []
                    for i, comment in enumerate(comments):
                        if self.identifier in comment.group(0):
                            extracted_comments.append([comment])

                    for comment in extracted_comments:
                        issue = self._extract_issue_if_exists(comment, marker, block)
                        if issue:
                            issues.append(issue)

        default_user_projects = os.getenv('INPUT_USER_PROJECTS', None)
        default_org_projects = os.getenv('INPUT_ORG_PROJECTS', None)
        for i, issue in enumerate(issues):
            # Strip some of the diff symbols so it can be included as a code snippet in the issue body.
            # Strip removed lines.
            cleaned_hunk = re.sub(r'\n^-.*$', '', issue.hunk, 0, re.MULTILINE)
            # Strip leading symbols/whitespace.
            cleaned_hunk = re.sub(r'^.', '', cleaned_hunk, 0, re.MULTILINE)
            # Strip newline message.
            cleaned_hunk = re.sub(r'\n\sNo newline at end of file', '', cleaned_hunk, 0, re.MULTILINE)
            issue.hunk = cleaned_hunk

            # If no projects have been specified for this issue, assign any default projects that exist.
            if len(issue.user_projects) == 0 and default_user_projects is not None:
                separated_user_projects = self._get_projects(f'user projects: {default_user_projects}', 'user')
                issue.user_projects = separated_user_projects
            if len(issue.org_projects) == 0 and default_org_projects is not None:
                separated_org_projects = self._get_projects(f'org projects: {default_org_projects}', 'org')
                issue.org_projects = separated_org_projects
        return issues

    def _get_file_details(self, file):
        """Try and get the markdown language and comment syntax data for the given file."""
        file_name, extension = os.path.splitext(os.path.basename(file))
        for language_name in self.languages_dict:
            if ('extensions' in self.languages_dict[language_name]
                    and extension in self.languages_dict[language_name]['extensions']):
                for syntax_details in self.syntax_dict:
                    if syntax_details['language'] == language_name:
                        return syntax_details['markers'], self.languages_dict[language_name]['ace_mode']
        return None, None

    def _extract_issue_if_exists(self, comment, marker, code_block):
        """Check this comment for TODOs, and if found, build an Issue object."""
        issue = None
        for match in comment:
            lines = match.group().split('\n')
            for line in lines:
                line_status, committed_line = self._get_line_status(line)
                cleaned_line = self._clean_line(committed_line, marker)
                line_title, ref = self._get_title(cleaned_line)
                if line_title:
                    if ref:
                        issue_title = f'[{ref}] {line_title}'
                    else:
                        issue_title = line_title
                    issue = Issue(
                        title=issue_title,
                        labels=['todo'],
                        assignees=[],
                        milestone=None,
                        user_projects=[],
                        org_projects=[],
                        body=[line_title],
                        hunk=code_block['hunk'],
                        file_name=code_block['file'],
                        start_line=code_block['start_line'],
                        markdown_language=code_block['markdown_language'],
                        status=line_status
                    )

                    # Calculate the file line number that this issue references.
                    hunk_lines = re.finditer(self.LINE_PATTERN, code_block['hunk'], re.MULTILINE)
                    start_line = code_block['start_line']
                    for i, hunk_line in enumerate(hunk_lines):
                        if hunk_line.group(0) == line:
                            issue.start_line = start_line
                            break
                        if i != 0 and (hunk_line.group(0).startswith('+') or not hunk_line.group(0).startswith('-')):
                            start_line += 1

                elif issue:
                    # Extract other issue information that may exist.
                    line_labels = self._get_labels(cleaned_line)
                    line_assignees = self._get_assignees(cleaned_line)
                    line_milestone = self._get_milestone(cleaned_line)
                    user_projects = self._get_projects(cleaned_line, 'user')
                    org_projects = self._get_projects(cleaned_line, 'org')
                    if line_labels:
                        issue.labels.extend(line_labels)
                    elif line_assignees:
                        issue.assignees.extend(line_assignees)
                    elif line_milestone and not issue.milestone:
                        issue.milestone = line_milestone
                    elif user_projects:
                        issue.user_projects.extend(user_projects)
                    elif org_projects:
                        issue.org_projects.extend(org_projects)
                    elif len(cleaned_line):
                        issue.body.append(cleaned_line)
        return issue

    def _get_line_status(self, comment):
        """Return a Tuple indicating whether this is an addition/deletion/unchanged, plus the cleaned comment."""
        addition_search = self.ADDITION_PATTERN.search(comment)
        if addition_search:
            return LineStatus.ADDED, addition_search.group(0)
        else:
            deletion_search = self.DELETION_PATTERN.search(comment)
            if deletion_search:
                return LineStatus.DELETED, deletion_search.group(0)
        return LineStatus.UNCHANGED, comment[1:]

    @staticmethod
    def _clean_line(comment, marker):
        """Remove unwanted symbols and whitespace."""
        comment = comment.strip()
        if marker['type'] == 'block':
            start_pattern = r'^' + marker['pattern']['start']
            end_pattern = marker['pattern']['end'] + r'$'
            comment = re.sub(start_pattern, '', comment)
            comment = re.sub(end_pattern, '', comment)
            # Some block comments might have an asterisk on each line.
            if '*' in start_pattern and comment.startswith('*'):
                comment = comment.lstrip('*')
        else:
            pattern = r'^' + marker['pattern']
            comment = re.sub(pattern, '', comment)
        return comment.strip()

    def _get_title(self, comment):
        """Check the passed comment for a new issue title (and reference, if specified)."""
        title = None
        ref = None
        title_pattern = re.compile(r'(?<=' + self.identifier + r'[\s:]).+')
        title_search = title_pattern.search(comment, re.IGNORECASE)
        if title_search:
            title = title_search.group(0).strip()
        else:
            title_ref_pattern = re.compile(r'(?<=' + self.identifier + r'\().+')
            title_ref_search = title_ref_pattern.search(comment, re.IGNORECASE)
            if title_ref_search:
                title = title_ref_search.group(0).strip()
                ref_search = self.REF_PATTERN.search(title)
                if ref_search:
                    ref = ref_search.group(0)
                    title = title.replace(ref, '', 1).lstrip(':) ')
        return title, ref

    def _get_labels(self, comment):
        """Check the passed comment for issue labels."""
        labels_search = self.LABELS_PATTERN.search(comment, re.IGNORECASE)
        labels = []
        if labels_search:
            labels = labels_search.group(0).replace(', ', ',')
            labels = list(filter(None, labels.split(',')))
        return labels

    def _get_assignees(self, comment):
        """Check the passed comment for issue assignees."""
        assignees_search = self.ASSIGNEES_PATTERN.search(comment, re.IGNORECASE)
        assignees = []
        if assignees_search:
            assignees = assignees_search.group(0).replace(', ', ',')
            assignees = list(filter(None, assignees.split(',')))
        return assignees

    def _get_milestone(self, comment):
        """Check the passed comment for a milestone."""
        milestone_search = self.MILESTONE_PATTERN.search(comment, re.IGNORECASE)
        milestone = None
        if milestone_search:
            milestone = milestone_search.group(0)
            if milestone.isdigit():
                milestone = int(milestone)
        return milestone

    def _get_projects(self, comment, projects_type):
        """Check the passed comment for projects to link the issue to."""
        projects = []
        if projects_type == 'user':
            projects_search = self.USER_PROJECTS_PATTERN.search(comment, re.IGNORECASE)
        elif projects_type == 'org':
            projects_search = self.ORG_PROJECTS_PATTERN.search(comment, re.IGNORECASE)
        else:
            return projects
        if projects_search:
            projects = projects_search.group(0).replace(', ', ',')
            projects = list(filter(None, projects.split(',')))
        return projects

    def _should_ignore(self, file):
        ignore_patterns = os.getenv('INPUT_IGNORE', None)
        if ignore_patterns:
            for pattern in filter(None, [pattern.strip() for pattern in ignore_patterns.split(',')]):
                if re.match(pattern, file):
                    return True
        return False


if __name__ == "__main__":
    # Create a basic client for communicating with GitHub, automatically initialised with environment variables.
    client = GitHubClient()
    if client.diff_url or len(client.commits) != 0:
        # Get the diff from the last pushed commit.
        last_diff = StringIO(client.get_last_diff())
        # Parse the diff for TODOs and create an Issue object for each.
        raw_issues = TodoParser().parse(last_diff)
        # This is a simple, non-perfect check to filter out any TODOs that have just been moved.
        # It looks for items that appear in the diff as both an addition and deletion.
        # It is based on the assumption that TODOs will not have identical titles in identical files.
        issues_to_process = []
        for values, similar_issues in itertools.groupby(raw_issues, key=operator.attrgetter('title', 'file_name',
                                                                                            'markdown_language')):
            similar_issues = list(similar_issues)
            if (len(similar_issues) == 2 and ((similar_issues[0].status == LineStatus.ADDED and
                                               similar_issues[1].status == LineStatus.DELETED) or
                                              (similar_issues[1].status == LineStatus.ADDED and
                                               similar_issues[0].status == LineStatus.DELETED))):
                print(f'Issue "{values[0]}" appears as both addition and deletion. '
                      f'Assuming this issue has been moved so skipping.')
                continue
            issues_to_process.extend(similar_issues)
        # Cycle through the Issue objects and create or close a corresponding GitHub issue for each.
        for j, raw_issue in enumerate(issues_to_process):
            print(f'Processing issue {j + 1} of {len(issues_to_process)}')
            if raw_issue.status == LineStatus.ADDED:
                status_code = client.create_issue(raw_issue)
                if status_code == 201:
                    print('Issue created')
                else:
                    print('Issue could not be created')
            elif raw_issue.status == LineStatus.DELETED and os.getenv('INPUT_CLOSE_ISSUES', 'true') == 'true':
                status_code = client.close_issue(raw_issue)
                if status_code == 201:
                    print('Issue closed')
                else:
                    print('Issue could not be closed')
            # Stagger the requests to be on the safe side.
            sleep(1)
