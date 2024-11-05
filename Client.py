class Client(object):
    def get_last_diff(self):
        return None

    def create_issue(self, issue):
        return [201, None]

    def close_issue(self, issue):
        return 200

    def get_issue_url(self, new_issue_number):
        return "N/A"
