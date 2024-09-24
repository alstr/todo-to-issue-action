# -*- coding: utf-8 -*-
"""Convert IDE TODOs to GitHub issues."""

import os
import requests
import re
import json
from time import sleep
from io import StringIO
from ruamel.yaml import YAML
from enum import Enum
import itertools
import operator
from collections import defaultdict
from urllib.parse import urlparse


class LineStatus(Enum):
    """Represents the status of a line in a diff file."""
    ADDED = 0
    DELETED = 1
    UNCHANGED = 2


class Issue(object):
    """Basic Issue model for collecting the necessary info to send to GitHub."""

    def __init__(self, title, labels, assignees, milestone, body, hunk, file_name,
                 start_line, num_lines, markdown_language, status, identifier, ref, issue_url, issue_number):
        self.title = title
        self.labels = labels
        self.assignees = assignees
        self.milestone = milestone
        self.body = body
        self.hunk = hunk
        self.file_name = file_name
        self.start_line = start_line
        self.num_lines = num_lines
        self.markdown_language = markdown_language
        self.status = status
        self.identifier = identifier
        self.ref = ref
        self.issue_url = issue_url
        self.issue_number = issue_number


class GitHubClient(object):
    """Basic client for getting the last diff and managing issues."""
    existing_issues = []
    milestones = []

    def __init__(self):
        self.github_url = os.getenv('INPUT_GITHUB_URL')
        self.base_url = f'{self.github_url}/'
        self.repos_url = f'{self.base_url}repos/'
        self.repo = os.getenv('INPUT_REPO')
        self.before = os.getenv('INPUT_BEFORE')
        self.sha = os.getenv('INPUT_SHA')
        self.commits = json.loads(os.getenv('INPUT_COMMITS')) or []
        self.diff_url = os.getenv('INPUT_DIFF_URL')
        self.token = os.getenv('INPUT_TOKEN')
        self.issues_url = f'{self.repos_url}{self.repo}/issues'
        self.milestones_url = f'{self.repos_url}{self.repo}/milestones'
        self.issue_headers = {
            'Content-Type': 'application/json',
            'Authorization': f'token {self.token}',
            'X-GitHub-Api-Version': '2022-11-28'
        }
        self.graphql_headers = {
            'Authorization': f'Bearer {os.getenv("INPUT_PROJECTS_SECRET", "")}',
            'Accept': 'application/vnd.github.v4+json'
        }
        auto_p = os.getenv('INPUT_AUTO_P', 'true') == 'true'
        self.line_break = '\n\n' if auto_p else '\n'
        self.auto_assign = os.getenv('INPUT_AUTO_ASSIGN', 'false') == 'true'
        self.actor = os.getenv('INPUT_ACTOR')
        self.insert_issue_urls = os.getenv('INPUT_INSERT_ISSUE_URLS', 'false') == 'true'
        if self.base_url == 'https://api.github.com/':
            self.line_base_url = 'https://github.com/'
        else:
            self.line_base_url = self.base_url
        self.project = os.getenv('INPUT_PROJECT', None)
        # Retrieve the existing repo issues now so we can easily check them later.
        self._get_existing_issues()
        # Populate milestones so we can perform a lookup if one is specified.
        self._get_milestones()

    def get_last_diff(self):
        """Get the last diff."""
        if self.diff_url:
            # Diff url was directly passed in config, likely due to this being a PR.
            diff_url = self.diff_url
        elif self.before != '0000000000000000000000000000000000000000':
            # There is a valid before SHA to compare with, or this is a release being created.
            diff_url = f'{self.repos_url}{self.repo}/compare/{self.before}...{self.sha}'
        elif len(self.commits) == 1:
            # There is only one commit.
            diff_url = f'{self.repos_url}{self.repo}/commits/{self.sha}'
        else:
            # There are several commits: compare with the oldest one.
            oldest = sorted(self.commits, key=self._get_timestamp)[0]['id']
            diff_url = f'{self.repos_url}{self.repo}/compare/{oldest}...{self.sha}'

        diff_headers = {
            'Accept': 'application/vnd.github.v3.diff',
            'Authorization': f'token {self.token}',
            'X-GitHub-Api-Version': '2022-11-28'
        }
        diff_request = requests.get(url=diff_url, headers=diff_headers)
        if diff_request.status_code == 200:
            return diff_request.text
        raise Exception('Could not retrieve diff. Operation will abort.')

    # noinspection PyMethodMayBeStatic
    def _get_timestamp(self, commit):
        """Get a commit timestamp."""
        return commit.get('timestamp')

    def _get_milestones(self, page=1):
        """Get all the milestones."""
        params = {
            'per_page': 100,
            'page': page,
            'state': 'open'
        }
        milestones_request = requests.get(self.milestones_url, headers=self.issue_headers, params=params)
        if milestones_request.status_code == 200:
            self.milestones.extend(milestones_request.json())
            links = milestones_request.links
            if 'next' in links:
                self._get_milestones(page + 1)

    def _get_milestone(self, title):
        """Get the milestone number for the one with this title (creating one if it doesn't exist)."""
        for m in self.milestones:
            if m['title'] == title:
                return m['number']
        else:
            return self._create_milestone(title)

    def _create_milestone(self, title):
        """Create a new milestone with this title."""
        milestone_data = {
            'title': title
        }
        milestone_request = requests.post(self.milestones_url, headers=self.issue_headers, json=milestone_data)
        return milestone_request.json()['number'] if milestone_request.status_code == 201 else None

    def _get_existing_issues(self, page=1):
        """Populate the existing issues list."""
        params = {
            'per_page': 100,
            'page': page,
            'state': 'open'
        }
        list_issues_request = requests.get(self.issues_url, headers=self.issue_headers, params=params)
        if list_issues_request.status_code == 200:
            self.existing_issues.extend(list_issues_request.json())
            links = list_issues_request.links
            if 'next' in links:
                self._get_existing_issues(page + 1)

    def _get_project_id(self, project):
        """Get the project ID."""
        project_type, owner, project_name = project.split('/')
        if project_type == 'user':
            query = """
            query($owner: String!) {
                user(login: $owner) {
                    projectsV2(first: 10) {
                        nodes {
                            id
                            title
                        }
                    }
                }
            }
            """
        elif project_type == 'organization':
            query = """
            query($owner: String!) {
                organization(login: $owner) {
                    projectsV2(first: 10) {
                        nodes {
                            id
                            title
                        }
                    }
                }
            }
            """
        else:
            print("Invalid project type")
            return None

        variables = {
            'owner': owner,
        }
        project_request = requests.post('https://api.github.com/graphql',
                                        json={'query': query, 'variables': variables},
                                        headers=self.graphql_headers)
        if project_request.status_code == 200:
            projects = (project_request.json().get('data', {}).get(project_type, {}).get('projectsV2', {})
                        .get('nodes', []))
            for project in projects:
                if project['title'] == project_name:
                    return project['id']
        return None

    def _get_issue_global_id(self, owner, repo, issue_number):
        """Get the global ID for a given issue."""
        query = """
        query($owner: String!, $repo: String!, $issue_number: Int!) {
            repository(owner: $owner, name: $repo) {
                issue(number: $issue_number) {
                    id
                }
            }
        }
        """
        variables = {
            'owner': owner,
            'repo': repo,
            'issue_number': issue_number
        }
        project_request = requests.post('https://api.github.com/graphql',
                                        json={'query': query, 'variables': variables},
                                        headers=self.graphql_headers)
        if project_request.status_code == 200:
            return project_request.json()['data']['repository']['issue']['id']
        return None

    def _add_issue_to_project(self, issue_id, project_id):
        """Attempt to add this issue to a project."""
        mutation = """
        mutation($projectId: ID!, $contentId: ID!) {
            addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
                item {
                    id
                }
            }
        }
        """
        variables = {
            "projectId": project_id,
            "contentId": issue_id
        }
        project_request = requests.post('https://api.github.com/graphql',
                                        json={'query': mutation, 'variables': variables},
                                        headers=self.graphql_headers)
        return project_request.status_code

    def _comment_issue(self, issue_number, comment):
        """Post a comment on an issue."""
        issue_comment_url = f'{self.repos_url}{self.repo}/issues/{issue_number}/comments'
        body = {'body': comment}
        update_issue_request = requests.post(issue_comment_url, headers=self.issue_headers, json=body)
        return update_issue_request.status_code

    def create_issue(self, issue):
        """Create a dict containing the issue details and send it to GitHub."""
        formatted_issue_body = self.line_break.join(issue.body)
        line_num_anchor = f'#L{issue.start_line}'
        if issue.num_lines > 1:
            line_num_anchor += f'-L{issue.start_line + issue.num_lines - 1}'
        url_to_line = f'{self.line_base_url}{self.repo}/blob/{self.sha}/{issue.file_name}{line_num_anchor}'
        snippet = '```' + issue.markdown_language + '\n' + issue.hunk + '\n' + '```'

        issue_template = os.getenv('INPUT_ISSUE_TEMPLATE', None)
        if issue_template:
            issue_contents = (issue_template.replace('{{ title }}', issue.title)
                              .replace('{{ body }}', formatted_issue_body)
                              .replace('{{ url }}', url_to_line)
                              .replace('{{ snippet }}', snippet)
                              )
        elif len(issue.body) != 0:
            issue_contents = formatted_issue_body + '\n\n' + url_to_line + '\n\n' + snippet
        else:
            issue_contents = url_to_line + '\n\n' + snippet

        endpoint = self.issues_url
        if issue.issue_url:
            # Issue already exists, update existing rather than create new.
            endpoint += f'/{issue.issue_number}'

        title = issue.title

        if issue.ref:
            if issue.ref.startswith('@'):
                # Ref = assignee.
                issue.assignees.append(issue.ref.lstrip('@'))
            elif issue.ref.startswith('!'):
                # Ref = label.
                issue.labels.append(issue.ref.lstrip('!'))
            elif issue.ref.startswith('#'):
                # Ref = issue number (indicating this is a comment on that issue).
                issue_number = issue.ref.lstrip('#')
                if issue_number.isdigit():
                    # Create the comment now.
                    return self._comment_issue(issue_number, f'{issue.title}\n\n{issue_contents}'), None
            else:
                # Just prepend the ref to the title.
                title = f'[{issue.ref}] {issue.title}'

        title = title + '...' if len(title) > 80 else title
        new_issue_body = {'title': title, 'body': issue_contents, 'labels': issue.labels}

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
            milestone_number = self._get_milestone(issue.milestone)
            if milestone_number:
                new_issue_body['milestone'] = milestone_number
            else:
                print(f'Milestone {issue.milestone} could not be set. Dropping this milestone!')

        if issue.issue_url:
            # Update existing issue.
            issue_request = requests.patch(url=endpoint, headers=self.issue_headers, json=new_issue_body)
        else:
            # Create new issue.
            issue_request = requests.post(url=endpoint, headers=self.issue_headers, json=new_issue_body)

        request_status = issue_request.status_code
        issue_number = issue_request.json()['number'] if request_status in [200, 201] else None

        # Check if issue should be added to a project now it exists.
        if issue_number and self.project:
            project_id = self._get_project_id(self.project)
            if project_id:
                owner, repo = self.repo.split('/')
                issue_id = self._get_issue_global_id(owner, repo, issue_number)
                if issue_id:
                    self._add_issue_to_project(issue_id, project_id)

        return request_status, issue_number

    def close_issue(self, issue):
        """Check to see if this issue can be found on GitHub and if so close it."""
        issue_number = None
        if issue.issue_number:
            # If URL insertion is enabled.
            issue_number = issue.issue_number
        else:
            # Try simple matching.
            matched = 0
            for existing_issue in self.existing_issues:
                if existing_issue['title'] == issue.title:
                    matched += 1
                    # If there are multiple issues with similar titles, don't try and close any.
                    if matched > 1:
                        print(f'Skipping issue (multiple matches)')
                        break
                    issue_number = existing_issue['number']
        if issue_number:
            update_issue_url = f'{self.issues_url}/{issue_number}'
            body = {'state': 'closed'}
            requests.patch(update_issue_url, headers=self.issue_headers, json=body)
            request_status = self._comment_issue(issue_number, f'Closed in {self.sha}.')

            # Update the description if this is a PR.
            if os.getenv('GITHUB_EVENT_NAME') == 'pull_request':
                pr_number = os.getenv('PR_NUMBER')
                if pr_number:
                    request_status = self._update_pr_body(pr_number, body)
            return request_status
        return None

    def _update_pr_body(self, pr_number, issue_number):
        """Add a close message for an issue to a PR."""
        pr_url = f'{self.repos_url}{self.repo}/pulls/{pr_number}'
        pr_request = requests.get(pr_url, headers=self.issue_headers)
        if pr_request.status_code == 200:
            pr_body = pr_request.json()['body']
            close_message = f'Closes #{issue_number}'
            if close_message not in pr_body:
                updated_pr_body = f'{pr_body}\n\n{close_message}' if pr_body.strip() else close_message
                body = {'body': updated_pr_body}
                pr_update_request = requests.patch(pr_url, headers=self.issue_headers, json=body)
                return pr_update_request.status_code
        return pr_request.status_code


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
    LABELS_PATTERN = re.compile(r'(?<=labels:\s).+', re.IGNORECASE)
    ASSIGNEES_PATTERN = re.compile(r'(?<=assignees:\s).+', re.IGNORECASE)
    MILESTONE_PATTERN = re.compile(r'(?<=milestone:\s).+', re.IGNORECASE)
    ISSUE_URL_PATTERN = re.compile(r'(?<=Issue URL:\s).+', re.IGNORECASE)
    ISSUE_NUMBER_PATTERN = re.compile(r'/issues/(\d+)', re.IGNORECASE)

    def __init__(self):
        # Determine if the issues should be escaped.
        self.should_escape = os.getenv('INPUT_ESCAPE', 'true') == 'true'
        # Load any custom identifiers, otherwise use the default.
        custom_identifiers = os.getenv('INPUT_IDENTIFIERS')
        self.identifiers = ['TODO']
        self.identifiers_dict = None
        if custom_identifiers:
            try:
                custom_identifiers_dict = json.loads(custom_identifiers)
                for identifier_dict in custom_identifiers_dict:
                    if type(identifier_dict['name']) is not str or type(identifier_dict['labels']) is not list:
                        raise TypeError
                self.identifiers = [identifier['name'] for identifier in custom_identifiers_dict]
                self.identifiers_dict = custom_identifiers_dict
            except (json.JSONDecodeError, KeyError, TypeError):
                print('Invalid identifiers dict, ignoring.')

        self.languages_dict = None
        # Check if the standard collections should be loaded.
        if os.getenv('INPUT_NO_STANDARD', 'false') != 'true':
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
        else:
            self.syntax_dict = []
            self.languages_dict = {}

        custom_languages = os.getenv('INPUT_LANGUAGES', '')
        if custom_languages != '':
            # Load all custom languages.
            for path in custom_languages.split(','):
                # noinspection PyBroadException
                try:
                    # Decide if the path is a url or local file.
                    if path.startswith('http'):
                        languages_request = requests.get(path)
                        if languages_request.status_code != 200:
                            print(f'Cannot retrieve custom language file "{path}".')
                            continue
                        data = languages_request.json()
                    else:
                        path = os.path.join(os.getcwd(), path)
                        if not os.path.exists(path) or not os.path.isfile(path):
                            print(f'Cannot retrieve custom language file "{path}".')
                            continue
                        f = open(path)
                        data = json.load(f)

                    # Iterate through the definitions.
                    for lang in data:
                        # Add/replace the language definition.
                        self.languages_dict[lang['language']] = {}
                        self.languages_dict[lang['language']]['type'] = ''
                        self.languages_dict[lang['language']]['color'] = ''
                        self.languages_dict[lang['language']]['extensions'] = lang['extensions']
                        self.languages_dict[lang['language']]['source'] = ''
                        self.languages_dict[lang['language']]['ace_mode'] = 'text'
                        self.languages_dict[lang['language']]['language_id'] = 0

                        # Check if comment syntax for the language name already exists.
                        counter = 0
                        exists = False
                        for syntax in self.syntax_dict:
                            if syntax['language'] == lang['language']:
                                exists = True
                                break

                            counter = counter + 1

                        if exists:
                            # When the syntax exists it will be popped out of the list.
                            self.syntax_dict.pop(counter)

                        # And be replaced with the new syntax definition.
                        self.syntax_dict.append({
                            'language': lang['language'],
                            'markers': lang['markers']
                        })
                except Exception:
                    print(f'An error occurred in the custom language file "{path}".')
                    print('Please check the file, or if it represents undefined behavior, '
                          'create an issue at https://github.com/alstr/todo-to-issue-action/issues.')

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
            # Extract the file information so we can figure out the Markdown language and comment syntax.
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
                print(f'Could not check "{curr_file}" for TODOs as this language is not yet supported by default.')
                continue

            # Break this section down into individual changed code blocks.
            line_numbers_iterator = re.finditer(self.LINE_NUMBERS_PATTERN, hunk)
            for i, line_numbers in enumerate(line_numbers_iterator):
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
                    # noinspection PyTypedDict
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
                    # Add a negative lookup to include the second character from alternative comment patterns.
                    # This step is essential to handle cases like in Julia, where '#' and '#=' are comment patterns.
                    # It ensures that when a space after the comment is optional ('\s' => '\s*'),
                    # the second character would be matched because of the any character expression ('.+').
                    suff_escape_list = []
                    pref_escape_list = []
                    for to_escape in block['markers']:
                        if to_escape['type'] == 'line':
                            if to_escape['pattern'] == marker['pattern']:
                                continue
                            if marker['pattern'][0] == to_escape['pattern'][0]:
                                suff_escape_list.append(self._extract_character(to_escape['pattern'], 1))
                        else:
                            # Block comments and line comments cannot have the same comment pattern,
                            # so a check if the string is the same is unnecessary.
                            if to_escape['pattern']['start'][0] == marker['pattern'][0]:
                                suff_escape_list.append(self._extract_character(to_escape['pattern']['start'], 1))
                            search = to_escape['pattern']['end'].find(marker['pattern'])
                            if search != -1:
                                pref_escape_list.append(self._extract_character(to_escape['pattern']['end'],
                                                                                search - 1))

                    comment_pattern = (r'(^.*'
                                       + (r'(?<!(' + '|'.join(pref_escape_list) + r'))' if len(pref_escape_list) > 0
                                          else '')
                                       + marker['pattern']
                                       + (r'(?!(' + '|'.join(suff_escape_list) + r'))' if len(suff_escape_list) > 0
                                          else '')
                                       + r'\s*.+$)')
                    comments = re.finditer(comment_pattern, block['hunk'], re.MULTILINE)
                    extracted_comments = []
                    prev_comment = None
                    for i, comment in enumerate(comments):
                        if prev_comment and comment.start() == prev_comment.end() + 1:
                            extracted_comments[len(extracted_comments) - 1].append(comment)
                        else:
                            extracted_comments.append([comment])
                        prev_comment = comment
                    for comment in extracted_comments:
                        extracted_issues = self._extract_issue_if_exists(comment, marker, block)
                        if extracted_issues:
                            issues.extend(extracted_issues)
                else:
                    comment_pattern = (r'(?:[+\-\s]\s*' + marker['pattern']['start'] + r'.*?'
                                       + marker['pattern']['end'] + ')')
                    comments = re.finditer(comment_pattern, block['hunk'], re.DOTALL)
                    extracted_comments = []
                    for i, comment in enumerate(comments):
                        if re.search('|'.join(self.identifiers), comment.group(0)):
                            extracted_comments.append([comment])

                    for comment in extracted_comments:
                        extracted_issues = self._extract_issue_if_exists(comment, marker, block)
                        if extracted_issues:
                            issues.extend(extracted_issues)

        for i, issue in enumerate(issues):
            # Strip some of the diff symbols so it can be included as a code snippet in the issue body.
            # Strip removed lines.
            cleaned_hunk = re.sub(r'\n^-.*$', '', issue.hunk, 0, re.MULTILINE)
            # Strip leading symbols/whitespace.
            cleaned_hunk = re.sub(r'^.', '', cleaned_hunk, 0, re.MULTILINE)
            # Strip newline message.
            cleaned_hunk = re.sub(r'\n\sNo newline at end of file', '', cleaned_hunk, 0, re.MULTILINE)
            issue.hunk = cleaned_hunk

        return issues

    def _get_language_details(self, language_name, attribute, value):
        """Try and get the Markdown language and comment syntax data based on a specified attribute of the language."""
        attributes = [at.lower() for at in self.languages_dict[language_name][attribute]]
        if value.lower() in attributes:
            for syntax_details in self.syntax_dict:
                if syntax_details['language'] == language_name:
                    return syntax_details['markers'], self.languages_dict[language_name]['ace_mode']
        return None, None

    def _get_file_details(self, file):
        """Try and get the Markdown language and comment syntax data for the given file."""
        file_name, extension = os.path.splitext(os.path.basename(file))
        for language_name in self.languages_dict:
            if extension != '' and 'extensions' in self.languages_dict[language_name]:
                syntax_details, ace_mode = self._get_language_details(language_name, 'extensions', extension)
                if syntax_details is not None and ace_mode is not None:
                    return syntax_details, ace_mode
            elif 'filenames' in self.languages_dict[language_name]:
                syntax_details, ace_mode = self._get_language_details(language_name, 'filenames', file_name)
                if syntax_details is not None and ace_mode is not None:
                    return syntax_details, ace_mode
        return None, None

    def _extract_issue_if_exists(self, comment, marker, code_block):
        """Check this comment for TODOs, and if found, build an Issue object."""
        curr_issue = None
        found_issues = []
        line_statuses = []
        prev_line_title = False
        for match in comment:
            comment_lines = match.group().split('\n')
            for line in comment_lines:
                line_status, committed_line = self._get_line_status(line)
                line_statuses.append(line_status)
                cleaned_line = self._clean_line(committed_line, marker)
                line_title, ref, identifier = self._get_title(cleaned_line)
                if line_title:
                    if prev_line_title and line_status == line_statuses[-2]:
                        # This means that there is a separate one-line TODO directly above this one.
                        # We need to store the previous one.
                        curr_issue.status = line_status
                        found_issues.append(curr_issue)
                    curr_issue = Issue(
                        title=line_title,
                        labels=[],
                        assignees=[],
                        milestone=None,
                        body=[],
                        hunk=code_block['hunk'],
                        file_name=code_block['file'],
                        start_line=code_block['start_line'],
                        num_lines=1,
                        markdown_language=code_block['markdown_language'],
                        status=line_status,
                        identifier=identifier,
                        ref=ref,
                        issue_url=None,
                        issue_number=None
                    )
                    prev_line_title = True

                    # Calculate the file line number that this issue references.
                    hunk_lines = re.finditer(self.LINE_PATTERN, code_block['hunk'], re.MULTILINE)
                    start_line = code_block['start_line']
                    for i, hunk_line in enumerate(hunk_lines):
                        if hunk_line.group(0) == line:
                            curr_issue.start_line = start_line
                            break
                        if i != 0 and (hunk_line.group(0).startswith('+') or not hunk_line.group(0).startswith('-')):
                            start_line += 1

                elif curr_issue:
                    # Extract other issue information that may exist below the title.
                    line_labels = self._get_labels(cleaned_line)
                    line_assignees = self._get_assignees(cleaned_line)
                    line_milestone = self._get_milestone(cleaned_line)
                    line_url = self._get_issue_url(cleaned_line)
                    if line_labels:
                        curr_issue.labels.extend(line_labels)
                    elif line_assignees:
                        curr_issue.assignees.extend(line_assignees)
                    elif line_milestone:
                        curr_issue.milestone = line_milestone
                    elif line_url:
                        curr_issue.issue_url = line_url
                        issue_number_search = self.ISSUE_NUMBER_PATTERN.search(line_url)
                        if issue_number_search:
                            curr_issue.issue_number = issue_number_search.group(1)
                    elif len(cleaned_line) and line_status != LineStatus.DELETED:
                        if self.should_escape:
                            curr_issue.body.append(self._escape_markdown(cleaned_line))
                        else:
                            curr_issue.body.append(cleaned_line)
                    if not line.startswith('-'):
                        curr_issue.num_lines += 1
                if not line_title:
                    prev_line_title = False
        if curr_issue is not None and curr_issue.identifier is not None and self.identifiers_dict is not None:
            for identifier_dict in self.identifiers_dict:
                if identifier_dict['name'] == curr_issue.identifier:
                    for label in identifier_dict['labels']:
                        if label not in curr_issue.labels:
                            curr_issue.labels.append(label)

        if curr_issue is not None:
            # If all the lines are unchanged, don't do anything.
            if all(s == LineStatus.UNCHANGED for s in line_statuses):
                return None
            # If the title line hasn't changed, but the info below has, we need to mark it as an update (addition).
            if (curr_issue.status == LineStatus.UNCHANGED
                    and (LineStatus.ADDED in line_statuses or LineStatus.DELETED in line_statuses)):
                curr_issue.status = LineStatus.ADDED

            found_issues.append(curr_issue)

        return found_issues

    @staticmethod
    def _escape_markdown(comment):
        # All basic characters according to: https://www.markdownguide.org/basic-syntax
        must_escape = ['\\', '<', '>', '#', '`', '*', '_', '[', ']', '(', ')', '!', '+', '-', '.', '|', '{', '}', '~',
                       '=']

        escaped = ''

        # Linear Escape Algorithm, because the algorithm ends in an infinite loop when using the function 'replace',
        # which tries to replace all backslashes with duplicate backslashes, i.e. also the already other escaped
        # characters.
        for c in comment:
            if c in must_escape:
                escaped += '\\' + c
            else:
                escaped += c
        return escaped

    @staticmethod
    def _extract_character(input_str, pos):
        # Extracts a character from the input string at the specified position,
        # considering escape sequences when applicable.
        # Test cases
        # print(_extract_character("/\\*", 1))   # Output: "\*"
        # print(_extract_character("\\*", 0))    # Output: "\*"
        # print(_extract_character("\\", 0))     # Output: "\\"
        # print(_extract_character("w", 0))      # Output: "w"
        # print(_extract_character("wa", 1))     # Output: "a"
        # print(_extract_character("\\\\w", 1))  # Output: "\\"
        if input_str[pos] == '\\':
            if pos >= 1 and not input_str[pos - 1] == '\\' and len(input_str) > pos + 1:
                return '\\' + input_str[pos + 1]
            return '\\\\'
        if pos >= 1:
            if input_str[pos - 1] == '\\':
                return '\\' + input_str[pos]
        return input_str[pos]

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
        title_identifier = None
        for identifier in self.identifiers:
            title_identifier = identifier
            title_pattern = re.compile(fr'(?<={identifier}[\s:]).+', re.IGNORECASE)
            title_search = title_pattern.search(comment, re.IGNORECASE)
            if title_search:
                title = title_search.group(0).strip(': ')
                break
            else:
                title_ref_pattern = re.compile(fr'(?<={identifier}\().+', re.IGNORECASE)
                title_ref_search = title_ref_pattern.search(comment, re.IGNORECASE)
                if title_ref_search:
                    title = title_ref_search.group(0).strip()
                    ref_search = self.REF_PATTERN.search(title)
                    if ref_search:
                        ref = ref_search.group(0)
                        title = title.replace(ref, '', 1).lstrip(':) ')
                    break
        return title, ref, title_identifier

    def _get_issue_url(self, comment):
        """Check the passed comment for a GitHub issue URL."""
        url_search = self.ISSUE_URL_PATTERN.search(comment, re.IGNORECASE)
        url = None
        if url_search:
            url = url_search.group(0)
            parsed_url = urlparse(url)
            return url if all([parsed_url.scheme, parsed_url.netloc]) else None
        return url

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
        return milestone

    # noinspection PyMethodMayBeStatic
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
    # Check to see if the workflow has been run manually.
    # If so, adjust the client SHA and diff URL to use the manually supplied inputs.
    manual_commit_ref = os.getenv('MANUAL_COMMIT_REF')
    manual_base_ref = os.getenv('MANUAL_BASE_REF')
    if manual_commit_ref:
        client.sha = manual_commit_ref
    if manual_commit_ref and manual_base_ref:
        print(f'Manually comparing {manual_base_ref}...{manual_commit_ref}')
        client.diff_url = f'{client.repos_url}{client.repo}/compare/{manual_base_ref}...{manual_commit_ref}'
    elif manual_commit_ref:
        print(f'Manual checking {manual_commit_ref}')
        client.diff_url = f'{client.repos_url}{client.repo}/commits/{manual_commit_ref}'
    if client.diff_url or len(client.commits) != 0:
        # Get the diff from the last pushed commit.
        last_diff = StringIO(client.get_last_diff())
        # Parse the diff for TODOs and create an Issue object for each.
        raw_issues = TodoParser().parse(last_diff)
        # This is a simple, non-perfect check to filter out any TODOs that have just been moved.
        # It looks for items that appear in the diff as both an addition and deletion.
        # It is based on the assumption that TODOs will not have identical titles in identical files.
        # That is about as good as we can do for TODOs without issue URLs.
        issues_to_process = []
        for values, similar_issues in itertools.groupby(raw_issues, key=operator.attrgetter('title', 'file_name',
                                                                                            'markdown_language')):
            similar_issues = list(similar_issues)
            if (len(similar_issues) == 2 and all(issue.issue_url is None for issue in similar_issues)
                    and ((similar_issues[0].status == LineStatus.ADDED
                          and similar_issues[1].status == LineStatus.DELETED)
                     or (similar_issues[1].status == LineStatus.ADDED
                         and similar_issues[0].status == LineStatus.DELETED))):
                print(f'Issue "{values[0]}" appears as both addition and deletion. '
                      f'Assuming this issue has been moved so skipping.')
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
        for j, raw_issue in enumerate(issues_to_process):
            print(f'Processing issue {j + 1} of {len(issues_to_process)}')
            if raw_issue.status == LineStatus.ADDED:
                status_code, new_issue_number = client.create_issue(raw_issue)
                if status_code == 201:
                    print('Issue created')
                    # Check to see if we should insert the issue URL back into the linked TODO.
                    # Don't insert URLs for comments. Comments do not get updated.
                    if client.insert_issue_urls and not (raw_issue.ref and raw_issue.ref.startswith('#')):
                        line_number = raw_issue.start_line - 1
                        with open(raw_issue.file_name, 'r') as issue_file:
                            file_lines = issue_file.readlines()
                        if line_number < len(file_lines):
                            # Duplicate the line to retain the comment syntax.
                            new_line = file_lines[line_number]
                            remove = fr'{raw_issue.identifier}.*{raw_issue.title}'
                            insert = f'Issue URL: {client.line_base_url}{client.repo}/issues/{new_issue_number}'
                            new_line = re.sub(remove, insert, new_line)
                            # Check if the URL line already exists, if so abort.
                            if line_number == len(file_lines) - 1 or file_lines[line_number + 1] != new_line:
                                file_lines.insert(line_number + 1, new_line)
                                with open(raw_issue.file_name, 'w') as issue_file:
                                    issue_file.writelines(file_lines)
                elif status_code == 200:
                    print('Issue updated')
                else:
                    print('Issue could not be created')
            elif raw_issue.status == LineStatus.DELETED and os.getenv('INPUT_CLOSE_ISSUES', 'true') == 'true':
                if raw_issue.ref and raw_issue.ref.startswith('#'):
                    print('Issue looks like a comment, will not attempt to close.')
                    continue
                status_code = client.close_issue(raw_issue)
                if status_code in [200, 201]:
                    print('Issue closed')
                else:
                    print('Issue could not be closed')
            # Stagger the requests to be on the safe side.
            sleep(1)
