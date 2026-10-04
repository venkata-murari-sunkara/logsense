from fastapi import APIRouter

from app.schemas import SimulationStart, SimulationStatus
from app.services import simulation

router = APIRouter(prefix="/api/simulation", tags=["simulation"])


@router.post("/start", response_model=SimulationStatus)
def start_simulation(payload: SimulationStart):
    return simulation.start(payload.interval_seconds)


@router.post("/stop", response_model=SimulationStatus)
def stop_simulation():
    return simulation.stop()


@router.get("/status", response_model=SimulationStatus)
def get_simulation_status():
    return simulation.status()
