# TODO to Issue Action

This action will convert your `# TODO` comments to GitHub issues when a new commit is pushed.

The new issue will contain a link to the line in the file containing the TODO, together with a code snippet and any defined labels. The action performs a `GET` request to retrieve GitHub's [`languages.yml` file](https://raw.githubusercontent.com/github/linguist/master/lib/linguist/languages.yml) file to apply highlighting to the snippet.

It will also close an issue when a `# TODO` is removed in a pushed commit. A comment will be posted
with the ref of the commit that it was closed by.

The `# TODO` comment is commonly used in Python, but this can be customised to whatever you want.

## Summary
- [Usage](#usage)
    - [workflow.yaml](#workflowyaml)
    - [Inputs](#inputs)
- [Examples](#examples)
    - [Adding TODOs](#adding-todos)
    - [Multiline TODOs](#multiline-todos)
    - [Specifying Identifier](#specifying-identifier)
    - [Specifying Labels](#specifying-labels)
    - [Specifying Assignees](#specifying-assignees)
    - [Specifying Milestone](#specifying-milestone)
    - [Removing TODOs](#removing-todos)
    - [Updating TODOs](#updating-todos)
    - [Existing TODOs](#existing-todos)
- [Contributing & Issues](#contributing--issues)
- [Thanks](#thanks)

## Usage

Create a workflow file in your .github/workflows directory as follows:

### workflow.yaml

Latest version is `v2.4`.

    name: "Workflow"
    on: ["push"]
    jobs:
      build:
        runs-on: "ubuntu-latest"
        steps:
          - uses: "actions/checkout@master"
          - name: "TODO to Issue"
            uses: "alstr/todo-to-issue-action@v2.4"
            id: "todo"
            with:
              TOKEN: ${{ secrets.GITHUB_TOKEN }}

**If you use the action in a new repo, you should initialise the repo with an empty commit.**

### Inputs

| Input    | Default value | Description |
|----------|---------------|-------------|
| `REPO` | `"${{ github.repository }}"` | The path to the repository where the action will be used, e.g. 'alstr/my-repo' (automatically set) |
| `BEFORE` | `"${{ github.event.before }}"` | The SHA of the last pushed commit (automatically set) |
| `SHA` | `"${{ github.sha }}"` | The SHA of the latest commit (automatically set) |
| `TOKEN` | `"${{ secrets.GITHUB_TOKEN }}"` | The GitHub access token to allow us to retrieve, create and update issues (automatically set) |
| `LABEL` | `"# TODO"` | The label that will be used to identify TODO comments |
| `COMMENT_MARKER` | `"#"` | The marker used to signify a line comment in your code |
| `CLOSE_ISSUES` | `true` | Optional input that specifies whether to attempt to close an issue when a TODO is removed |
| `AUTO_P` | `true` | For multiline TODOs, format each line as a new paragraph when creating the issue |

## Examples

### Adding TODOs

    def hello_world():
        # TODO Come up with a more imaginative greeting
        print('Hello world!')
        
This will create an issue called "Come up with a more imaginative greeting".
 
**The action expects a colon and/or space to follow the `TODO` label (so `TODO: ` or just `TODO`).**
 
Should the title be longer than 80 characters, it will be truncated for the issue title.
 
The full title will be included in the issue body and a `todo` label will be attached to the issue.

A reference hash is added to the end of the issue body. This is to help prevent duplication of TODOs.

### Multiline TODOs

    def hello_world():
        # TODO Come up with a more imaginative greeting
        #  Everyone uses hello world and it's boring.
        print('Hello world!')

You can create a multiline todo by continuing below the initial TODO declaration with a comment.

The extra line(s) will be posted in the body of the issue.

The `COMMENT_MARKER` input must be set to the correct syntax (e.g. `#` for Python).

Each line in the multiline TODO will be formatted as a paragraph in the issue body. To disable this, set `AUTO_P` to `false`.

### Specifying Identifier

    def hello_world():
        # TODO(alstr) Come up with a more imaginative greeting

As per the [Google Style Guide](https://google.github.io/styleguide/cppguide.html#TODO_Comments), you can provide an identifier after the TODO label. This will be included in the issue title for searchability.

Don't include parentheses within the identifier itself.

### Specifying Labels

    def hello_world():
        # TODO Come up with a more imaginative greeting
        #  Everyone uses hello world and it's boring.
        #  labels: enhancement, help wanted
        print('Hello world!')

You can specify the labels to add to your issue in the TODO body.

The labels should be on their own line below the initial TODO declaration.

Include the `labels:` prefix, then a list of comma-separated label titles. If any of the labels do not already exist, they will be created.

The `todo` label is automatically added to issues to help the action efficiently retrieve them in the future.

### Specifying Assignees

    def hello_world():
        # TODO Come up with a more imaginative greeting
        #  Everyone uses hello world and it's boring.
        #  assignees: alstr, bouteillerAlan, hbjydev
        print('Hello world!')

Similar to labels, you can define assignees as a comma-separated list.

If the assignee is not valid, it will be dropped from the issue creation request.

### Specifying Milestone

    def hello_world():
        # TODO Come up with a more imaginative greeting
        #  Everyone uses hello world and it's boring.
        #  milestone: 1
        print('Hello world!')

You can set the issue milestone by specifying the milestone ID. Only a single milestone can be specified.

If the milestone does not already exist, it will be dropped from the issue creation request.

### Removing TODOs

    def hello_world():
        print('Hello world!')

Removing the `# TODO` comment will close the issue on push.

This is still an experimental feature. By default it is enabled, but if you want to disable it, you can set `CLOSE_ISSUES` to `false` as described in [Inputs](#inputs).

### Updating TODOs

    def hello_world():
        # TODO Come up with a more imaginative greeting, like "Greetings world!"
        print('Hello world!')
        
Should you change the `# TODO` text, this will currently create a new issue, so bear that in mind.

This may be updated in future.

### Existing TODOs

> This action will convert your `# TODO` comments to GitHub issues when a new commit is pushed.

As the TODOs are found by analysing the difference between the new commit and the previous one, this means that if this action is implemented during development any existing TODOs will not be detected. For them to be detected, you would have to remove them, commit, put them back and commit again.

## Contributing & Issues

The action was developed for the GitHub Hackathon and is still in an early stage. Whilst every effort is made to ensure it works, it comes with no guarantee.

It may not yet work for [ events ](https://help.github.com/en/actions/reference/events-that-trigger-workflows) other than `push` or those with a complex [ workflow syntax ](https://help.github.com/en/actions/reference/workflow-syntax-for-github-actions).

If you do encounter any problems, please file an issue. PRs are welcome and appreciated!

## Thanks

Thanks to Jacob Tomlinson for [his handy overview of GitHub Actions](https://www.jacobtomlinson.co.uk/posts/2019/creating-github-actions-in-python/).

Thanks to GitHub's [linguist repo](https://github.com/github/linguist/) for the [ `languages.yml` ](
https://raw.githubusercontent.com/github/linguist/master/lib/linguist/languages.yml) file used by the app to determine the correct highlighting to apply to code snippets.
