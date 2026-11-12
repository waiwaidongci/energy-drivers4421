import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy import text
from redis import Redis
from src.config.database import Base,engine,Session
from src.config.settings import SEED_DEMO,REDIS_URL
from src import models
from src.routes import auth,datasets,days,runs,findings,hypotheses,audit
from src.middlewares.audit import AuditMiddleware
from src.middlewares.errors import ErrorMiddleware
from src.middlewares.rate_limit import RateLimitMiddleware
@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    try:
        from src.services.hypothesis_service import ensure_revision_schema,backfill_revisions
        with Session() as db:ensure_revision_schema(db);backfill_revisions(db)
    except Exception:logging.exception("hypothesis revision migration failed; app remains available")
    if SEED_DEMO:
        try:
            from scripts.seed_demo import seed
            seed()
        except Exception:logging.exception("seed failed; app remains available")
    yield
app=FastAPI(title="砾山建筑能耗归因台",lifespan=lifespan)
app.add_middleware(AuditMiddleware);app.add_middleware(RateLimitMiddleware);app.add_middleware(ErrorMiddleware)
for mod in (auth,datasets,days,runs,findings,hypotheses,audit):app.include_router(mod.router)
@app.get("/health")
def health():
    with engine.connect() as conn:conn.execute(text("SELECT 1"))
    Redis.from_url(REDIS_URL).ping();return {"status":"ok"}
