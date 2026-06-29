from fastapi import APIRouter

from ai.api import router as ai_router
from app.api.v1 import analytics, assistant, auth, crime, currency, digital_arrest, graph, notifications, reports

api_router = APIRouter()
for router in (
    auth.router, digital_arrest.router, currency.router, graph.router, crime.router,
    assistant.router, reports.router, analytics.router, notifications.router, ai_router,
):
    api_router.include_router(router)
