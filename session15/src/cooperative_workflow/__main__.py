import asyncio
import sys

from langchain_openai import ChatOpenAI

from . import run_supervisor

DEFAULT_MODEL_ID = "gpt-5.4-mini"
REQUEST = "この製品の機能、導入条件、利用者の要望を確認したい。"

async def main(model_id: str = DEFAULT_MODEL_ID):
    result = await run_supervisor(ChatOpenAI(model=model_id), REQUEST)
    print(result.report)
    print("\n実行イベント:")
    for event in result.events:
        print(f"{event.elapsed:6.2f}s  {event.actor:<12} {event.phase}")

if __name__ == "__main__":
    asyncio.run(main(*sys.argv[1:2]))
