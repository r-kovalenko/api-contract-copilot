"""Always-offline provider demo; live calls require explicit application configuration."""

import asyncio

from app.model_provider import Evidence, FakeProvider, GenerationRequest


async def main():
    request = GenerationRequest(
        question="What evidence is available?",
        evidence=[
            Evidence(source_id="synthetic-1", text="The v2 schema uses display_name."),
        ],
    )
    print((await FakeProvider().generate(request)).model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
