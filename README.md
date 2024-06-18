# TODO to Issue Action

This action will convert newly committed TODO comments to GitHub issues on push.

Optionally, issues can also be closed when the TODOs are removed in a future commit.

Action supports:

* Multiple, customizable comments identifiers (FIXME, etc.),
* Configurable auto-labeling,
* Assignees,
* Milestones,
* Projects (classic).

`todo-to-issue` works with almost any programming language.

## Usage

Simply add a comment starting with TODO (or any other comment identifiers configured), followed by a colon and/or space.

Here's an example for Python creating an issue named after the TODO _description_:

```python
    def hello_world():
    # TODO Come up with a more imaginative greeting
    print('Hello world!')
```

_Multiline_ TODOs are supported, with additional lines inserted into the issue body:

```python
    def hello_world():
    # TODO: Come up with a more imaginative greeting
    #  Everyone uses hello world and it's boring.
    print('Hello world!')
```

As per the [Google Style Guide](https://google.github.io/styleguide/cppguide.html#TODO_Comments), you can provide a
_reference_ after the TODO identifier. This will be included in the issue title for searchability.

```python
    def hello_world():
    # TODO(alstr) Come up with a more imaginative greeting
    #  Everyone uses hello world and it's boring.
    print('Hello world!')
```

Don't include parentheses within the reference itself.

## TODO Options

A range of options can also be provided to apply to the new issue.

Options follow the `name: value` syntax.
Unless otherwise specified, options should be on their own line, below the initial TODO declaration and 'body'.

### Assignees

Comma-separated list of usernames to assign to the issue:

```python
    def hello_world():
    # TODO(alstr): Come up with a more imaginative greeting
    #  Everyone uses hello world and it's boring.
    #  assignees: alstr, bouteillerAlan, hbjydev
    print('Hello world!')
```

### Labels

Comma-separated list of labels to add to the issue:

```python
    def hello_world():
    # TODO(alstr): Come up with a more imaginative greeting
    #  Everyone uses hello world and it's boring.
    #  labels: enhancement, help wanted
    print('Hello world!')
```

If any of the labels do not already exist, they will be created.

The `todo` label is automatically added to issues to help the action efficiently retrieve them in the future.

### Milestone

Milestone `ID` to assign to the issue:

```python
    def hello_world():
    # TODO(alstr): Come up with a more imaginative greeting
    #  Everyone uses hello world and it's boring.
    #  milestone: 1
    print('Hello world!')
```

Only a single milestone can be specified and it must already exist.

### Projects

_Please note, the action currently only supports classic user and organisation projects, and not 'new' projects._

With some additional setup, you can assign the created issues a status (column) within user or organisation projects.

By default, the action cannot access your projects. To enable it, you must:

* [Create a Personal Access Token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token),
* [Create an encrypted secret in your repo settings](https://docs.github.com/en/actions/reference/encrypted-secrets#creating-encrypted-secrets-for-a-repository),
  with the value set to the Personal Access Token,
* Assign the secret in the workflow file like `PROJECTS_SECRET: ${{ secrets.PROJECTS_SECRET }}`. _Do not enter the raw
  secret_.

Projects are identified by their `full project name and issue status` (column) reference with
the `<user or org name>/project name/status name` syntax.

* To assign to a _user project_, use the `user projects:` option.
* To assign to an _organisation project_, use `org projects:` option.

```python
    def hello_world():
    # TODO Come up with a more imaginative greeting
    #  Everyone uses hello world and it's boring.
    #  user projects: alstr/Test User Project/To Do
    #  org projects: alstrorg/Test Org Project/To Do
    print('Hello world!')
```

You can assign issues to multiple projects separating them with commas,
i.e. `user projects: alstr/Test User Project 1/To Do, alstr/Test User Project 2/Tasks`.

You can also specify `default projects` in the same way by defining `USER_PROJECTS` or `ORG_PROJECTS` in your workflow
file.
These will be applied automatically to every issue, but will be overrode by any specified within the TODO.

## Supported Languages

- ABAP
- ABAP CDS
- AutoHotkey
- C
- C++
- C#
- CSS
- Crystal
- Clojure
- Cuda
- Dart
- Elixir
- GDScript
- Go
- Handlebars
- HCL
- Haskell
- HTML
- Java
- JavaScript
- JSON5
- JSON with Comments
- Julia
- Kotlin
- Less
- Liquid
- Makefile
- Markdown
- Nix
- Objective-C
- Org Mode
- PHP
- Python
- R
- Razor
- RMarkdown
- Ruby
- Rust
- Sass
- Scala
- SCSS
- Shell
- SQL
- Starlark
- Swift
- TeX
- TSX
- Twig
- TypeScript
- Vue
- XML
- YAML

New languages can easily be added to the `syntax.json` file, used by the action to identify TODO comments.

When adding languages, follow the structure of existing entries, and use the language name defined by GitHub
in [`languages.yml`](https://raw.githubusercontent.com/github/linguist/master/lib/linguist/languages.yml).

Of course, PRs adding new languages are welcome and appreciated. Please add a test for your language in order for your
PR to be accepted. See [Contributing](#contributing--issues).

## Setup

On your repo go to `Settings -> Actions (General) -> Workflow permissions` and enable "Read and write permissions".

Create a `workflow.yml` file in your `.github/workflows` directory like:

```yml
name: "Run TODO to Issue"
on: [ "push" ]
jobs:
  build:
    runs-on: "ubuntu-latest"
    steps:
      - uses: "actions/checkout@v3"
      - name: "TODO to Issue"
        uses: "alstr/todo-to-issue-action@v4"
```

See [Github's workflow syntax](https://help.github.com/en/actions/reference/workflow-syntax-for-github-actions) for
further details on this file.

The workflow file takes the following optional inputs:

| Parameter       | Required | Description                                                                                                                        |
|-----------------|----------|------------------------------------------------------------------------------------------------------------------------------------|
| REPO            | False    | The path to the repository where the action will be used, e.g., 'alstr/my-repo' (automatically set)                                |
| BEFORE          | False    | The SHA of the last pushed commit (automatically set)                                                                              |
| COMMITS         | False    | An array of commit objects describing the pushed commits                                                                           |
| DIFF_URL        | False    | The URL to use to get the diff (automatically set)                                                                                 |
| SHA             | False    | The SHA of the latest commit (automatically set)                                                                                   |
| TOKEN           | False    | The GitHub access token to allow us to retrieve, create and update issues (automatically set)                                      |
| LABEL           | False    | The label that will be used to identify TODO comments (deprecated)                                                                 |
| COMMENT_MARKER  | False    | The marker used to signify a line comment in your code (deprecated)                                                                |
| CLOSE_ISSUES    | False    | Optional input that specifies whether to attempt to close an issue when a TODO is removed                                          |
| AUTO_P          | False    | For multiline TODOs, format each line as a new paragraph when creating the issue                                                   |
| PROJECTS_SECRET | False    | Encrypted secret corresponding to your personal access token (do not enter the actual secret)                                      |
| USER_PROJECTS   | False    | Default user projects                                                                                                              |
| ORG_PROJECTS    | False    | Default organization projects                                                                                                      |
| IGNORE          | False    | A collection of comma-delimited regular expressions that match files that should be ignored when searching for TODOs               |
| AUTO_ASSIGN     | False    | Automatically assign new issues to the user who triggered the action                                                               |
| ACTOR           | False    | The username of the person who triggered the action                                                                                |
| ISSUE_TEMPLATE  | False    | The template used to format new issues                                                                                             |
| IDENTIFIERS     | False    | List of custom identifier dictionaries of the form `[{"name": "TODO", "labels": [todo]}]`                                          |
| GITHUB_URL      | False    | Base URL of GitHub API                                                                                                             |
| ESCAPE          | False    | Escape all special Markdown characters                                                                                             |
| LANGUAGES       | False    | A collection of comma-delimited URLs or local paths starting from the current working directory of the action for custom languages |
| NO_STANDARD     | False    | Exclude loading the default 'syntax.json' and 'language.yml' files from the repository                                             |

These can be specified using `with` parameter in the workflow file, as below:

```yml
name: "Run TODO to Issue"
on: [ "push" ]
jobs:
  build:
    runs-on: "ubuntu-latest"
    steps:
      - uses: "actions/checkout@v3"
      - name: "TODO to Issue"
        uses: "alstr/todo-to-issue-action@v4"
        with:
          AUTO_ASSIGN: true
```

### Considerations

- TODOs are found by analysing the difference between the new commit and its previous one (i.e., the diff). That means
  that if this action is implemented during development, any existing TODOs will not be detected. For them to be
  detected, you would have to remove them, commit, put them back, and commit again,
  or [run the action manually](#running-the-action-manually).
- Should you change the TODO text, this will currently create a new issue.
- Closing TODOs is still somewhat experimental.

## Custom Languages

If you want to add or overwrite language detections that are not currently supported, you can add them manually using the `LANGUAGES` input.

Just create a file that contains an array with languages, each having the following properties:

| Property   | Type     | Description                                                                                                                                        |
|------------|----------|----------------------------------------------------------------------------------------------------------------------------------------------------|
| language   | string   | The unique name of the language                                                                                                                    |
| extensions | string[] | A list of file extensions for the custom language                                                                                                  |
| markers    | object[] | A list of objects (see example below) to declare the comment markers. Make sure to escape all special Markdown characters with a double backslash. |

For example, here is a language declaration file for Java:

```json
[
  {
    "language": "Java",
    "extensions": [
      ".java"
    ],
    "markers": [
      {
        "type": "line",
        "pattern": "//"
      },
      {
        "type": "block",
        "pattern": {
          "start": "/\\*",
          "end": "\\*/"
        }
      }
    ]
  }
]
```
Next, add the file to the `LANGUAGES` property in your workflow YAML file. Please note that if multiple paths are provided, the last path specified will take precedence over any previous ones:

**Using a Local File:**

```yaml
name: "Run TODO to Issue"
on: [ "push" ]
jobs:
  build:
    runs-on: "ubuntu-latest"
    steps:
      - uses: "actions/checkout@v3"
      - name: "TODO to Issue"
        uses: "alstr/todo-to-issue-action@v4"
        with:
          LANGUAGES: "path/to/my/file.json"
```

**Using a File from HTTP(s):**

```yaml
name: "Run TODO to Issue"
on: [ "push" ]
jobs:
  build:
    runs-on: "ubuntu-latest"
    steps:
      - uses: "actions/checkout@v3"
      - name: "TODO to Issue"
        uses: "alstr/todo-to-issue-action@v4"
        with:
          LANGUAGES: "http://myserver.com/path/to/my/file.json"
```

This will configure the action to use your custom language file for detecting TODO comments.

## Running the action manually

There may be circumstances where you want the action to run for a particular commit(s) already pushed.

You can run the action manually by adding support for the `workflow_dispatch` event to your workflow file:

```yaml
name: "Run TODO to Issue"
on:
  push:
  workflow_dispatch:
    inputs:
      MANUAL_COMMIT_REF:
        description: "The SHA of the commit to get the diff for"
        required: true
      MANUAL_BASE_REF:
        description: "By default, the commit entered above is compared to the one directly before it; to go back further, enter an earlier SHA here"
        required: false
jobs:
  build:
    runs-on: "ubuntu-latest"
    steps:
      - uses: "actions/checkout@v3"
      - name: "TODO to Issue"
        uses: "alstr/todo-to-issue-action@master"
        env:
          MANUAL_COMMIT_REF: ${{ inputs.MANUAL_COMMIT_REF }}
          MANUAL_BASE_REF: ${{ inputs.MANUAL_BASE_REF }}
```

Head to the Actions section of your repo, select the workflow and then 'Run workflow'.

You can run the workflow for a single commit by entering the commit SHA in the first box. In this case, the action will
compare the commit to the one directly before it.

You can also compare a broader range of commits. For that, also enter the 'from'/base commit SHA in the second box.

## Troubleshooting

### No issues have been created

- Make sure your file language is in `syntax.json`.
- The action will not recognise existing TODOs that have already been pushed, unless
  you [run the action manually](#running-the-action-manually).
- If a similar TODO appears in the diff as both an addition and deletion, it is assumed to have been moved, so is
  ignored.
- If your workflow is executed but no issue is generated, check your repo permissions by navigating
  to `Settings -> Actions (General) -> Workflow permissions` and enable "Read and write permissions".

### Multiple issues have been created

Issues are created whenever the action runs and finds a newly added TODO in the diff. Rebasing may cause a TODO to show
up in a diff multiple times. This is an acknowledged issue, but you may have some luck by adjusting your workflow file.

## Contributing & Issues

If you do encounter any problems, please file an issue or submit a PR. Everyone is welcome and encouraged to contribute.

**If submitting a request to add a new language, please ensure you add the appropriate tests covering your language. In
the interests of stability, PRs without tests cannot be considered.**

## Running tests locally

To run the tests locally, simply run the following in the main repo:

```shell
python -m unittest
```

## Customising

If you want to fork this action to customise its behaviour, there are a few steps you should take to ensure your changes
run:

- In `workflow.yml`, set `uses: ` to your action.
- In `action.yml`, set `image: ` to `Dockerfile`, rather than the prebuilt image.
- If customising `syntax.json`, you will want to update the URL in `main.py` to target your version of the file.

## Thanks

The action was developed for the GitHub Hackathon. Whilst every effort is made to ensure it works, it comes with no
guarantee.

Thanks to Jacob Tomlinson
for [his handy overview of GitHub Actions](https://www.jacobtomlinson.co.uk/posts/2019/creating-github-actions-in-python/).

Thanks to GitHub's [linguist repo](https://github.com/github/linguist/) for
the [`languages.yml`](https://raw.githubusercontent.com/github/linguist/master/lib/linguist/languages.yml) file used by
the app to look up file extensions and determine the correct highlighting to apply to code snippets.

Thanks to all those who have [contributed](https://github.com/alstr/todo-to-issue-action/graphs/contributors) to the
further development of this action.
