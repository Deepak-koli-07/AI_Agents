from typing import Annotated
from pydantic import BaseModel, Field

MatchScore = Annotated[int, Field(ge = 0, le = 100, description = "Match score between 0 and 100")]
NonEmptyStr   = Annotated[str, Field(min_length= 1, description= 'Must be non empty string')]
SkillList     = Annotated[list[str], Field(default_factory= list, description="List of skills")]

from typing import Optional

class ScreenRequest(BaseModel):
    job_description: NonEmptyStr
    resume_text: Optional[NonEmptyStr] = None


class ScreenResponse(BaseModel):
    match_score: MatchScore
    matched_skills: SkillList
    gaps: SkillList
    summary: NonEmptyStr