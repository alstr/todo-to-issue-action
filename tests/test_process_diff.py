import json
import os
import unittest
import tempfile
import subprocess
import io

from TodoParser import TodoParser
from main import process_diff


class IssueUrlInsertionTest(unittest.TestCase):
    orig_cwd = None
    tempdir = None
    diff_file = None
    parser = None

    def _setUp(self, diff_file):
        # get current working directory
        self.orig_cwd = os.getcwd()

        # Create temporary directory to hold simulated filesystem.
        self.tempdir = tempfile.TemporaryDirectory()

        # run patch against the diff file to generate the simulated filesystem
        subprocess.run(['patch', '-d', self.tempdir.name,
                        '-i', f'{os.getcwd()}/tests/{diff_file}'],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=True)

        self.diff_file = open(f'tests/{diff_file}', 'r')
        self.parser = TodoParser()
        with open('syntax.json', 'r') as syntax_json:
            self.parser.syntax_dict = json.load(syntax_json)

        # change to the simulated filesystem directory
        os.chdir(self.tempdir.name)

    def _standardTest(self, expected_count):
        # create object to hold output
        output = io.StringIO()
        # process the diffs
        process_diff(diff=self.diff_file, insert_issue_urls=True, parser=self.parser, output=output)
        # make sure the number of issue URL comments inserted is as expected
        self.assertEqual(output.getvalue().count('Issue URL successfully inserted'),
                         expected_count,
                         msg='\nProcessing log\n--------------\n'+output.getvalue())

    # this test can take a while and, as far as TodoParser is concerned,
    # redundant with the tests of test_todo_parser, so enable the means
    # to skip it if desired
    @unittest.skipIf(os.getenv('SKIP_PROCESS_DIFF_TEST', 'false') == 'true',
                     "Skipping because 'SKIP_PROCESS_DIFF_TEST' is 'true'")
    def test_url_insertion(self):
        self._setUp('test_new.diff')
        self._standardTest(80)

    @unittest.expectedFailure
    def test_same_title_in_same_file(self):
        self._setUp('test_same_title_in_same_file.diff')
        self._standardTest(5)

    def tearDown(self):
        # return to original working directory to ensure we don't mess up other tests
        os.chdir(self.orig_cwd)

        # explicitly cleanup to avoid warning being printed about implicit cleanup
        self.tempdir.cleanup()
        self.tempdir = None
