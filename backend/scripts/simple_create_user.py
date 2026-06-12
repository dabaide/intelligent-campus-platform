#!/usr/bin/env python3
import asyncio
import hashlib
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import async_engine
from models.user import User
import uuid

async def create_simple_user():
    """Create a test user with simple password hashing"""
    print("Creating test user with simple hash...")
    
    try:
        async with AsyncSession(async_engine) as session:
            # Simple password hash for testing (not secure for production)
            password = "demo123"
            simple_hash = hashlib.sha256(password.encode()).hexdigest()
            
            test_user = User(
                id=uuid.uuid4(),
                username="demo",
                email="demo@campus.edu",
                full_name="演示用户",
                role="student",
                student_id="2024001",
                department="计算机学院",
                grade="2024",
                major="计算机科学与技术",
                hashed_password=f"simple:{simple_hash}",  # Add prefix to identify simple hash
                is_active=True
            )
            
            session.add(test_user)
            await session.commit()
            
            print("✅ Test user created successfully!")
            print("Username: demo")
            print("Password: demo123")
            print("Note: Using simple hash for testing")
            
    except Exception as e:
        print(f"❌ Error creating test user: {str(e)}")

if __name__ == "__main__":
    asyncio.run(create_simple_user())
