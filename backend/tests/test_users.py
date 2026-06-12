import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from core.database import AsyncSessionLocal
from models.user import User
from sqlalchemy import select
from api.deps import verify_password

async def check():
    print("开始检查用户...")
    async with AsyncSessionLocal() as session:
        users = await session.execute(select(User))
        for u in users.scalars():
            print(f"找到用户: {u.username}, 邮箱: {u.email}")
            print(f"密码验证 (password123): {verify_password('password123', u.hashed_password)}")
            print(f"是否激活: {u.is_active}")

asyncio.run(check())
