#!/usr/bin/env python3
"""
Initialize demo users for testing
Creates demo accounts that match the frontend login page
"""

import asyncio
import os
import sys
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from core.database import async_engine, AsyncSessionLocal
from models.user import User
from api.deps import get_password_hash


async def init_demo_users():
    """Initialize demo users"""
    print("🚀 Initializing demo users...")
    
    # Demo users configuration
    demo_users = [
        {
            "username": "student",
            "email": "student@example.com",
            "password": "password123",
            "full_name": "学生用户",
            "role": "student",
            "department": "计算机学院",
            "grade": "2022级",
            "major": "计算机科学与技术"
        },
        {
            "username": "teacher",
            "email": "teacher@example.com",
            "password": "password123",
            "full_name": "教师用户",
            "role": "teacher",
            "department": "计算机学院",
            "grade": None,
            "major": None
        },
        {
            "username": "admin",
            "email": "admin@example.com",
            "password": "password123",
            "full_name": "管理员用户",
            "role": "admin",
            "department": "信息中心",
            "grade": None,
            "major": None
        }
    ]
    
    async with AsyncSessionLocal() as session:
        try:
            for user_data in demo_users:
                # Check if user already exists
                from sqlalchemy import select
                query = select(User).where(
                    (User.username == user_data["username"]) | 
                    (User.email == user_data["email"])
                )
                result = await session.execute(query)
                existing_user = result.scalar_one_or_none()
                
                if existing_user:
                    print(f"✅ User '{user_data['username']}' already exists")
                    continue
                
                # Create new user
                user = User(
                    id=uuid.uuid4(),
                    username=user_data["username"],
                    email=user_data["email"],
                    hashed_password=get_password_hash(user_data["password"]),
                    full_name=user_data["full_name"],
                    role=user_data["role"],
                    department=user_data["department"],
                    grade=user_data["grade"],
                    major=user_data["major"],
                    is_active=True,
                    created_at=datetime.now()
                )
                
                session.add(user)
                print(f"✨ Created user: {user_data['username']} ({user_data['email']})")
            
            await session.commit()
            print("\n✅ Demo users initialized successfully!")
            print("\n📝 Demo Accounts:")
            print("=" * 50)
            for user_data in demo_users:
                print(f"  {user_data['role'].upper()}: {user_data['email']} / {user_data['password']}")
            print("=" * 50)
            
        except Exception as e:
            await session.rollback()
            print(f"❌ Error initializing demo users: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(init_demo_users())
    sys.exit(0 if success else 1)
