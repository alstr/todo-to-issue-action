import unittest
from main import TodoParser


def count_issues_for_file_type(raw_issues, file_type):
    num_issues = 0
    for issue in raw_issues:
        if issue.markdown_language == file_type:
            num_issues += 1
    return num_issues


class NewIssueTests(unittest.TestCase):
    # Check for newly added TODOs across the files specified (covers all current marker types).
    def setUp(self):
        diff_file = open('tests/test_new.diff', 'r')
        self.raw_issues = TodoParser().parse(diff_file)

    def test_python_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'python'), 2)

    def test_yaml_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'yaml'), 2)

    def test_php_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'php'), 3)

    def test_java_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'java'), 2)

    def test_css_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'css'), 2)

    def test_ruby_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'ruby'), 3)


class ClosedIssueTests(unittest.TestCase):
    # Check for removed TODOs across the files specified (covers all current marker types).
    def setUp(self):
        diff_file = open('tests/test_closed.diff', 'r')
        self.raw_issues = TodoParser().parse(diff_file)

    def test_python_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'python'), 2)

    def test_yaml_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'yaml'), 2)

    def test_php_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'php'), 3)

    def test_java_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'java'), 2)

    def test_css_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'css'), 2)

    def test_ruby_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'ruby'), 3)
