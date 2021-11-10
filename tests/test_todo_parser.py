import os
import unittest
from main import TodoParser


def count_issues_for_file_type(raw_issues, file_type):
    num_issues = 0
    for issue in raw_issues:
        if issue.markdown_language == file_type:
            num_issues += 1
    return num_issues


class NewIssueTests(unittest.TestCase):
    # Check for newly added TODOs across the files specified.
    def setUp(self):
        diff_file = open('tests/test_new.diff', 'r')
        self.raw_issues = TodoParser().parse(diff_file)

    def test_python_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'python'), 2)

    def test_yaml_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'yaml'), 2)

    def test_php_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'php'), 4)

    def test_java_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'java'), 2)

    def test_ruby_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'ruby'), 3)

    def test_abap_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'abap'), 2)

    def test_sql_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'sql'), 1)

    # TODO: Update tests
    #  Need tests for Julia, AutoHotKey, Handlebars, Org and TeX, as these markers are not currently covered.


class ClosedIssueTests(unittest.TestCase):
    # Check for removed TODOs across the files specified.
    def setUp(self):
        diff_file = open('tests/test_closed.diff', 'r')
        self.raw_issues = TodoParser().parse(diff_file)

    def test_python_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'python'), 2)

    def test_yaml_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'yaml'), 2)

    def test_php_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'php'), 4)

    def test_java_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'java'), 2)

    def test_ruby_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'ruby'), 3)

    def test_abap_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'abap'), 2)

    def test_sql_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'sql'), 1)


class IgnorePatternTests(unittest.TestCase):

    def test_single_ignore(self):
        os.environ['INPUT_IGNORE'] = '.*\\.java'
        diff_file = open('tests/test_new.diff', 'r')
        self.raw_issues = TodoParser().parse(diff_file)
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'python'), 2)
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'yaml'), 2)
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'php'), 4)
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'java'), 0)
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'ruby'), 3)
        os.environ['INPUT_IGNORE'] = ''

    def test_multiple_ignores(self):
        os.environ['INPUT_IGNORE'] = '.*\\.java, tests/example-file\\.php'
        diff_file = open('tests/test_new.diff', 'r')
        self.raw_issues = TodoParser().parse(diff_file)
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'python'), 2)
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'yaml'), 2)
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'php'), 0)
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'java'), 0)
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'ruby'), 3)
        os.environ['INPUT_IGNORE'] = ''
