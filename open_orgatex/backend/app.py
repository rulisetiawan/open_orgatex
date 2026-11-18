import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import init_db
from .routes import machines, programs, recipes, planning, logs, third_party_api, orgatex_exact_api, ftp, setpoints
from .services.event_broker import broker
from .services.intervention_service import InterventionService

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Database (TimescaleDB / PostgreSQL)
    try:
        init_db()
        from .database import get_db
        from .models.schema_pg import Machine
        from .data.populate_pg import run as seed_machines

        for db in get_db():
            count = db.query(Machine).count()
            if count == 0:
                print("Database machines table empty. Auto-populating factory machines...")
                seed_machines(db)
                print(f"Seeding completed. Total machines: {db.query(Machine).count()}")
            break
    except Exception as e:
        print(f"Warning during DB initialization: {e}")

    # Startup Message Broker & Intervention Service
    try:
        await broker.start()
        InterventionService.register_listener()
    except Exception as be:
        print(f"Warning starting Event Broker: {be}")

    yield

    # Shutdown
    try:
        await broker.stop()
    except Exception as e:
        print(f"Error stopping broker: {e}")

app = FastAPI(
    title="OpenOrgaTEX - SETEX 777 Industrial MES Backend",
    version="2.2.0",
    description="Python & React Replacement for OrgaTEX Textile Dyeing Automation (Read-Only Acquisition Mode with TimescaleDB)",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Sub-Routers
app.include_router(machines.router)
app.include_router(programs.router)
app.include_router(recipes.router)
app.include_router(planning.router)
app.include_router(logs.router)
app.include_router(third_party_api.router)
app.include_router(orgatex_exact_api.router)
app.include_router(ftp.router)
app.include_router(setpoints.router)

@app.get("/api/health")
def health_check():
    return {
        "status": "online",
        "engine": "SETEX 777 Protocol Engine",
        "version": "2.2.0",
        "write_mode": "DISABLED (Read-Only Mode Active)",
        "database": "TimescaleDB (pt_smm_jetflow @ 192.168.100.30:5433)",
        "hypertable_chunk": "6 hours",
        "compression_policy": "1 day",
        "extensions": ["timescaledb", "dblink", "postgres_fdw"]
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8788"))
    uvicorn.run("open_orgatex.backend.app:app", host="0.0.0.0", port=port, reload=True)
