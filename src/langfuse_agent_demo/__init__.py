def main() -> None:
    import uvicorn

    uvicorn.run("langfuse_agent_demo.main:app", host="127.0.0.1", port=8000)
