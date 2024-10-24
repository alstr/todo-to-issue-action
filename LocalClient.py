import subprocess

class LocalClient(object):
    def __init__(self):
        self.diff_url = None
        self.commits = ['placeholder'] # content doesn't matter, just length
        self.insert_issue_urls = False

    def get_last_diff(self):
        return subprocess.run(['git', 'diff', 'HEAD^..HEAD'], stdout=subprocess.PIPE).stdout.decode('utf-8')

    def create_issue(self, issue):
        return [201, None]

    def close_issue(self, issue):
        return 200
