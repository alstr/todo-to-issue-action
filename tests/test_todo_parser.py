import json
import os
import unittest

from TodoParser import TodoParser


def count_issues_for_file_type(raw_issues, file_type):
    num_issues = 0
    for issue in raw_issues:
        if issue.markdown_language == file_type:
            num_issues += 1
    return num_issues


def get_issues_for_fields(raw_issues, fields):
    matching_issues = []
    for issue in raw_issues:
        for key in fields.keys():
            if getattr(issue, key) != fields.get(key):
                break
        else:
            matching_issues.append(issue)
    return matching_issues


def print_unexpected_issues(unexpected_issues):
    return '\n'.join([
           '',
           'Unexpected issues:',
           '\n=========================\n'.join(map(str, unexpected_issues))])


class NewIssueTest(unittest.TestCase):
    # Check for newly added TODOs across the files specified.
    def setUp(self):
        parser = TodoParser()
        self.raw_issues = []
        with open('syntax.json', 'r') as syntax_json:
            parser.syntax_dict = json.load(syntax_json)
        with open('tests/test_new.diff', 'r') as diff_file:
            self.raw_issues.extend(parser.parse(diff_file))
        with open('tests/test_new2.diff', 'r') as diff_file:
            self.raw_issues.extend(parser.parse(diff_file))
        with open('tests/test_edit.diff', 'r') as diff_file:
            self.raw_issues.extend(parser.parse(diff_file))

    def test_python_issues(self):
        # Includes 4 tests for Starlark.
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'python'), 7)

    def test_yaml_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'yaml'), 2)

    def test_toml_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'toml'), 2)

    def test_php_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'php'), 4)

    def test_java_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'java'), 2)

    def test_javascript_issues(self):
        # Includes 1 test for JSON with Comments.
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'javascript'), 1)

    def test_json5_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'json5'), 1)

    def test_tsx_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'tsx'), 3)

    def test_ruby_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'ruby'), 3)

    def test_crystal_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'crystal'), 2)

    def test_abap_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'abap'), 2)

    def test_sql_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'sql'), 1)

    def test_tex_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'tex'), 2)

    def test_julia_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'julia'), 2)

    def test_starlark_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'python'), 7)

    def test_autohotkey_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'autohotkey'), 1)

    def test_handlebars_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'handlebars'), 2)

    def test_text_issues(self):
        # Includes 2 tests for Org, 2 tests for GAP, 2 tests for Visual Basic, 2 tests for Agda, 4 tests for Sol,
        # 4 tests for Move, 3 tests for AL
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'text'), 19)

    def test_scss_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'scss'), 2)

    def test_twig_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'twig'), 2)

    def test_makefile_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'makefile'), 3)

    def test_md_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'markdown'), 8)

    def test_r_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'r'), 2)

    def test_haskell_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'haskell'), 4)

    def test_clojure_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'clojure'), 2)

    def test_nix_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'nix'), 2)

    def test_xaml_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'xml'), 2)

    def test_c_cpp_like_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'c_cpp'), 2)

    def test_liquid_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'liquid'), 3)

    def test_lua_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'lua'), 2)

    def test_dockerfile_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'dockerfile'), 1)

    def test_powershell_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'powershell'), 3)


