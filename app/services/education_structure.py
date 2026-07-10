"""
services/education_structure.py

Single source of truth for the Sindh Board level/group/subject structure.
Subjects are NEVER accepted from the client -- always derived here, so
an invalid combination (e.g. Pre-Medical + Computer Science) can't exist.
"""

LEVEL_GROUP_SUBJECTS = {
    ("SSC (Matric)", "Science (Biology)"): ["Physics", "Chemistry", "Biology", "Mathematics"],
    ("SSC (Matric)", "Science (Computer Science)"): ["Physics", "Chemistry", "Computer Science", "Mathematics"],
    ("HSSC (Intermediate)", "Pre-Medical"): ["Physics", "Chemistry", "Biology"],
    ("HSSC (Intermediate)", "Pre-Engineering"): ["Physics", "Chemistry", "Mathematics"],
    ("HSSC (Intermediate)", "ICS (Computer Science)"): ["Physics", "Computer Science", "Mathematics"],
}

LEVEL_GRADES = {
    "SSC (Matric)": [9, 10],
    "HSSC (Intermediate)": [11, 12],
}


def get_subjects(level: str, group: str) -> list[str]:
    key = (level, group)
    if key not in LEVEL_GROUP_SUBJECTS:
        raise ValueError(f"Invalid combination: {level} + {group}")
    return LEVEL_GROUP_SUBJECTS[key]


def validate_grade(level: str, grade: int) -> bool:
    return grade in LEVEL_GRADES.get(level, [])