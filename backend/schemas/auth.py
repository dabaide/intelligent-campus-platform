from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from datetime import datetime

class UserLogin(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="用户名或邮箱")
    password: str = Field(..., min_length=6, max_length=128, description="密码")

class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: EmailStr = Field(..., description="邮箱地址")
    password: str = Field(..., min_length=6, max_length=128, description="密码")
    student_id: Optional[str] = Field(None, max_length=20, description="学号")
    full_name: str = Field(..., min_length=2, max_length=100, description="真实姓名")
    role: Optional[str] = Field("student", description="用户角色")
    department: Optional[str] = Field(None, max_length=100, description="院系")
    grade: Optional[str] = Field(None, max_length=20, description="年级")
    major: Optional[str] = Field(None, max_length=100, description="专业")
    phone: Optional[str] = Field(None, max_length=20, description="手机号")

    @validator('role')
    def validate_role(cls, v):
        allowed_roles = ["student", "teacher", "staff", "admin"]
        if v not in allowed_roles:
            raise ValueError(f"角色必须是以下之一: {', '.join(allowed_roles)}")
        return v

    @validator('password')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError("密码长度至少6位")
        if not any(c.isdigit() for c in v):
            raise ValueError("密码必须包含至少一个数字")
        if not any(c.isalpha() for c in v):
            raise ValueError("密码必须包含至少一个字母")
        return v

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    student_id: Optional[str]
    full_name: str
    role: str
    department: Optional[str]
    grade: Optional[str]
    major: Optional[str]
    phone: Optional[str]
    is_active: bool
    last_login: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user: dict

class TokenData(BaseModel):
    username: Optional[str] = None

class PasswordChange(BaseModel):
    current_password: str = Field(..., min_length=6, description="当前密码")
    new_password: str = Field(..., min_length=6, description="新密码")

    @validator('new_password')
    def validate_new_password(cls, v):
        if len(v) < 6:
            raise ValueError("密码长度至少6位")
        if not any(c.isdigit() for c in v):
            raise ValueError("密码必须包含至少一个数字")
        if not any(c.isalpha() for c in v):
            raise ValueError("密码必须包含至少一个字母")
        return v
