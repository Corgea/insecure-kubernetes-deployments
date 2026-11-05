"""An in-memory stand-in for the browser, following static/download.html."""


class FakePage:
    def __init__(self):
        self.step = None
        self.values = {}
        self.message = ""

    def goto(self, path):
        self.step = "email"

    def fill(self, selector, value):
        self.values[selector] = value

    def click(self, selector):
        visible = {
            "email": {"#continue"},
            "code": {"#download", "#new-code"},
        }[self.step]
        if selector not in visible:
            raise AssertionError(f"{selector} is not on the {self.step} step")
        if selector == "#continue":
            self.step = "code"
        elif selector == "#new-code":
            self.message = "If that address has a transfer, we sent a new code."

    def text_content(self, selector):
        return self.message
