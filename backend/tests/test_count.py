import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from core.database import AsyncSessionLocal
from models.knowledge_base import Document, FAQ
from sqlalchemy import select, and_, func

async def check():
    async with AsyncSessionLocal() as session:
        for cat in ['general', 'administrative']:
            print(f"\n分类: {cat}")
            
            # 方法 1
            query1 = select(func.count(Document.id)).where(Document.category == cat)
            res1 = await session.execute(query1)
            print(f"  无条件: {res1.scalar()}")
            
            # 方法 2
            query2 = select(func.count(Document.id)).where(and_(Document.category == cat, Document.is_active.is_(True)))
            res2 = await session.execute(query2)
            print(f"  is_(True): {res2.scalar()}")
            
            # 方法 3
            query3 = select(func.count(Document.id)).where(and_(Document.category == cat, Document.is_active == 1))
            res3 = await session.execute(query3)
            print(f"  == 1: {res3.scalar()}")

asyncio.run(check())
