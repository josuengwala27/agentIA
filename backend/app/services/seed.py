from pathlib import Path

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import Organization, User, UserRole


def seed_demo_data(db: Session) -> None:
    org = db.query(Organization).filter(Organization.name == "Centre Demo").first()
    if not org:
        org = Organization(name="Centre Demo")
        db.add(org)
        db.flush()

    demos = [
        ("admin@demo.local", "Admin Demo", UserRole.ADMIN.value, "admin123"),
        ("formateur@demo.local", "Formateur Demo", UserRole.TRAINER.value, "trainer123"),
        ("apprenant@demo.local", "Apprenant Demo", UserRole.LEARNER.value, "learner123"),
    ]
    for email, name, role, password in demos:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            continue
        db.add(
            User(
                organization_id=org.id,
                email=email,
                full_name=name,
                role=role,
                hashed_password=hash_password(password),
            )
        )
    db.commit()

    Path("uploads").mkdir(parents=True, exist_ok=True)
