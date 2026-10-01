class MockEmailProvider:
    def send(self, email: str, subject: str, message: str):
        return True, None
