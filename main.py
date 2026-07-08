import time
import uuid
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

EMAIL = "24f2002757@ds.study.iitm.ac.in"

RATE_LIMIT = 16
WINDOW = 10

app = FastAPI()

# Add the exam page origin here if it is shown in the assignment.
ALLOWED_ORIGINS = [
    "https://app-8t8xgk.example.com",
    "https://exam.sanand.workers.dev",
]

client_requests = defaultdict(deque)

# Middlewares are added from innermost to outermost.
# 1. Innermost: Rate Limit
@app.middleware("http")
async def rate_limit(request: Request, call_next):
    # Never rate-limit CORS preflight
    if request.method == "OPTIONS":
        return await call_next(request)

    client_id = request.headers.get("X-Client-Id", "anonymous")

    now = time.time()

    bucket = client_requests[client_id]

    while bucket and now - bucket[0] >= WINDOW:
        bucket.popleft()

    if len(bucket) >= RATE_LIMIT:
        retry_after = max(1, int(WINDOW - (now - bucket[0])))

        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded"},
            headers={
                "Retry-After": str(retry_after)
            },
        )

    bucket.append(now)

    return await call_next(request)

# 2. Middle: Request Context
# This needs to be outside rate_limit so that 429 responses still get the X-Request-ID header.
@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID")

    if not request_id:
        request_id = str(uuid.uuid4())

    request.state.request_id = request_id

    response = await call_next(request)

    response.headers["X-Request-ID"] = request_id

    return response

# 3. Outermost: CORS
# This must be added last so it becomes the outermost middleware. 
# This ensures that early returns (like 429 from rate_limit) still receive CORS headers.
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/ping")
def ping(request: Request):
    return {
        "email": EMAIL,
        "request_id": request.state.request_id,
    }
