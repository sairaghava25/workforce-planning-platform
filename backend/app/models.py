from sqlalchemy import String, Integer, Float, Boolean, Date, DateTime, ForeignKey, UniqueConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from .database import Base

class Employee(Base):
    __tablename__="employees"
    id: Mapped[str]=mapped_column(String, primary_key=True)
    name: Mapped[str]=mapped_column(String, nullable=False)
    email: Mapped[str]=mapped_column(String, unique=True, nullable=False)
    role_id: Mapped[str]=mapped_column(ForeignKey("roles.id"), nullable=False)
    department: Mapped[str]=mapped_column(String, nullable=False)
    employment_type: Mapped[str]=mapped_column(String, nullable=False)
    weekly_hours: Mapped[float]=mapped_column(Float, nullable=False)
    status: Mapped[str]=mapped_column(String, default="ACTIVE")
    joined_on: Mapped[datetime]=mapped_column(Date, nullable=False)

class Role(Base):
    __tablename__="roles"
    id: Mapped[str]=mapped_column(String, primary_key=True)
    name: Mapped[str]=mapped_column(String, unique=True, nullable=False)
    department: Mapped[str]=mapped_column(String, nullable=False)

class Skill(Base):
    __tablename__="skills"
    id: Mapped[str]=mapped_column(String, primary_key=True)
    name: Mapped[str]=mapped_column(String, unique=True, nullable=False)
    category: Mapped[str]=mapped_column(String, nullable=False)
    verification_days: Mapped[int]=mapped_column(Integer, default=365)

class EmployeeSkill(Base):
    __tablename__="employee_skills"
    __table_args__=(UniqueConstraint("employee_id","skill_id",name="uq_employee_skill"),)
    id: Mapped[str]=mapped_column(String, primary_key=True)
    employee_id: Mapped[str]=mapped_column(ForeignKey("employees.id"), nullable=False)
    skill_id: Mapped[str]=mapped_column(ForeignKey("skills.id"), nullable=False)
    proficiency: Mapped[int]=mapped_column(Integer, nullable=False)
    last_verified: Mapped[datetime]=mapped_column(Date, nullable=False)
    expires_on: Mapped[datetime|None]=mapped_column(Date, nullable=True)
    verified_current: Mapped[bool]=mapped_column(Boolean, default=True)

class Project(Base):
    __tablename__="projects"
    id: Mapped[str]=mapped_column(String, primary_key=True)
    name: Mapped[str]=mapped_column(String, nullable=False)
    department: Mapped[str]=mapped_column(String, nullable=False)
    start_date: Mapped[datetime]=mapped_column(Date, nullable=False)
    end_date: Mapped[datetime]=mapped_column(Date, nullable=False)
    status: Mapped[str]=mapped_column(String, nullable=False)
    priority: Mapped[str]=mapped_column(String, nullable=False)

class DemandPlan(Base):
    __tablename__="demand_plans"
    id: Mapped[str]=mapped_column(String, primary_key=True)
    project_id: Mapped[str]=mapped_column(ForeignKey("projects.id"), nullable=False)
    role_id: Mapped[str]=mapped_column(ForeignKey("roles.id"), nullable=False)
    skill_id: Mapped[str]=mapped_column(ForeignKey("skills.id"), nullable=False)
    period_start: Mapped[datetime]=mapped_column(Date, nullable=False)
    required_fte: Mapped[float]=mapped_column(Float, nullable=False)
    demand_version: Mapped[int]=mapped_column(Integer, default=1)
    status: Mapped[str]=mapped_column(String, default="APPROVED")

class Allocation(Base):
    __tablename__="allocations"
    id: Mapped[str]=mapped_column(String, primary_key=True)
    employee_id: Mapped[str]=mapped_column(ForeignKey("employees.id"), nullable=False)
    project_id: Mapped[str]=mapped_column(ForeignKey("projects.id"), nullable=False)
    period_start: Mapped[datetime]=mapped_column(Date, nullable=False)
    period_end: Mapped[datetime]=mapped_column(Date, nullable=False)
    allocated_hours: Mapped[float]=mapped_column(Float, nullable=False)
    status: Mapped[str]=mapped_column(String, default="CONFIRMED")

class Availability(Base):
    __tablename__="availability"
    __table_args__=(UniqueConstraint("employee_id","period_start",name="uq_employee_availability_period"),)
    id: Mapped[str]=mapped_column(String, primary_key=True)
    employee_id: Mapped[str]=mapped_column(ForeignKey("employees.id"), nullable=False)
    period_start: Mapped[datetime]=mapped_column(Date, nullable=False)
    working_hours: Mapped[float]=mapped_column(Float, nullable=False)
    leave_hours: Mapped[float]=mapped_column(Float, default=0)
    available_hours: Mapped[float]=mapped_column(Float, nullable=False)

class Training(Base):
    __tablename__="training"
    id: Mapped[str]=mapped_column(String, primary_key=True)
    employee_id: Mapped[str]=mapped_column(ForeignKey("employees.id"), nullable=False)
    skill_id: Mapped[str]=mapped_column(ForeignKey("skills.id"), nullable=False)
    status: Mapped[str]=mapped_column(String, nullable=False)
    hours: Mapped[float]=mapped_column(Float, default=0)
    started_on: Mapped[datetime|None]=mapped_column(Date, nullable=True)
    completed_on: Mapped[datetime|None]=mapped_column(Date, nullable=True)

class GapAnalysis(Base):
    __tablename__="gap_analysis"
    id: Mapped[str]=mapped_column(String, primary_key=True)
    demand_id: Mapped[str]=mapped_column(ForeignKey("demand_plans.id"), nullable=False)
    required_fte: Mapped[float]=mapped_column(Float, nullable=False)
    available_fte: Mapped[float]=mapped_column(Float, nullable=False)
    gap_fte: Mapped[float]=mapped_column(Float, nullable=False)
    status: Mapped[str]=mapped_column(String, nullable=False)
    assumptions: Mapped[str]=mapped_column(Text, nullable=False)

class PolicySetting(Base):
    __tablename__="policy_settings"
    key: Mapped[str]=mapped_column(String, primary_key=True)
    value: Mapped[str]=mapped_column(String, nullable=False)
    description: Mapped[str]=mapped_column(String, nullable=False)

class AnomalyIssue(Base):
    __tablename__="anomaly_issues"
    id: Mapped[str]=mapped_column(String, primary_key=True)
    issue_type: Mapped[str]=mapped_column(String, nullable=False)
    entity_id: Mapped[str]=mapped_column(String, nullable=False)
    ground_truth: Mapped[bool]=mapped_column(Boolean, nullable=False)
    details: Mapped[str]=mapped_column(Text, nullable=False)

class AuditEvent(Base):
    __tablename__="audit_events"
    id: Mapped[str]=mapped_column(String, primary_key=True)
    event_type: Mapped[str]=mapped_column(String, nullable=False)
    entity_type: Mapped[str]=mapped_column(String, nullable=False)
    entity_id: Mapped[str]=mapped_column(String, nullable=False)
    details: Mapped[str]=mapped_column(Text, nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime, default=datetime.utcnow)
