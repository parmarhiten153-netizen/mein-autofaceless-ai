from contextlib import asynccontextmanager
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from .config import settings
from .database import Base, engine, get_db
from .models import User, DailyUsage, VideoJob, QuotaAudit
from .schemas import RegisterIn, LoginIn, TokenOut, UserOut, JobCreate, JobOut, DashboardOut
from .security import hash_password, verify_password, create_access_token, current_user

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in settings.allowed_origins.split(",")], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
def health():
    return {"status": "ok", "service": settings.app_name, "stage": 1}

def validate_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(status_code=422, detail="Use a valid IANA timezone, such as Asia/Kolkata")
    return value

@app.post("/api/auth/register", response_model=UserOut, status_code=201)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    validate_timezone(payload.timezone)
    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(email=email, password_hash=hash_password(payload.password), timezone=payload.timezone, daily_quota=settings.default_daily_quota)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    db.refresh(user)
    return user

@app.post("/api/auth/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")
    return TokenOut(access_token=create_access_token(user.id))

@app.get("/api/auth/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user

@app.patch("/api/settings/timezone", response_model=UserOut)
def update_timezone(payload: dict, db: Session = Depends(get_db), user: User = Depends(current_user)):
    value = validate_timezone(str(payload.get("timezone", "")))
    user.timezone = value
    db.commit()
    db.refresh(user)
    return user

def local_today(user: User):
    return datetime.now(timezone.utc).astimezone(ZoneInfo(user.timezone)).date()

@app.post("/api/jobs", response_model=JobOut, status_code=202)
def create_job(payload: JobCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    # The user row is locked in PostgreSQL so concurrent requests for this account
    # serialize before quota is checked. SQLite is for local demo/testing only.
    if db.bind and db.bind.dialect.name == "postgresql":
        locked_user = db.scalar(select(User).where(User.id == user.id).with_for_update())
        if not locked_user:
            raise HTTPException(status_code=401, detail="Account is unavailable")
        user = locked_user
    existing = db.scalar(select(VideoJob).where(VideoJob.user_id == user.id, VideoJob.idempotency_key == payload.idempotency_key))
    if existing:
        return existing
    today = local_today(user)
    usage = db.scalar(select(DailyUsage).where(DailyUsage.user_id == user.id, DailyUsage.local_date == today))
    if not usage:
        usage = DailyUsage(user_id=user.id, local_date=today, reserved=0, completed=0)
        db.add(usage)
        db.flush()
    used = usage.reserved + usage.completed
    if used >= user.daily_quota:
        db.rollback()
        raise HTTPException(status_code=429, detail=f"Daily limit reached ({user.daily_quota} jobs). Your quota resets at midnight in {user.timezone}.")
    job = VideoJob(user_id=user.id, idempotency_key=payload.idempotency_key, title="Untitled video", niche=payload.niche, language=payload.language, format=payload.format, target_duration_seconds=payload.target_duration_seconds, tone=payload.tone, status="queued", progress=0, quota_date=today, quota_reserved=True)
    usage.reserved += 1
    db.add(job)
    db.flush()
    db.add(QuotaAudit(user_id=user.id, job_id=job.id, local_date=today, action="reserved", details=f"Reserved generation slot {usage.reserved}/{user.daily_quota}"))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(VideoJob).where(VideoJob.user_id == user.id, VideoJob.idempotency_key == payload.idempotency_key))
        if existing:
            return existing
        raise HTTPException(status_code=409, detail="Could not reserve quota; please retry")
    db.refresh(job)
    return job

@app.get("/api/jobs", response_model=list[JobOut])
def list_jobs(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return list(db.scalars(select(VideoJob).where(VideoJob.user_id == user.id).order_by(VideoJob.created_at.desc()).limit(100)))

@app.post("/api/jobs/{job_id}/cancel", response_model=JobOut)
def cancel_job(job_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    job = db.scalar(select(VideoJob).where(VideoJob.id == job_id, VideoJob.user_id == user.id))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in ("queued", "processing"):
        raise HTTPException(status_code=409, detail="Only queued or processing jobs can be cancelled")
    if job.status == "queued" and job.quota_reserved:
        usage = db.scalar(select(DailyUsage).where(DailyUsage.user_id == user.id, DailyUsage.local_date == job.quota_date))
        if usage:
            usage.reserved = max(0, usage.reserved - 1)
        job.quota_reserved = False
        db.add(QuotaAudit(user_id=user.id, job_id=job.id, local_date=job.quota_date, action="released", details="Queued job cancelled before processing"))
    job.status = "cancelled"
    job.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return job

@app.get("/api/dashboard", response_model=DashboardOut)
def dashboard(db: Session = Depends(get_db), user: User = Depends(current_user)):
    today = local_today(user)
    usage = db.scalar(select(DailyUsage).where(DailyUsage.user_id == user.id, DailyUsage.local_date == today))
    reserved = usage.reserved if usage else 0
    completed_today = usage.completed if usage else 0
    used = reserved + completed_today
    jobs = list(db.scalars(select(VideoJob).where(VideoJob.user_id == user.id).order_by(VideoJob.created_at.desc()).limit(50)))
    counts = {state: sum(1 for j in jobs if j.status == state) for state in ["queued", "processing", "completed", "failed"]}
    return DashboardOut(timezone=user.timezone, local_date=today, daily_limit=user.daily_quota, videos_used_today=used, remaining_today=max(0, user.daily_quota-used), queued=counts["queued"], processing=counts["processing"], completed=counts["completed"], failed=counts["failed"], jobs=jobs)

@app.delete("/api/account", status_code=204)
def delete_account(db: Session = Depends(get_db), user: User = Depends(current_user)):
    db.delete(user)
    db.commit()
    return None
