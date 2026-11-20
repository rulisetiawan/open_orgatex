import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import init_db
from .routes import machines, programs, recipes, planning, logs, third_party_api, orgatex_exact_api, ftp, setpoints
from .services.event_broker import broker
from .services.intervention_service import InterventionService
from .services.db_sync_service import DBSyncService

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Database (TimescaleDB / PostgreSQL / SQLite)
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

    # Startup Database Synchronization (PostgreSQL <-> SQLite)
    try:
        if DBSyncService.is_pg_reachable():
            sync_res = DBSyncService.sync_all()
            print(f"Initial DB Sync: {sync_res.get('message', sync_res.get('status'))}")
        else:
            print("PostgreSQL offline during startup. Local SQLite database active.")
    except Exception as se:
        print(f"Warning during initial DB sync: {se}")

    # Startup Message Broker & Intervention Service
    try:
        await broker.start()
        InterventionService.register_listener()
    except Exception as be:
        print(f"Warning starting Event Broker: {be}")

    # Background Periodic Database Synchronizer (Runs every 45s, non-blocking worker thread)
    sync_task = None
    async def periodic_db_sync():
        while True:
            await asyncio.sleep(45)
            try:
                if DBSyncService.is_pg_reachable():
                    await asyncio.to_thread(DBSyncService.sync_all)
            except Exception:
                pass

    try:
        sync_task = asyncio.create_task(periodic_db_sync())
    except Exception:
        pass

    yield

    # Shutdown
    if sync_task:
        sync_task.cancel()

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

@app.get("/api/database/sync-status")
def get_db_sync_status():
    """Mengembalikan status sinkronisasi antara PostgreSQL dan SQLite lokal."""
    return DBSyncService.get_sync_status()

@app.post("/api/database/sync")
def trigger_db_sync():
    """Memaksa proses sinkronisasi dua arah antara PostgreSQL dan SQLite lokal."""
    return DBSyncService.sync_all()

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