class CustomOptionsTest(unittest.TestCase):
    def setUp(self):
        parser = TodoParser(options={"identifiers":
                                     [{"name": "FIX", "labels": []},
                                      {"name": "[TODO]", "labels": []},
                                      {"name": "TODO", "labels": []}
                                      ]})
        self.raw_issues = []
        with open('syntax.json', 'r') as syntax_json:
            parser.syntax_dict = json.load(syntax_json)
        with open('tests/test_new.diff', 'r') as diff_file:
            self.raw_issues.extend(parser.parse(diff_file))

    def test_exact_identifier_match(self):
        """
        Verify that issues are only created when there's an exact identifier match

        Other than case-insensitivity, an issue should only be matched if the
        identifier is exactly within the list of identifiers. For instances, if
        "FIX" is an identifier, it should NOT accidentally match comments with
        the words "suffix" or "prefix".
        """
        matching_issues = get_issues_for_fields(self.raw_issues,
                                                {
                                                    "file_name": "example_file.py",
                                                    "identifier": "FIX"
                                                })
        self.assertEqual(len(matching_issues), 0,
                         msg=print_unexpected_issues(matching_issues))

    # See GitHub issue #242
    def test_regex_identifier_chars(self):
        """
        Verify that the presence of regex characters in the identifier
        doesn't confuse the parser

        An identifier such as "[TODO]" should be matched literally, not treating
        the "[" and "]" characters as part of a regular expression pattern.
        """
        matching_issues = get_issues_for_fields(self.raw_issues,
                                                {
                                                    "file_name": "example_file.py",
                                                    "identifier": "[TODO]"
                                                })
        self.assertEqual(len(matching_issues), 1,
                         msg=print_unexpected_issues(matching_issues))

    # See GitHub issue #235
    @unittest.expectedFailure
    def test_multiple_identifiers(self):
        """
        Verify that issues by matching the first identifier on the line

        Issues should be identified such that the priority is where the identifier
        is found within the comment line, which is not necessarily the order they're
        specified in the identifier dictionary. For instance, if the dictionary is
            [{"name": "FIX", "labels": []},
             {"name": "TODO", "labels": []}]})
        then a comment line such as
            # TODO: Fix this
        should match because of the "TODO", not because of the "Fix". This is not
        a trivial difference. If it matches for the "TODO", then the title will be
        "Fix this", but if it matches for the "Fix", then the title will erroneously
        be just "this".
        """
        matching_issues = get_issues_for_fields(self.raw_issues,
                                                {
                                                    "file_name": "init.lua",
                                                    "identifier": "FIX"
                                                })
        self.assertEqual(len(matching_issues), 0,
                         msg=print_unexpected_issues(matching_issues))

        matching_issues = get_issues_for_fields(self.raw_issues,
                                                {
                                                    "file_name": "init.lua",
                                                    "identifier": "TODO"
                                                })
        self.assertEqual(len(matching_issues), 2,
                         msg=print_unexpected_issues(matching_issues))


class ClosedIssueTest(unittest.TestCase):
    # Check for removed TODOs across the files specified.
    def setUp(self):
        diff_file = open('tests/test_closed.diff', 'r')
        parser = TodoParser()
        with open('syntax.json', 'r') as syntax_json:
            parser.syntax_dict = json.load(syntax_json)
        self.raw_issues = parser.parse(diff_file)

    def test_python_issues(self):
        # Includes 1 test for Starlark.
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'python'), 5)

    def test_yaml_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'yaml'), 2)

    def test_toml_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'toml'), 2)

    def test_php_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'php'), 4)

    def test_java_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'java'), 2)

    def test_ruby_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'ruby'), 3)

    def test_crystal_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'crystal'), 2)

    def test_abap_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'abap'), 2)

    def test_sql_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'sql'), 1)

    def test_tex_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'tex'), 2)

    def test_julia_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'julia'), 4)

    def test_starlark_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'python'), 5)

    def test_javascript_issues(self):
        # Includes 1 test for JSON with Comments.
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'javascript'), 1)

    def test_json5_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'json5'), 1)

    def test_tsx_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'tsx'), 3)

    def test_autohotkey_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'autohotkey'), 1)

    def test_handlebars_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'handlebars'), 2)

    def test_text_issues(self):
        # Includes 2 tests for Org, 2 tests for GAP, 2 tests for Visual Basic, 2 tests for Agda, 4 tests for Sol,
        # 4 tests for Move, 3 tests for AL
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'text'), 19)

    def test_scss_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'scss'), 2)

    def test_twig_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'twig'), 2)

    def test_makefile_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'makefile'), 3)

    def test_md_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'markdown'), 8)

    def test_r_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'r'), 2)

    def test_haskell_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'haskell'), 4)

    def test_clojure_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'clojure'), 2)

    def test_nix_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'nix'), 2)

    def test_xaml_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'xml'), 2)

    def test_c_cpp_like_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'c_cpp'), 2)

    def test_liquid_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'liquid'), 3)

    def test_lua_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'lua'), 2)

    def test_dockerfile_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'dockerfile'), 1)

    def test_powershell_issues(self):
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'powershell'), 3)


