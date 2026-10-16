'''
练习3：改造同步代码
将下面这段同步代码改写为异步版本(可以不使用httpx)：

import requests

def get_all_data():
    urls = ["https://api1.com/a", "https://api2.com/b", "https://api3.com/c"]
    results = []
    for url in urls:
        resp = requests.get(url, timeout=30)
        results.append(resp.json())
    return results
'''

import asyncio
import requests

async def get_all_data():
    urls = ["http://api1.com/a", "https://api2.com/b", "https://api3.com/c"]
    results = await asyncio.gather(*(requests.get(i) for i in urls))
    return results

"""
AI 评价：
你的思路方向对了（用 asyncio.gather 并发），但有一个致命缺陷：requests.get 是同步阻塞的，
它既不是协程，也无法被 await。把同步函数直接放进 asyncio.gather 里，会导致：
requests.get(i) 立即执行并阻塞当前线程，事件循环被卡住，所有“并发”退化成串行。
gather 期望接收协程对象，你却传入了 requests.Response 对象，运行时会抛出 TypeError。
所以这段代码根本无法正常运行，也没有发挥异步的威力。
"""