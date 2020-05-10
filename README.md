# TODO to Issue Action

This action will convert your `# TODO` comments to GitHub issues when a new commit is pushed.

The new issue will contain a link to the line in the file containing the TODO, together with a code snippet. The action performs a `GET` request to retrieve GitHub's [`languages.yml` file](https://raw.githubusercontent.com/github/linguist/master/lib/linguist/languages.yml) file to apply highlighting to the snippet.

It will also close an issue when a `# TODO` is removed in a pushed commit. A comment will be posted
with the ref of the commit that it was closed by.

The `# TODO` comment is commonly used in Python, but this can be customised to whatever you want.

## Usage

Create a workflow file in your .github/workflows directory as follows:

### workflow.yaml

Latest version is `v1.1.1-beta`.

    name: "Workflow"
    on: ["push"]
    jobs:
      build:
        runs-on: "ubuntu-latest"
        steps:
          - uses: "actions/checkout@master"
          - name: "TODO to Issue"
            uses: "alstr/todo-to-issue-action@v1.1.1-beta"
            with:
              REPO: ${{ github.repository }}
              BEFORE: ${{ github.event.before }}
              SHA: ${{ github.sha }}
              TOKEN: ${{ secrets.GITHUB_TOKEN }}
              LABEL: "# TODO"
              COMMENT_MARKER: "#"
            id: "todo"

**If you use the action in a new repo, you should initialise the repo with an empty commit.**

### Inputs

| Input    | Description |
|----------|-------------|
| `REPO` | The path to the repository where the action will be used, e.g. 'alstr/my-repo' (automatically set) |
| `BEFORE` | The SHA of the last pushed commit (automatically set) |
| `SHA` | The SHA of the latest commit (automatically set) |
| `TOKEN` | The GitHub access token to allow us to retrieve, create and update issues (automatically set) |
| `LABEL` | The label that will be used to identify TODO comments (by default this is `# TODO` for Python) |
| `COMMENT_MARKER` | The marker used to signify a line comment in your code (by default this is `#` for Python) |

## Examples

### Adding TODOs

    def hello_world():
        # TODO Come up with a more imaginative greeting
        print('Hello world!')
        
This will create an issue called "Come up with a more imaginative greeting".
 
**The action expects a space to follow the `TODO` label.**
 
Should the title be longer than 50 characters, it will be truncated for the issue title.
 
The full title will be included in the issue body and a `todo` label will be attached to the issue.

### Multiline TODOs

    def hello_world():
        # TODO Come up with a more imaginative greeting
        #  Everyone uses hello world and it's boring.
        print('Hello world!')

You can create a multiline todo by continuing below the initial TODO declaration with a comment.

The extra line(s) will be posted in the body of the issue.

The `COMMENT_MARKER` input must be set to the correct syntax (e.g. `#` for Python).

### Removing TODOs

    def hello_world():
        print('Hello world!')

Removing the `# TODO` comment will close the issue on push.

### Updating TODOs

    def hello_world():
        # TODO Come up with a more imaginative greeting, like "Greetings world!"
        print('Hello world!')
        
Should you change the `# TODO` text, this will currently create a new issue, so bear that in mind.

This may be updated in future.

## Thanks

Thanks to Jacob Tomlinson for his handy overview of GitHub Actions:

https://www.jacobtomlinson.co.uk/posts/2019/creating-github-actions-in-python/

Thanks to GitHub's [linguist repo](https://github.com/github/linguist/) for the handy `languages.yml` file used by the app to determine the correct highlighting to apply to code snippets:

https://raw.githubusercontent.com/github/linguist/master/lib/linguist/languages.yml