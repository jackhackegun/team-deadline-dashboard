from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User
from ..deps import get_current_user
from ..schemas import MeUpdate, TokenResponse, UserCreate, UserLogin
from ..security import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


def _find_by_email(db: Session, email: str) -> User | None:
    """이메일은 대소문자를 가리지 않는다. Kim@Test.com으로 가입하고 kim@test.com으로 로그인해도 같은 사람이다."""
    return db.query(User).filter(func.lower(User.email) == email.strip().lower()).first()


@router.post("/signup", response_model=TokenResponse)
def signup(payload: UserCreate, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    if _find_by_email(db, email):
        raise HTTPException(status_code=400, detail="이미 가입된 이메일입니다. 로그인해 주세요.")
    user = User(email=email, password_hash=hash_password(payload.password), name=payload.name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = _find_by_email(db, payload.email)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않습니다.")
    return TokenResponse(access_token=create_access_token(user.id))


@router.get("/me")
def get_me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "name": user.name, "github_login": user.github_login}


@router.patch("/me")
def update_me(payload: MeUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """깃허브 아이디를 등록해야 내 커밋이 나로 인식된다."""
    if payload.github_login is not None:
        login = payload.github_login.strip().removeprefix("@")
        user.github_login = login or None
    db.commit()
    return {"github_login": user.github_login}
