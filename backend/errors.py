"""API errors. Every error goes back to the frontend as

    {"error": {"code": "BELOW_THRESHOLD", "message": "You need at least 100 points to pay."}}

The frontend shows its own wording per code; the message is a readable fallback.
"""

STATUS_BY_CODE = {
    "INVALID_REQUEST": 400,     # malformed input (not in the original spec)
    "USER_NOT_FOUND": 404,
    "BELOW_THRESHOLD": 400,
    "UNKNOWN_BRAND": 400,
    "ORDER_NOT_FOUND": 404,
    "ORDER_ALREADY_PAID": 409,
    "CHAIN_ERROR": 400,         # the spec says every error is a 4xx
}


class ApiError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = STATUS_BY_CODE.get(code, 400)


def error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}
