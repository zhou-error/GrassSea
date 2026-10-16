import asyncio
import random

random.seed(42)

async def fetch_user_info(user_id: str) -> str:
    print(f"开始获取 {user_id} 的用户信息")
    await asyncio.sleep(random.uniform(1,5))
    print(f"成功获取到 {user_id} 的信息")
    return f"<{user_id} 的信息>"

users_id = ["熊大", "熊二", "光头强", "涂涂", "蹦蹦"]

async def main():
    results = await asyncio.gather(*(fetch_user_info(i) for i in users_id))
    for r in results:
        print(r)

asyncio.run(main())