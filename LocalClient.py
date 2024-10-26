import subprocess
import os

class LocalClient(object):
    def __init__(self):
        self.diff_url = None
        self.commits = ['placeholder'] # content doesn't matter, just length
        self.insert_issue_urls = False
        self.__set_diff_refs__()

    def __set_diff_refs__(self):
        # set the target of the comparison to user-specified value, if
        # provided, falling back to HEAD
        manual_commit_ref = os.getenv('MANUAL_COMMIT_REF')
        if manual_commit_ref:
            self.sha = manual_commit_ref
        else:
            self.sha = subprocess.run(['git', 'rev-parse', 'HEAD'], stdout=subprocess.PIPE).stdout.decode('utf-8').strip()
        # set the soruce of the comparison to user-specified value, if
        # provided, falling back to commit immediately before the target
        manual_base_ref = os.getenv('MANUAL_BASE_REF')
        if manual_base_ref:
            self.base_ref = manual_base_ref
        else:
            self.base_ref = subprocess.run(['git', 'rev-parse', f'{self.sha}^'], stdout=subprocess.PIPE).stdout.decode('utf-8').strip()
        # print feedback to the user
        if manual_commit_ref and manual_base_ref:
            print(f'Manually comparing {manual_base_ref}...{manual_commit_ref}')
        elif manual_commit_ref:
            print(f'Manual checking {manual_commit_ref}')

    def get_last_diff(self):
        return subprocess.run(['git', 'diff', f'{self.base_ref}..{self.sha}'], stdout=subprocess.PIPE).stdout.decode('latin-1')

    def create_issue(self, issue):
        return [201, None]

    def close_issue(self, issue):
        return 200

    def get_issue_url(self, new_issue_number):
        return "N/A"