class IgnorePatternTest(unittest.TestCase):
    def test_single_ignore(self):
        os.environ['INPUT_IGNORE'] = '.*\\.java'
        parser = TodoParser()
        with open('syntax.json', 'r') as syntax_json:
            parser.syntax_dict = json.load(syntax_json)
        diff_file = open('tests/test_closed.diff', 'r')
        self.raw_issues = parser.parse(diff_file)
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'python'), 5)
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'yaml'), 2)
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'php'), 4)
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'java'), 0)
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'ruby'), 3)
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'crystal'), 2)
        os.environ['INPUT_IGNORE'] = ''

    def test_multiple_ignores(self):
        os.environ['INPUT_IGNORE'] = '.*\\.java, tests/example-file\\.php'
        parser = TodoParser()
        with open('syntax.json', 'r') as syntax_json:
            parser.syntax_dict = json.load(syntax_json)
        diff_file = open('tests/test_closed.diff', 'r')
        self.raw_issues = parser.parse(diff_file)
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'python'), 5)
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'yaml'), 2)
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'php'), 0)
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'java'), 0)
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'ruby'), 3)
        self.assertEqual(count_issues_for_file_type(self.raw_issues, 'crystal'), 2)
        os.environ['INPUT_IGNORE'] = ''


class EscapeMarkdownTest(unittest.TestCase):
    def test_simple_escape(self):
        os.environ['INPUT_ESCAPE'] = 'true'
        parser = TodoParser()
        with open('syntax.json', 'r') as syntax_json:
            parser.syntax_dict = json.load(syntax_json)
        diff_file = open('tests/test_escape.diff', 'r')

        # I had no other idea to make these checks dynamic.
        self.raw_issues = parser.parse(diff_file)
        self.assertEqual(len(self.raw_issues), 2)

        issue = self.raw_issues[0]
        self.assertEqual(len(issue.body), 2)
        self.assertEqual(issue.body[0], '\\# Some title')
        self.assertEqual(issue.body[1], '\\<SomeTag\\>')

        issue = self.raw_issues[1]
        self.assertEqual(len(issue.body), 2)
        self.assertEqual(issue.body[0], '\\# Another title')
        self.assertEqual(issue.body[1], '\\<AnotherTag\\>')


class BaseCustomLanguageTests:
    class BaseTest(unittest.TestCase):
        @staticmethod
        def count_syntax(parser: TodoParser, name: str):
            counter = 0

            for syntax in parser.syntax_dict:
                if syntax['language'] == name:
                    counter = counter + 1

            return counter


class CustomLanguageFileTest(BaseCustomLanguageTests.BaseTest):
    def setUp(self):
        os.environ['INPUT_LANGUAGES'] = 'tests/custom_languages.json'
        self.parser = TodoParser()

    def test_custom_lang_load(self):
        # Test if the custom language ILS is actually loaded into the system
        self.assertIsNotNone(self.parser.languages_dict['ILS'])
        self.assertEqual(self.count_syntax(self.parser, 'ILS'), 1)

    def test_custom_lang_not_duplicate(self):

        # Test if a custom language can overwrite the rules of an existing one
        self.assertEqual(self.count_syntax(self.parser, 'Java'), 1)
        for syntax in self.parser.syntax_dict:
            if syntax['language'] == 'Java':
                self.assertEqual(len(syntax['markers']), 2)
                self.assertEqual(syntax['markers'][0]['pattern'], "////")
                self.assertEqual(syntax['markers'][1]['pattern']['start'], '+=')
                self.assertEqual(syntax['markers'][1]['pattern']['end'], '=+')
                break

        self.assertIsNotNone(self.parser.languages_dict['Java'])
        self.assertEqual(len(self.parser.languages_dict['Java']['extensions']), 1)
        self.assertEqual(self.parser.languages_dict['Java']['extensions'][0], ".java2")

    def tearDown(self):
        del os.environ['INPUT_LANGUAGES']


class CustomLanguageUrlTest(BaseCustomLanguageTests.BaseTest):
    def setUp(self):
        os.environ['INPUT_LANGUAGES'] = ('https://raw.githubusercontent.com/alstr/'
                                         'todo-to-issue-action/master/tests/custom_languages.json')
        os.environ['INPUT_NO_STANDARD'] = 'true'
        self.parser = TodoParser()

    def test_url_load(self):
        self.assertEqual(len(self.parser.languages_dict), 2)
        self.assertEqual(len(self.parser.syntax_dict), 2)

    def tearDown(self):
        del os.environ['INPUT_LANGUAGES']
        del os.environ['INPUT_NO_STANDARD']
