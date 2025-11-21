# tests/test_dashboard.py

import asyncio

from src.utils.dashboard_generator import (
    generate_structured_dashboard,
    generate_rag_dashboard,
)

TEST_COMPANY_ID = "abridge"   # or "anthropic" or any valid company_id


async def main():
    print(f"=== Testing dashboards for company: {TEST_COMPANY_ID} ===\n")

    print("-> Generating STRUCTURED dashboard...")
    structured_md, structured_path = await generate_structured_dashboard(TEST_COMPANY_ID)
    print("STRUCTURED dashboard uploaded to:", structured_path)
    print("STRUCTURED preview:\n", structured_md[:500], "\n")

    print("-> Generating RAG dashboard...")
    rag_md, rag_path = await generate_rag_dashboard(TEST_COMPANY_ID)
    print("RAG dashboard uploaded to:", rag_path)
    print("RAG preview:\n", rag_md[:500], "\n")


if __name__ == "__main__":
    asyncio.run(main())
