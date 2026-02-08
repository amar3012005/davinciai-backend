"""
Quick Test Script for DaVinci AI Backend Prototype

Run this to test the API endpoints with mock data:
python test_api.py
"""

import asyncio
import httpx

BASE_URL = "http://localhost:8000"

async def test_endpoints():
    async with httpx.AsyncClient() as client:
        print("=== Testing DaVinci AI Backend Prototype ===\n")
        
        # 1. Health Check
        print("1. Health Check")
        response = await client.get(f"{BASE_URL}/health")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}\n")
        
        # 2. Login
        print("2. Login (Test credentials: admin@davinciai.eu / password)")
        response = await client.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@davinciai.eu", "password": "password"}
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   User: {data['user']['full_name']}")
            print(f"   Tenant: {data['tenant']['organization_name']}")
            tenant_id = data['tenant']['tenant_id']
        print()
        
        # 3. List Agents
        print("3. List Tenant Agents")
        response = await client.get(f"{BASE_URL}/api/tenants/{tenant_id}/agents")
        print(f"   Status: {response.status_code}")
        agents = response.json()
        print(f"   Found {len(agents)} agents:")
        for agent in agents:
            print(f"     - {agent['agent_name']} ({agent['stats']['total_calls']} calls)")
        print()
        
        # 4. Get Metrics
        print("4. Get Call Metrics")
        response = await client.get(f"{BASE_URL}/api/metrics/analytics?agent_id=tara-support-001")
        print(f"   Status: {response.status_code}")
        analytics = response.json()
        print(f"   Total Calls Today: {analytics['total_calls_today']}")
        print(f"   Total Minutes: {analytics['total_minutes_today']}")
        print(f"   Success Rate: {analytics['success_rate']*100}%")
        print()
        
        # 5. Get Wallet Balance
        print("5. Get Wallet Balance")
        response = await client.get(f"{BASE_URL}/api/wallet/{tenant_id}")
        print(f"   Status: {response.status_code}")
        wallet = response.json()
        print(f"   Balance: €{wallet['balance_euros']}")
        print(f"   Estimated Calls Remaining: {wallet['estimated_calls_remaining']}")
        print(f"   Status: {wallet['balance_status']}")
        print()
        
        # 6. Get Call Logs
        print("6. Recent Call Logs")
        response = await client.get(f"{BASE_URL}/api/metrics/calls?agent_id=tara-support-001&limit=5")
        print(f"   Status: {response.status_code}")
        calls = response.json()
        print(f"   Recent {len(calls)} calls:")
        for call in calls[:3]:
            print(f"     - {call['call_id']}: {call['duration_display']} - €{call['cost_euros']} [{call['status']}]")
        print()
        
        # 7. Get Pricing
        print("7. Pricing Tiers")
        response = await client.get(f"{BASE_URL}/api/wallet/pricing/display")
        print(f"   Status: {response.status_code}")
        pricing = response.json()
        print("   Tiers:")
        for tier in pricing['tiers']:
            duration = f"{tier['duration_min']}-{tier['duration_max']}" if tier['duration_max'] else f"{tier['duration_min']}+"
            print(f"     - {duration} min: €{tier['price']}")
        print()
        
        print("✅ All tests completed!")

if __name__ == "__main__":
    asyncio.run(test_endpoints())
