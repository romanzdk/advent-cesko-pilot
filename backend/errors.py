"""Safe API errors; messages never include submitted data or internal details."""
class APIError(Exception):
    def __init__(self, code, error, message):
        super().__init__(message)
        self.code, self.error, self.message = code, error, message

    def body(self):
        return {"error": self.error, "message": self.message}
