class Issue(object):
    """Basic Issue model for collecting the necessary info to send to GitHub."""

    def __init__(self, title, labels, assignees, milestone, body, hunk, file_name,
                 start_line, num_lines, markdown_language, status, identifier, identifier_actual, ref, issue_url, issue_number, start_line_within_hunk=1):
        self.title = title
        self.labels = labels
        self.assignees = assignees
        self.milestone = milestone
        self.body = body
        self.hunk = hunk
        self.file_name = file_name
        self.start_line = start_line
        self.num_lines = num_lines
        self.markdown_language = markdown_language
        self.status = status
        self.identifier = identifier
        self.identifier_actual = identifier_actual
        self.ref = ref
        self.issue_url = issue_url
        self.issue_number = issue_number
        self.start_line_within_hunk = start_line_within_hunk

    def __str__(self):
        selflist = []
        for key in [x for x in vars(self).keys() if x not in ("hunk")]:
            selflist.append(f'"{key}": "{getattr(self, key)}"')
        selflist.append((f'"hunk": "{self.hunk}"'))
        return '\n'.join(selflist)