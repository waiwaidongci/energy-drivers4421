from pydantic import BaseModel,Field
class HypothesisInput(BaseModel):
    title:str=Field(min_length=2,max_length=160)
    finding_id:int
    action:str=Field(min_length=10,max_length=1200)
    verification:str=Field(min_length=10,max_length=1200)
class RevisionInput(BaseModel):
    base_version:int=Field(ge=1)
    finding_id:int
    action:str=Field(min_length=10,max_length=1200)
    verification:str=Field(min_length=10,max_length=1200)
class ApproveInput(BaseModel):
    version:int|None=Field(default=None,ge=1)
