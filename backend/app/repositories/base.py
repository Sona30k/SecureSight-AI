from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class Repository(Generic[ModelT]):
    def __init__(self, model: type[ModelT], session: AsyncSession):
        self.model = model
        self.session = session

    async def get(self, entity_id: UUID) -> ModelT | None:
        return await self.session.get(self.model, entity_id)

    async def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        await self.session.flush()
        return entity
