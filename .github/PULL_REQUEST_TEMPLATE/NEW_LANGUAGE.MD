# New Language Definition Contribution

Thank you for contributing a new language definition! Please follow the guidelines below to ensure that your contribution can be easily reviewed and integrated into the project.

## Description

**Language Name**: (e.g., Python, JavaScript)

Fixes # (issue number, if applicable)

## Checklist for Adding a New Language

Before submitting your pull request, please ensure the following requirements are met:

- [ ] I have added the language to `syntax.json` with the language name matching that in GitHub's [Linguist `languages.yml` file](https://github.com/github-linguist/linguist/blob/main/lib/linguist/languages.yml).
- [ ] I have added sample code to `test_new.diff` and `test_closed.diff`.
- [ ] I have added issue creation and closure tests to `test_todo_parser.py`. The tests should check that the `ace_mode` of the issue matches that specified in the `languages.yml` file. If existing checks for that `ace_mode` exists, I have incremented them instead.
- [ ] I have updated `README.md` to add the language.
- [ ] I have run and verified all tests.

## Thank You

We appreciate your time and effort in improving this project!
