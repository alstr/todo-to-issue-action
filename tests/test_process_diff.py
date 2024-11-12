import json
import os
import unittest
import tempfile
import subprocess
import io
import re

from TodoParser import TodoParser
from main import process_diff


class IssueUrlInsertionTest(unittest.TestCase):
    _original_addSubTest = None
    num_subtest_failures = 0
    orig_cwd = None
    tempdir = None
    diff_file = None
    parser = None

    def _setUp(self, diff_files):
        # reset counter
        self.num_subtest_failures = 0

        # get current working directory
        self.orig_cwd = os.getcwd()

        # Create temporary directory to hold simulated filesystem.
        self.tempdir = tempfile.TemporaryDirectory()

        for diff_file in diff_files:
            # run patch against the diff file to generate/update the simulated filesystem
            subprocess.run(['patch', '-d', self.tempdir.name,
                            '-i', f'{os.getcwd()}/tests/{diff_file}'],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            check=True)

        self.diff_file = open(f'tests/{diff_files[-1]}', 'r')
        self.parser = TodoParser()
        with open('syntax.json', 'r') as syntax_json:
            self.parser.syntax_dict = json.load(syntax_json)

        # change to the simulated filesystem directory
        os.chdir(self.tempdir.name)

    def _standardTest(self, expected_count, output_log_on_failure=True):
        # create object to hold output
        output = io.StringIO()
        # process the diffs
        self.raw_issues = process_diff(diff=self.diff_file, insert_issue_urls=True, parser=self.parser, output=output)
        # store the log for later processing
        self.output_log = output.getvalue()
        # make sure the number of issue URL comments inserted is as expected
        self.assertEqual(output.getvalue().count('Issue URL successfully inserted'),
                         expected_count,
                         msg=(
                             '\nProcessing log\n--------------\n'+output.getvalue()
                                if output_log_on_failure else None))

    def _addSubTest(self, test, subtest, outcome):
        if outcome:
            self.num_subtest_failures+=1
        if self._original_addSubTest:
            self._original_addSubTest(test, subtest, outcome)

    def run(self, result=None):
        if result and getattr(result, "addSubTest", None):
            self._original_addSubTest = result.addSubTest
            result.addSubTest = self._addSubTest

        super().run(result)

    # this test can take a while and, as far as TodoParser is concerned,
    # redundant with the tests of test_todo_parser, so enable the means
    # to skip it if desired
    @unittest.skipIf(os.getenv('SKIP_PROCESS_DIFF_TEST', 'false') == 'true',
                     "Skipping because 'SKIP_PROCESS_DIFF_TEST' is 'true'")
    def test_url_insertion(self):
        self._setUp(['test_new.diff'])
        self._standardTest(79)

    def test_line_numbering_with_deletions(self):
        self._setUp(['test_new_py.diff', 'test_edit_py.diff'])
        with self.subTest("Issue URL insertion"):
            # was issue URL successfully inserted?
            self._standardTest(1, False)
        with self.subTest("Issue insertion line numbering"):
            # make sure the log reports having inserted the issue based on the
            # correct line numbering of the updated file
            self.assertIn("Processing issue 1 of 2: 'Do more stuff' @ example_file.py:7",
                          self.output_log)
        with self.subTest("Issue deletion line numbering"):
            # make sure the log reports having closed the issue based on the
            # correct line numbering of the old (not the updated!) file
            self.assertIn("Processing issue 2 of 2: 'Come up with a more imaginative greeting' @ example_file.py:2",
                          self.output_log)

        if self.num_subtest_failures > 0:
            self.fail(
                '\n'.join([
                '',
                'One or more subtests have failed',
                'Processing log',
                '--------------',
                ''])+
                self.output_log)

    def test_same_title_in_same_file(self):
        self._setUp(['test_same_title_in_same_file.diff'])
        self._standardTest(5)

    def test_comment_suffix_after_source_line(self):
        self._setUp(['test_comment_suffix_after_source_line.diff'])
        self._standardTest(1)
        # get details about the issue and source file
        issue = self.raw_issues[0]
        markers, _ = self.parser._get_file_details(issue.file_name)
        with open(f'{self.tempdir.name}/{issue.file_name}', 'r') as source_file:
            lines = source_file.read().splitlines()
        # regex search the TODO comment and issue URL lines, such that groups are:
        # 2: everything from start of line up to (but excluding) comment marker
        # 3: comment marker
        # 4: anything after comment marker and before identifier
        # 1: encompasses all of the above
        source_and_todo_line = re.search(fr'^((.*?)({markers[0]["pattern"]})(.*?))(?i:{issue.identifier}).*?{issue.title}',
                                         lines[issue.start_line-1]).groups()
        issue_url_line = re.search(fr'^((.*?)({markers[0]["pattern"]})(\s*))Issue URL: N/A$',
                                   lines[issue.start_line]).groups()
        # ensure Issue URL is aligned with the TODO above it by verifying
        # that length of first group is equal for both lines
        self.assertEqual(len(source_and_todo_line[0]), len(issue_url_line[0]), msg='\n'
                         + f'Issue URL mis-alignment. {issue.identifier} begins at column '
                         + f'{len(source_and_todo_line[0])+1} but\nissue URL begins at column '
                         + f'{len(issue_url_line[0])+1}.\n'
                         + '-------------------------------------------------------------------\n'
                         + f'{lines[issue.start_line-1]}\n'
                         + f'{lines[issue.start_line]}\n')
        # ensure Issue URL line has only whitespace before the comment marker
        self.assertRegex(issue_url_line[1], r'^\s*$', msg='\n'
                         + 'Non-whitespace detected prior to comment marker for issue URL line!\n'
                         + '-------------------------------------------------------------------\n'
                         + f'{lines[issue.start_line]}\n')

    def tearDown(self):
        # return to original working directory to ensure we don't mess up other tests
        os.chdir(self.orig_cwd)

        # explicitly cleanup to avoid warning being printed about implicit cleanup
        self.tempdir.cleanup()
        self.tempdir = None
