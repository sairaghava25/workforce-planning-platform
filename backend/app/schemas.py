from pydantic import BaseModel, Field
class GenerateRequest(BaseModel):
    employees: int = Field(default=100, ge=10, le=5000)
    skills: int = Field(default=30, ge=10, le=300)
    projects: int = Field(default=10, ge=2, le=500)
    months: int = Field(default=12, ge=1, le=12)
    seed: int = 20261022
    inject_anomalies: bool = True
