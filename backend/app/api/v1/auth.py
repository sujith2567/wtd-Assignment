from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ...core.database import get_db
from ...core.security import verify_password, get_password_hash, create_access_token, get_current_user
from ...models.user import User, UserRole
from ...models.student import Student
from ...models.company import Company
from ...schemas.user import UserCreate, UserLogin, Token, UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    # Check if user already exists
    existing = db.query(User).filter(User.email == user_in.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists."
        )

    # Create user
    user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        role=user_in.role,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # If recruiter, create a default company profile placeholder if not exists
    if user.role == UserRole.RECRUITER:
        comp = Company(
            user_id=user.id,
            company_name=f"{user.full_name}'s Organization",
            contact_email=user.email
        )
        db.add(comp)
        db.commit()

    return user

@router.post("/login", response_model=Token)
def login(user_in: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_in.email).first()
    if not user or not verify_password(user_in.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user account")

    # Enforce role-match validation: database role MUST match selected login role
    if user_in.role is not None and user.role != user_in.role:
        role_labels = {
            UserRole.STUDENT: "Student",
            UserRole.RECRUITER: "Recruiter / Company",
            UserRole.ADMIN: "College Administrator",
        }
        selected_label = role_labels.get(user_in.role, str(user_in.role.value).capitalize())
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This account is not registered as a {selected_label}. Please select the correct role tile to sign in."
        )

    access_token = create_access_token(data={"sub": user.email, "role": user.role.value, "user_id": user.id})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "email": user.email,
        "role": user.role,
        "full_name": user.full_name
    }


@router.get("/me", response_model=UserResponse)
def read_current_user_profile(current_user: User = Depends(get_current_user)):
    return current_user
