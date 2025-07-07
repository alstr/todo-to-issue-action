import os
import requests
import json
import re
from urllib.parse import quote
from Client import Client

class GitHubClient(Client):
    """Basic client for getting the last diff and managing issues."""
    existing_issues = []
    milestones = []
    max_issue_title_length = 256

    def __init__(self):
        self.github_url = os.getenv('INPUT_GITHUB_URL')
        if not self.github_url:
            raise EnvironmentError
        self.base_url = f'{self.github_url}/'
        self.repos_url = f'{self.base_url}repos/'
        self.repo = os.getenv('INPUT_REPO')
        self.before = os.getenv('INPUT_BEFORE')
        self.sha = os.getenv('INPUT_SHA')
        self.commits = json.loads(os.getenv('INPUT_COMMITS')) or []
        self.__init_diff_url__()
        self.token = os.getenv('INPUT_TOKEN')
        self.issues_url = f'{self.repos_url}{self.repo}/issues'
        self.milestones_url = f'{self.repos_url}{self.repo}/milestones'
        self.issue_headers = {
            'Content-Type': 'application/json',
            'Authorization': f'token {self.token}',
            'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': 'TODOToIssue/5.1.9'
        }
        self.graphql_headers = {
            'Authorization': f'Bearer {os.getenv("INPUT_PROJECTS_SECRET", "")}',
            'Accept': 'application/vnd.github.v4+json',
            'User-Agent': 'TODOToIssue/5.1.9'
        }
        auto_p = os.getenv('INPUT_AUTO_P', 'true') == 'true'
        self.line_break = '\n\n' if auto_p else '\n'
        self.auto_assign = os.getenv('INPUT_AUTO_ASSIGN', 'false') == 'true'
        self.actor = os.getenv('INPUT_ACTOR')
        self.line_base_url = os.getenv('INPUT_GITHUB_SERVER_URL')
        if not self.line_base_url.endswith('/'):
            self.line_base_url += '/'
        self.project = os.getenv('INPUT_PROJECT', None)
        # Retrieve the existing repo issues now so we can easily check them later.
        self._get_existing_issues()
        # Populate milestones so we can perform a lookup if one is specified.
        self._get_milestones()

    def __init_diff_url__(self):
        manual_commit_ref = os.getenv('MANUAL_COMMIT_REF')
        manual_base_ref = os.getenv('MANUAL_BASE_REF')
        if manual_commit_ref:
            self.sha = manual_commit_ref
        if manual_commit_ref and manual_base_ref:
            print(f'Manually comparing {manual_base_ref}...{manual_commit_ref}')
            self.diff_url = f'{self.repos_url}{self.repo}/compare/{manual_base_ref}...{manual_commit_ref}'
        elif manual_commit_ref:
            print(f'Manual checking {manual_commit_ref}')
            self.diff_url = f'{self.repos_url}{self.repo}/commits/{manual_commit_ref}'
        else:
            self.diff_url = os.getenv('INPUT_DIFF_URL')

    def get_last_diff(self):
        """Get the last diff."""
        if self.diff_url:
            # Diff url was directly passed in config, likely due to this being a PR.
            diff_url = self.diff_url
            pr_url_pattern = r'/pull/(\d+)\.diff$'
            pr_search = re.search(pr_url_pattern, diff_url)
            if pr_search:
                pr_number = pr_search.group(1)
                diff_url = f'{self.repos_url}{self.repo}/pulls/{pr_number}'
        elif self.before != '0000000000000000000000000000000000000000':
            # There is a valid before SHA to compare with, or this is a release being created.
            diff_url = f'{self.repos_url}{self.repo}/compare/{self.before}...{self.sha}'
        elif len(self.commits) == 1:
            # There is only one commit.
            diff_url = f'{self.repos_url}{self.repo}/commits/{self.sha}'
        elif len(self.commits) > 1:
            # There are several commits: compare with the oldest one.
            oldest = sorted(self.commits, key=self._get_timestamp)[0]['id']
            diff_url = f'{self.repos_url}{self.repo}/compare/{oldest}...{self.sha}'
        else:
            return None

        diff_headers = {
            'Accept': 'application/vnd.github.v3.diff',
            'Authorization': f'token {self.token}',
            'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': 'TODOToIssue/5.1.9'
        }
        diff_request = requests.get(url=diff_url, headers=diff_headers)
        if diff_request.status_code == 200:
            return diff_request.text

        error_response = [f'Could not retrieve diff',
                          f'URL: {diff_url}',
                          f'Status code: {diff_request.status_code}']
        if 'application/json' in diff_request.headers['content-type']:
            error_response.append(f"Server response: {json.loads(diff_request.text)['message']}")
            error_response.append('Operation will abort')

        if '/compare/' in diff_url:
            # The before SHA may no longer be valid due to a force push, fall back to /commits/ endpoint.
            diff_url = f'{self.repos_url}{self.repo}/commits/{self.sha}'
            print(f'Falling back to {diff_url}')
            diff_request = requests.get(url=diff_url, headers=diff_headers)
            if diff_request.status_code == 200:
                return diff_request.text
            error_response.append('Fallback URL also failed')

        raise Exception('\n'.join(error_response))

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
        url_to_line = f'{self.line_base_url}{self.repo}/blob/{self.sha}/{quote(issue.file_name)}{line_num_anchor}'
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

        title = title + '...' if len(title) > self.max_issue_title_length else title
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
            # If title length is long, make sure we're searching using the exact same title as would've been inserted.
            search_title = issue.title + '...' if len(issue.title) > self.max_issue_title_length else issue.title
            for existing_issue in self.existing_issues:
                if existing_issue['title'] == search_title:
                    matched += 1
                    # If there are multiple issues with similar titles, don't try and close any.
                    if matched > 1:
                        print(f'Skipping issue closure due to ambiguous match against multiple existing issues, shown below')
                        for x in self.existing_issues:
                            if x['title'] == search_title:
                                print(f' {x["web_url"]}')
                        issue_number = None
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

    def get_issue_url(self, new_issue_number):
        return f'{self.line_base_url}{self.repo}/issues/{new_issue_number}'
