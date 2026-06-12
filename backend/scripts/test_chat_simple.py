#!/usr/bin/env python3
"""
Simple chat API test to diagnose the issue
"""

import asyncio
import os
import sys
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from core.database import async_engine
from models.conversation import Conversation
from models.user import User  # Import User model to ensure it's registered
from services.ai_service import ai_service


async def test_simple_chat():
    """Test simple chat functionality"""
    print("Testing simple chat functionality...")

    try:
        # Test AI service directly
        print("1. Testing AI service...")
        ai_response = await ai_service.generate_response(
            agent_type="navigation",
            user_message="你好",
            context={"user_id": "test"},
        )
        print(f"AI Response: {ai_response}")

        # Test database conversation creation
        print("2. Testing conversation creation...")
        async with AsyncSession(async_engine) as session:
            conversation = Conversation(
                user_id=uuid.UUID("2aa36071-a26f-46ed-9f06-b5740aa042b8"),  # Our test user ID
                title="测试对话",
                category="academic",
                status="active",
            )

            session.add(conversation)
            await session.commit()
            await session.refresh(conversation)

            print(f"✅ Conversation created: {conversation.id}")
            return conversation.id

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback

        traceback.print_exc()
        return None


if __name__ == "__main__":
    conversation_id = asyncio.run(test_simple_chat())
    print(f"Test completed. Conversation ID: {conversation_id}")
