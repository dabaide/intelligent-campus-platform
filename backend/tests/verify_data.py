#!/usr/bin/env python3
"""验证知识库数据是否正确导入"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from core.database import AsyncSessionLocal
from models.knowledge_base import Document, FAQ
from sqlalchemy import select, func

async def verify():
    async with AsyncSessionLocal() as session:
        # 检查文档
        doc_count = await session.execute(select(func.count(Document.id)))
        doc_total = doc_count.scalar()
        print(f"📄 文档总数: {doc_total}")
        
        if doc_total > 0:
            docs = await session.execute(select(Document))
            for doc in docs.scalars():
                print(f"   ✓ {doc.title} ({doc.category})")
        
        # 检查FAQ
        faq_count = await session.execute(select(func.count(FAQ.id)))
        faq_total = faq_count.scalar()
        print(f"\n❓ FAQ总数: {faq_total}")
        
        if faq_total > 0:
            faqs = await session.execute(select(FAQ))
            for faq in faqs.scalars():
                print(f"   ✓ {faq.question} ({faq.category})")
        
        # 检查分类
        doc_cats = await session.execute(select(Document.category).distinct())
        doc_categories = doc_cats.scalars().all()
        print(f"\n📂 文档分类: {doc_categories}")
        
        faq_cats = await session.execute(select(FAQ.category).distinct())
        faq_categories = faq_cats.scalars().all()
        print(f"📂 FAQ分类: {faq_categories}")
        
        if doc_total > 0 and faq_total > 0:
            print("\n✅ 数据验证成功！知识库数据已正确导入。")
        else:
            print("\n❌ 数据验证失败！知识库数据未导入。")

if __name__ == "__main__":
    asyncio.run(verify())
