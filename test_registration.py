import asyncio
import httpx
import uuid

BASE_URL = "http://localhost:8000"

async def test_registration_flow():
    email = f"test_{uuid.uuid4().hex[:6]}@example.com"
    password = "password123"
    
    async with httpx.AsyncClient() as client:
        print(f"--- Testing Registration for {email} ---")
        
        # 1. Register
        reg_data = {
            "organization_name": "Test Org",
            "email": email,
            "password": password,
            "full_name": "Test User",
            "phone_number": "+1234567890",
            "address": "123 Test St, Test City"
        }
        
        response = await client.post(f"{BASE_URL}/api/auth/register", json=reg_data)
        print(f"Registration Status: {response.status_code}")
        if response.status_code != 201:
            print(f"Error: {response.text}")
            return
            
        data = response.json()
        print(f"Registration Success: {data['user']['full_name']} registered.")
        
        # 2. Login
        login_data = {
            "email": email,
            "password": password
        }
        
        response = await client.post(f"{BASE_URL}/api/auth/login", json=login_data)
        print(f"Login Status: {response.status_code}")
        if response.status_code != 200:
            print(f"Error: {response.text}")
            return
            
        data = response.json()
        print(f"Login Success: Token acquired for {data['user']['full_name']}.")
        print("--- Registration Flow Test Passed ---")

if __name__ == "__main__":
    asyncio.run(test_registration_flow())
