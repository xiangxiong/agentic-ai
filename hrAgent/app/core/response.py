from typing import Any, Generic, TypeVar, Optional
from pydantic import BaseModel

T = TypeVar("T")

class ResponseSchema(BaseModel, Generic[T]):
    """标准 API 响应结构"""
    code: int = 200
    message: str = "success"
    data: Optional[T] = None

def success_response(data: Any = None, message: str = "success") -> ResponseSchema:
    return ResponseSchema(code=200, message=message, data=data)

def fail_response(code: int, message: str, data: Any = None) -> ResponseSchema:
    return ResponseSchema(code=code, message=message, data=data)