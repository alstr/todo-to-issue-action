import os
import re
from ruamel.yaml import YAML
from LineStatus import LineStatus
from Issue import Issue
import requests
import json
from urllib.parse import urlparse

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
                        with open(path) as f:
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
            # Check if the file extension matches the language's extensions.
            if extension != '' and 'extensions' in self.languages_dict[language_name]:
                syntax_details, ace_mode = self._get_language_details(language_name, 'extensions', extension)
                if syntax_details is not None and ace_mode is not None:
                    return syntax_details, ace_mode
            # Check if the file name matches the language's filenames.
            if 'filenames' in self.languages_dict[language_name]:
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

