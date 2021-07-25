# TODO to Issue Action

This action will convert newly committed TODO comments to GitHub issues on push. It will also optionally close the issues if the TODOs are removed in a future commit. Works with almost any programming language.

## Usage

Simply add a comment starting with TODO, followed by a colon and/or space. Here's an example for Python:

```python
    def hello_world():
        # TODO Come up with a more imaginative greeting
        print('Hello world!')
```

Multiline TODOs are supported, and a range of options can be provided to apply to the new issue:

```python
    def hello_world():
        # TODO Come up with a more imaginative greeting
        #  Everyone uses hello world and it's boring.
        #  labels: enhancement, help wanted
        #  assignees: alstr, bouteillerAlan, hbjydev
        #  milestone: 1
        print('Hello world!')
```

## Setup

Create a `workflow.yml` file in your `.github/workflows` directory like:

```yml
    name: "Workflow"
    on: ["push"]
    jobs:
      build:
        runs-on: "ubuntu-latest"
        steps:
          - uses: "actions/checkout@master"
          - name: "TODO to Issue"
            uses: "alstr/todo-to-issue-action@v4.0.7"
            id: "todo"
            with:
              TOKEN: ${{ secrets.GITHUB_TOKEN }} // defaults to ${{ github.token }}
```

See [Github's workflow syntax](https://help.github.com/en/actions/reference/workflow-syntax-for-github-actions) for further details on this file.

The workflow file takes the following inputs:

| Input    | Required | Description |
|----------|----------|-------------|
| `TOKEN` | No | The GitHub access token to allow us to retrieve, create and update issues for your repo. Default: `${{ github.token }}` |
| `CLOSE_ISSUES` | No | Optional boolean input that specifies whether to attempt to close an issue when a TODO is removed. Default: `true`. |
| `AUTO_P` | No | Optional boolean input that specifies whether to format each line in multiline TODOs as a new paragraph. Default: `true`. |

There are additional inputs if you want to be able to assign issues to projects. Consult the relevant section below for more details.

### Considerations

* TODOs are found by analysing the difference between the new commit and its previous one (i.e., the diff). That means that if this action is implemented during development, any existing TODOs will not be detected. For them to be detected, you would have to remove them, commit, put them back, and commit again.
* Similarly, if you use the action in a new repo and have TODOs in your first commit, you should initialise the repo with an empty commit beforehand for them to be identified. That is because no diff is available for the first commit.
* Should you change the TODO text, this will currently create a new issue.
* Closing TODOs is still somewhat experimental.

## Supported Languages

* AutoHotkey
* C
* C++
* C#
* CSS
* Dart
* Elixir
* Handlebars
* HTML
* Java
* JavaScript
* Julia
* Kotlin
* Less
* Markdown
* Objective-C
* Org Mode
* PHP
* Python
* Ruby
* Sass
* Scala
* Shell
* Swift
* TeX
* TSX
* TypeScript
* YAML

New languages can easily be added to the `syntax.json` file used by the action to identify TODO comments. When adding languages, follow the structure of existing entries, and use the language name defined by GitHub in [`languages.yml`](https://raw.githubusercontent.com/github/linguist/master/lib/linguist/languages.yml). PRs adding new languages are welcome and appreciated.

## TODO Options

Unless specified otherwise, options should be on their own line, below the initial TODO declaration.

### `assignees:`

Comma-separated list of usernames to assign to the issue.

### `labels:`

Comma-separated list of labels to add to the issue. If any of the labels do not already exist, they will be created. The `todo` label is automatically added to issues to help the action efficiently retrieve them in the future.

### `milestone:`

Milestone ID to assign to the issue. Only a single milestone can be specified and this must already have been created.

### Other Options

#### Identifier

As per the [Google Style Guide](https://google.github.io/styleguide/cppguide.html#TODO_Comments), you can provide an identifier after the TODO label. This will be included in the issue title for searchability.

```python
    def hello_world():
        # TODO(alstr) Come up with a more imaginative greeting
        print('Hello world!')
```

Don't include parentheses within the identifier itself.

#### Projects

You can assign the created issue to columns within user or organisation projects with some additional setup.

The action cannot access your projects by default. To enable access, you must [create an encrypted secret in your repo settings](https://docs.github.com/en/actions/reference/encrypted-secrets#creating-encrypted-secrets-for-a-repository), with the value set to a valid Personal Access Token. Then, assign the secret in the workflow file like `PROJECTS_SECRET: ${{ secrets.PROJECTS_SECRET }}`. Do not enter the raw secret.

To assign to a user project, use the `user projects:` prefix. To assign to an organisation project, use `org projects:` prefix.

The syntax is `<user or org name>/project name/column name`. All three must be provided.

```python
    def hello_world():
        # TODO Come up with a more imaginative greeting
        #  Everyone uses hello world and it's boring.
        #  user projects: alstr/Test User Project/To Do
        #  org projects: alstrorg/Test Org Project/To Do
        print('Hello world!')
```

You can assign to multiple projects by using commas, for example: `user projects: alstr/Test User Project 1/To Do, alstr/Test User Project 2/Tasks`.

You can also specify default projects in the same way by defining `USER_PROJECTS` or `ORG_PROJECTS` in your workflow file. These will be applied automatically to every issue, but will be overrode by any specified within the TODO.

## Troubleshooting

### No issues have been created

Make sure your file language is in `syntax.json`. Also, the action will not recognise TODOs in the first commit to a new repo, or existing TODOs that have already been committed.

### Multiple issues have been created

Issues are created whenever the action runs and finds a newly added TODO in the diff. Rebasing may cause a TODO to show up in a diff multiple times. This is an acknowledged issue, but you may have some luck by adjusting your workflow file.

## Contributing & Issues

If you do encounter any problems, please file an issue or submit a PR. Everyone is welcome and encouraged to contribute.

## Thanks

The action was developed for the GitHub Hackathon. Whilst every effort is made to ensure it works, it comes with no guarantee.

Thanks to Jacob Tomlinson for [his handy overview of GitHub Actions](https://www.jacobtomlinson.co.uk/posts/2019/creating-github-actions-in-python/).

Thanks to GitHub's [linguist repo](https://github.com/github/linguist/) for the [`languages.yml`](https://raw.githubusercontent.com/github/linguist/master/lib/linguist/languages.yml) file used by the app to look up file extensions and determine the correct highlighting to apply to code snippets.
