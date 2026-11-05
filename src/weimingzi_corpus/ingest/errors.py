"""Machine-readable failures shared by the CLI and publisher adapters."""


class IngestError(ValueError):
    def __init__(self, code, message, exit_code=2, **details):
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code
        self.details = details

    def as_dict(self):
        return {
            "status": "error",
            "code": self.code,
            "message": str(self),
            "exit_code": self.exit_code,
            **self.details,
        }


def require(condition, message, code="PACKAGE_INTEGRITY_FAILED", exit_code=2):
    if not condition:
        raise IngestError(code, message, exit_code)
