"""Error envelope (spec 15): {"error": {"code", "message_hi", "message_en"}}."""
from fastapi import Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, code: str, message_hi: str, message_en: str, status: int = 400):
        self.code, self.message_hi, self.message_en, self.status = code, message_hi, message_en, status


def handler(_: Request, e) -> JSONResponse:
    return JSONResponse(status_code=e.status, content={"error": {"code": e.code, "message_hi": e.message_hi,
                                                                 "message_en": e.message_en}})


def not_found(what: str) -> ApiError:
    return ApiError("NOT_FOUND", f"{what} nahi mila.", f"{what} not found.", 404)
