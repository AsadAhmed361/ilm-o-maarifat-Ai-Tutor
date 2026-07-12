from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas, auth
from app.services.education_structure import get_subjects, validate_grade

router = APIRouter(prefix="/profile", tags=["profile"])


@router.post("", response_model=schemas.StudentProfileOut)
def create_or_update_profile(
    profile_in: schemas.StudentProfileCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    if not validate_grade(profile_in.level, profile_in.grade):
        raise HTTPException(
            status_code=400,
            detail=f"Grade {profile_in.grade} is not valid for level {profile_in.level}",
        )

    try:
        subjects = get_subjects(profile_in.level, profile_in.group)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    existing = db.query(models.StudentProfile).filter(
        models.StudentProfile.user_id == current_user.id
    ).first()

    if existing:
        existing.name = profile_in.name
        existing.phone_number = profile_in.phone_number
        existing.level = profile_in.level
        existing.group = profile_in.group
        existing.grade = profile_in.grade
        existing.subjects = subjects
        existing.school_name = profile_in.school_name
        db.commit()
        db.refresh(existing)
        return existing

    new_profile = models.StudentProfile(
        user_id=current_user.id,
        name=profile_in.name,
        phone_number=profile_in.phone_number,
        level=profile_in.level,
        group=profile_in.group,
        grade=profile_in.grade,
        subjects=subjects,
        school_name=profile_in.school_name,
    )
    db.add(new_profile)
    db.commit()
    db.refresh(new_profile)
    return new_profile


@router.get("/me", response_model=schemas.StudentProfileOut)
def get_my_profile(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(models.StudentProfile).filter(
        models.StudentProfile.user_id == current_user.id
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not created yet")
    return profile
    
@router.patch("/me", response_model=schemas.StudentProfileOut)
def update_my_profile(
    profile_update: schemas.StudentProfileUpdate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(models.StudentProfile).filter(
        models.StudentProfile.user_id == current_user.id
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not created yet")

    # Merge provided fields with existing values -- only overwrite what
    # the client actually sent (exclude_unset=True skips absent fields)
    update_data = profile_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    # Re-validate and re-derive subjects using the MERGED state --
    # necessary because level or group may have just changed above.
    if not validate_grade(profile.level, profile.grade):
        raise HTTPException(
            status_code=400,
            detail=f"Grade {profile.grade} is not valid for level {profile.level}",
        )

    try:
        profile.subjects = get_subjects(profile.level, profile.group)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    db.commit()
    db.refresh(profile)
    return profile