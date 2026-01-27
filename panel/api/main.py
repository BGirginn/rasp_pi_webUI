"""
Pi Control Panel - FastAPI Application

Main entry point for the Panel API server.
"""

from contextlib import asynccontextmanager
from datetime import datetime

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from config import settings
from db import init_db, close_db
from db.migrations import run_migrations
from routers import auth, resources, telemetry, logs, jobs, alerts, network, devices, admin_console, terminal, system, files, iot, archive, backup
from services.sse import sse_manager, Channels
from services.agent_client import agent_client
from services.alert_manager import alert_manager
from services.telemetry_collector import telemetry_collector
from services.discovery import discovery_service

# ... existing code ...

# Include routers


# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Pi Control Panel API", version="1.0.0")
    
    # Run database migrations
    await run_migrations(settings.database_path)
    
    await init_db()
    
    # Start background services (agent is optional)
    try:
        await agent_client.connect()
    except Exception as e:
        logger.warning("Agent not available, running without it", error=str(e))
    
    await alert_manager.start()
    await telemetry_collector.start()
    await discovery_service.start()
    
    yield
    
    # Shutdown
    logger.info("Shutting down Pi Control Panel API")
    await discovery_service.stop()
    await telemetry_collector.stop()
    await alert_manager.stop()
    await agent_client.disconnect()
    await close_db()


# Create FastAPI app
app = FastAPI(
    title="Pi Control Panel API",
    description="Control panel for Raspberry Pi management",
    version="1.0.0",
    docs_url="/api/docs" if settings.api_debug else None,
    redoc_url="/api/redoc" if settings.api_debug else None,
    lifespan=lifespan,
)

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add CORS middleware
if settings.cors_origins_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests."""
    start_time = datetime.utcnow()
    
    response = await call_next(request)
    
    duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
    
    logger.info(
        "Request completed",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=round(duration_ms, 2),
        client=request.client.host if request.client else "unknown",
    )
    
    return response


# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions."""
    logger.exception("Unhandled exception", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(resources.router, prefix="/api/resources", tags=["Resources"])
app.include_router(telemetry.router, prefix="/api/telemetry", tags=["Telemetry"])
app.include_router(logs.router, prefix="/api/logs", tags=["Logs"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["Jobs"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["Alerts"])
app.include_router(network.router, prefix="/api/network", tags=["Network"])
app.include_router(devices.router, prefix="/api/devices", tags=["Devices"])
app.include_router(admin_console.router, prefix="/api/admin", tags=["Admin Console"])
app.include_router(terminal.router, prefix="/api/terminal", tags=["Terminal"])
app.include_router(system.router, prefix="/api/system", tags=["System"])
app.include_router(files.router, prefix="/api/files", tags=["Files"])
app.include_router(iot.router, prefix="/api/iot", tags=["IoT"])
app.include_router(archive.router, prefix="/api/archive", tags=["Archive"])
app.include_router(backup.router, prefix="/api/backup", tags=["Backup"])


# Health check endpoint
@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }


# Root redirect
@app.get("/api")
async def api_root():
    """API root - version info."""
    return {
        "name": "Pi Control Panel API",
        "version": "1.0.0",
        "docs": "/api/docs" if settings.api_debug else None
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_debug
    )


# === Static file serving for production ===
import os
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Path to UI dist folder
UI_DIST_PATH = Path(__file__).parent.parent / "ui" / "dist"

if UI_DIST_PATH.exists():
    # Serve static assets
    app.mount("/assets", StaticFiles(directory=UI_DIST_PATH / "assets"), name="assets")
    
    # Catch-all route for SPA - must be after all API routes
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve the SPA for all non-API routes."""
        # Don't serve SPA for API routes
        if full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        
        # Check if file exists in dist
        file_path = UI_DIST_PATH / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        
        # Fallback to index.html for SPA routing
        return FileResponse(UI_DIST_PATH / "index.html")
