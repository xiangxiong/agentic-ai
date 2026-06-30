from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.core.response import fail_response

class BusinessException(Exception):
    """自定义业务异常基类"""
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message

def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(BusinessException)
    async def business_exception_handler(request: Request, exc: BusinessException):
        """拦截主动抛出的业务错误"""
        return JSONResponse(
            status_code=200, # 业务错误通常用 200 状态码返回自定义 code
            content=fail_response(code=exc.code, message=exc.message).model_dump()
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """拦截 Pydantic 参数校验错误"""
        errors = exc.errors()
        msg = f"参数校验失败: {errors[0]['loc'][-1]} {errors[0]['msg']}" if errors else "参数错误"
        return JSONResponse(
            status_code=422,
            content=fail_response(code=422, message=msg).model_dump()
        )