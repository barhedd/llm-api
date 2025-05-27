from sqlalchemy.orm import Session
from app import models

def link_rights_to_analysis(db: Session, analysis_id, rights_ids):
    for right_id in rights_ids:
        link = models.AnalysisRight(
            id_analysis=analysis_id,
            id_right=right_id
        )
        db.add(link)
    db.commit() 