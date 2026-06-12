from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import timedelta
import uuid

from core.database import get_db
from core.config import settings
from api.deps import create_access_token, verify_password, get_password_hash, get_current_user
from models.user import User
from schemas.auth import UserLogin, UserRegister, UserResponse, Token

router = APIRouter()

@router.post("/login", response_model=Token)
# [身份认证安全网关]:
# 1. 底层调用 bcrypt 执行哈希密码安全比对（严防数据库拖库导致明文泄露）。
# 2. 鉴权通过后签发附带用户 ID 标识的 JWT Token，实现无状态高并发会话管理。
async def login(
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """
    User login endpoint
    
    这是用户登录的核心入口。
    1. 接收前端传来的 UserLogin 数据（账号/邮箱 + 密码）
    2. 依赖注入 AsyncSession 连接异步数据库
    """
    try:
        # 构建 SQL 查询语句，支持用户名或邮箱双重登录
        # Find user by username or email
        query = select(User).where(
            (User.username == login_data.username) | 
            (User.email == login_data.username)
        )
        result = await db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误"
            )
        
        # 极度关键！调用 verify_password，在底层使用 bcrypt 算法比对哈希密文。绝对不能用明文密码直接比对，保证数据库被脱库后的安全性。
        if not verify_password(login_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误"
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户账户已被禁用"
            )
        
        # 密码比对通过，系统开始签发 JWT Token
        # Create access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user.id)}, # 把用户ID藏进Token的 sub 字段里
            expires_delta=access_token_expires
        )
        
        # 返回完整的 Token 信息给前端，前端将其存入 localStorage
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "department": user.department,
                "grade": user.grade,
                "major": user.major
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"登录失败: {str(e)}"
        )

@router.post("/register", response_model=UserResponse)
async def register(
    register_data: UserRegister,
    db: AsyncSession = Depends(get_db)
):
    """
    User registration endpoint
    """
    try:
        # Check if username already exists
        username_query = select(User).where(User.username == register_data.username)
        username_result = await db.execute(username_query)
        if username_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已存在"
            )
        
        # Check if email already exists
        email_query = select(User).where(User.email == register_data.email)
        email_result = await db.execute(email_query)
        if email_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已被注册"
            )
        
        # Check if student_id already exists (if provided)
        if register_data.student_id:
            student_id_query = select(User).where(User.student_id == register_data.student_id)
            student_id_result = await db.execute(student_id_query)
            if student_id_result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="学号已被注册"
                )
        
        # Create new user
        hashed_password = get_password_hash(register_data.password)
        
        new_user = User(
            username=register_data.username,
            email=register_data.email,
            student_id=register_data.student_id,
            full_name=register_data.full_name,
            role=register_data.role or "student",
            department=register_data.department,
            grade=register_data.grade,
            major=register_data.major,
            phone=register_data.phone,
            hashed_password=hashed_password,
            is_active=True
        )
        
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        
        return {
            "id": str(new_user.id),
            "username": new_user.username,
            "email": new_user.email,
            "full_name": new_user.full_name,
            "role": new_user.role,
            "department": new_user.department,
            "grade": new_user.grade,
            "major": new_user.major,
            "is_active": new_user.is_active,
            "created_at": new_user.created_at
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"注册失败: {str(e)}"
        )

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current user information
    """
    return {
        "id": str(current_user.id),
        "username": current_user.username,
        "email": current_user.email,
        "student_id": current_user.student_id,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "department": current_user.department,
        "grade": current_user.grade,
        "major": current_user.major,
        "phone": current_user.phone,
        "is_active": current_user.is_active,
        "last_login": current_user.last_login,
        "created_at": current_user.created_at,
        "updated_at": current_user.updated_at
    }

@router.put("/me", response_model=UserResponse)
async def update_current_user(
    update_data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update current user information
    """
    try:
        # Fields that can be updated
        updatable_fields = ["full_name", "phone", "department", "grade", "major"]
        
        for field, value in update_data.items():
            if field in updatable_fields and hasattr(current_user, field):
                setattr(current_user, field, value)
        
        await db.commit()
        await db.refresh(current_user)
        
        return {
            "id": str(current_user.id),
            "username": current_user.username,
            "email": current_user.email,
            "student_id": current_user.student_id,
            "full_name": current_user.full_name,
            "role": current_user.role,
            "department": current_user.department,
            "grade": current_user.grade,
            "major": current_user.major,
            "phone": current_user.phone,
            "is_active": current_user.is_active,
            "last_login": current_user.last_login,
            "created_at": current_user.created_at,
            "updated_at": current_user.updated_at
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新用户信息失败: {str(e)}"
        )

@router.post("/change-password")
async def change_password(
    password_data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Change user password
    """
    try:
        current_password = password_data.get("current_password")
        new_password = password_data.get("new_password")
        
        if not current_password or not new_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请提供当前密码和新密码"
            )
        
        # Verify current password
        if not verify_password(current_password, current_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="当前密码不正确"
            )
        
        # Update password
        current_user.hashed_password = get_password_hash(new_password)
        await db.commit()
        
        return {"message": "密码修改成功"}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"密码修改失败: {str(e)}"
        )

@router.post("/logout")
async def logout():
    """
    User logout endpoint (client-side token removal)
    """
    return {"message": "退出登录成功"}

@router.post("/verify-token")
async def verify_token(
    current_user: User = Depends(get_current_user)
):
    """
    Verify if token is valid
    """
    return {
        "valid": True,
        "user_id": str(current_user.id),
        "username": current_user.username,
        "role": current_user.role
    }
