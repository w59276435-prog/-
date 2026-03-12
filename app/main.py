from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Generator, Optional

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, Integer, String, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

DATABASE_URL = "sqlite:///./data.db"


class Base(DeclarativeBase):
    pass


class Person(Base):
    __tablename__ = "people"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), index=True)
    department: Mapped[str] = mapped_column(String(64), index=True)
    tag: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class PersonCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    department: str = Field(min_length=1, max_length=64)
    tag: str = Field(default="", max_length=64)


class PersonUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    department: Optional[str] = Field(default=None, min_length=1, max_length=64)
    tag: Optional[str] = Field(default=None, max_length=64)


class PersonOut(BaseModel):
    id: int
    name: str
    department: str
    tag: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StatsOut(BaseModel):
    total_people: int
    total_departments: int


app = FastAPI(title="个人信息自动处理存档导出工具 MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/stats", response_model=StatsOut)
def stats(db: Session = Depends(get_db)) -> StatsOut:
    total_people = db.scalar(select(func.count(Person.id))) or 0
    total_departments = db.scalar(select(func.count(func.distinct(Person.department)))) or 0
    return StatsOut(total_people=total_people, total_departments=total_departments)


@app.get("/api/people", response_model=list[PersonOut])
def list_people(
    keyword: str = Query(default="", description="姓名/部门/标签关键字"),
    db: Session = Depends(get_db),
) -> list[PersonOut]:
    stmt = select(Person).order_by(Person.id.desc())
    if keyword.strip():
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(
            (Person.name.like(like))
            | (Person.department.like(like))
            | (Person.tag.like(like))
        )
    return list(db.scalars(stmt).all())


@app.post("/api/people", response_model=PersonOut)
def create_person(payload: PersonCreate, db: Session = Depends(get_db)) -> PersonOut:
    person = Person(name=payload.name, department=payload.department, tag=payload.tag)
    db.add(person)
    db.commit()
    db.refresh(person)
    return PersonOut.model_validate(person)


@app.patch("/api/people/{person_id}", response_model=PersonOut)
def update_person(
    person_id: int, payload: PersonUpdate, db: Session = Depends(get_db)
) -> PersonOut:
    person = db.get(Person, person_id)
    if not person:
        raise HTTPException(status_code=404, detail="人员不存在")
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(person, key, value)
    db.commit()
    db.refresh(person)
    return PersonOut.model_validate(person)


@app.delete("/api/people/{person_id}")
def delete_person(person_id: int, db: Session = Depends(get_db)) -> dict[str, bool]:
    person = db.get(Person, person_id)
    if not person:
        raise HTTPException(status_code=404, detail="人员不存在")
    db.delete(person)
    db.commit()
    return {"success": True}


@app.post("/api/import/csv")
async def import_csv(file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict[str, int]:
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="仅支持 CSV 文件")

    content = await file.read()
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    success = 0
    failed = 0

    for row in reader:
        name = (row.get("name") or "").strip()
        department = (row.get("department") or "").strip()
        tag = (row.get("tag") or "").strip()
        if not name or not department:
            failed += 1
            continue
        db.add(Person(name=name, department=department, tag=tag))
        success += 1

    db.commit()
    return {"success": success, "failed": failed}


@app.get("/api/export/csv")
def export_csv(db: Session = Depends(get_db)) -> FileResponse:
    people = db.scalars(select(Person).order_by(Person.id.asc())).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "name", "department", "tag", "created_at", "updated_at"])
    for p in people:
        writer.writerow([p.id, p.name, p.department, p.tag, p.created_at, p.updated_at])

    path = "export_people.csv"
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        f.write(output.getvalue())

    return FileResponse(path=path, media_type="text/csv", filename="people_export.csv")


app.mount("/", StaticFiles(directory="static", html=True), name="static")
