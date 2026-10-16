import asyncio
import time

async def greet(name: str) -> str:
    '''异步打招呼函数'''
    print(f"[开始]准备向{name}打招呼...")
    await asyncio.sleep(5)    # 模拟 I/O 等待（如网络请求）
    print(f"[完成] {name} 的招呼已准备好")
    return f"你好, {name}!"
'''
async def main():
    # 方式1: 顺序执行
    result1 = await greet("Alice")
    print(result1)
    result2 = await greet("Bob")
    print(result2)

# 运行
asyncio.run(main())
'''
'''
# 并发执行 -- asyncio.gather
async def main():
    resluts = await asyncio.gather(
        greet("Alice"),
        greet("Bob"),
        greet("Charlie")
    )
    for r in resluts:
        print(r)
    print(type(resluts))

asyncio.run(main())
'''
# 模拟 HTTP 请求并发
async def fetch_url(url: str) -> str:
    '''模拟获取 url 内容（实际应用使用httpx）'''
    print(f" [开始请求] {url}")
    await asyncio.sleep(2)    # 模拟网络延迟
    print(f" [完成请求] {url}")
    return f"<{url} 的内容>"

async def main():
    urls = ["http://api1.com", "http://api2.com", "http://api3.com"]

    start = time.time()
    # tips : asyncio.gather(*(...)) 中的 * 是解包操作符，将列表展开为多个参数。
    results = await asyncio.gather(*(fetch_url(u) for u in urls))
    elapsed = time.time() - start

    print(f"\n并发请求 {len(urls)} 个 URL 仅耗时 {elapsed:.1f} 秒")
    for r in results:
        print(r)

asyncio.run(main())