from fastapi import FastAPI

app = FastAPI(title="AML/KYC Decisioning Copilot")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
