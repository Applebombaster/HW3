from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.db.session import get_db
from app.models.website import Website, WebsiteCreate, WebsiteUpdate
from app.models.check_result import CheckResult

from app.nats.client import publish_event
from app.ws.manager import ws_manager

router = APIRouter(prefix="/websites", tags=["Websites"])


@router.get("/", response_model=List[Website])
async def list_websites(
    is_active: Optional[bool] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Website)
    if is_active is not None:
        stmt = stmt.where(Website.is_active == is_active)
    result = await db.execute(stmt.order_by(Website.id))
    return result.scalars().all()


@router.get("/{website_id}", response_model=Website)
async def get_website(website_id: int, db: AsyncSession = Depends(get_db)):
    website = await db.get(Website, website_id)
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    return website


@router.post("/", response_model=Website, status_code=201)
async def create_website(
    website: WebsiteCreate,
    db: AsyncSession = Depends(get_db)
):
    existing = await db.execute(
        select(Website).where(Website.url == website.url)
    )
    if existing.scalar():
        raise HTTPException(400, "Website with this URL already exists")
    
    new_website = Website(**website.dict())
    db.add(new_website)
    await db.commit()
    await db.refresh(new_website)

    event = {"type": "website.created", "payload": new_website.dict()}
    await publish_event(event) or await ws_manager.broadcast_json(event)
    return new_website


@router.patch("/{website_id}", response_model=Website)
async def update_website(
    website_id: int, update: WebsiteUpdate, db: AsyncSession = Depends(get_db)
):
    website = await db.get(Website, website_id)
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    
    update_data = update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(website, key, value)
    
    db.add(website)
    await db.commit()
    await db.refresh(website)

    event = {"type": "website.updated", "payload": website.dict()}
    await publish_event(event) or await ws_manager.broadcast_json(event)
    return website


@router.delete("/{website_id}", status_code=204)
async def delete_website(website_id: int, db: AsyncSession = Depends(get_db)):
    website = await db.get(Website, website_id)
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    
    await db.delete(website)
    await db.commit()

    event = {"type": "website.deleted", "payload": {"id": website_id}}
    await publish_event(event) or await ws_manager.broadcast_json(event)


@router.get("/{website_id}/checks", response_model=List[CheckResult])
async def get_website_checks(
    website_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    website = await db.get(Website, website_id)
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    
    stmt = (
        select(CheckResult)
        .where(CheckResult.website_id == website_id)
        .order_by(CheckResult.checked_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()