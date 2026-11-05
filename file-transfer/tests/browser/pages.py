"""Page objects for the browser tests."""


class DownloadPage:
    def __init__(self, page):
        self.page = page

    def open(self):
        self.page.goto("/download")

    def submit_email(self, email):
        self.page.fill("#email", email)
        self.page.click("#continue")

    def request_new_code(self, email):
        self.page.click("#new-code")

    def message(self):
        return self.page.text_content("#message")
