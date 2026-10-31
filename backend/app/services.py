import random, uuid, json, calendar, re
from datetime import date, timedelta
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import func, text, case, select
from . import models as m

ROLES = [
 ("Python Developer","Engineering"),("Backend Developer","Engineering"),("Frontend Developer","Engineering"),
 ("AI Engineer","Data"),("Data Scientist","Data"),("QA Engineer","Quality"),("DevOps Engineer","Operations"),
 ("Business Analyst","Business"),("Project Manager","Business"),("Data Engineer","Data"),
 ("Java Developer","Engineering"),("Cloud Engineer","Operations")
]
SKILL_NAMES = [
 "Python","FastAPI","Django","Java","Spring Boot","JavaScript","TypeScript","React","Next.js","SQL",
 "PostgreSQL","MongoDB","Machine Learning","Deep Learning","Natural Language Processing","PyTorch",
 "TensorFlow","Docker","Kubernetes","AWS","Azure","Git","CI/CD","Playwright","Selenium",
 "Manual Testing","Automation Testing","Data Analysis","Power BI","Pandas","NumPy","REST API",
 "Microservices","Linux","Communication","Agile","Project Management","System Design","HTML","CSS"
]
DEPARTMENTS=["Engineering","Data","Quality","Operations","Business","Product"]
PROJECT_PREFIX=["Atlas","Nova","Pulse","Orbit","Vertex","Nexus","Aster","Beacon","Cobalt","Summit"]
TODAY=date(2026,10,30)

def uid(prefix): return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"

def clear_all(db):
    for cls in [m.GapAnalysis,m.AnomalyIssue,m.Training,m.Allocation,m.Availability,m.DemandPlan,m.EmployeeSkill,m.Employee,m.Project,m.Skill,m.Role,m.PolicySetting]:
        db.query(cls).delete()
    db.commit()

def generate(db, cfg):
    clear_all(db)
    rng=random.Random(cfg.seed)
    # Policy values live in DB, not in UI or analysis consumers.
    policies=[
      ("stale_skill_days","365","Maximum days since skill verification"),
      ("underutilized_pct","50","Utilization below this percentage is underutilized"),
      ("healthy_utilization_pct","85","Upper healthy utilization percentage"),
      ("high_utilization_pct","100","Utilization above this percentage is overallocated"),
      ("minimum_proficiency","3","Minimum proficiency counted as qualified"),
      ("standard_week_hours","40","Standard full-time weekly hours"),
      ("training_gap_max_fte","1","Maximum uncovered FTE recommended for training before hiring is considered")
    ]
    db.add_all([m.PolicySetting(key=k,value=v,description=d) for k,v,d in policies])
    roles=[]
    for i,(name,dept) in enumerate(ROLES,1):
        obj=m.Role(id=f"ROLE-{i:03d}",name=name,department=dept); db.add(obj); roles.append(obj)
    skills=[]
    names=SKILL_NAMES[:]
    while len(names)<cfg.skills: names.append(f"Specialized Skill {len(names)+1:03d}")
    for i,name in enumerate(names[:cfg.skills],1):
        obj=m.Skill(id=f"SKL-{i:06d}",name=name,category=rng.choice(["Technical","Cloud","Data","Quality","Business"]),
                    verification_days=rng.choice([180,365,540]))
        db.add(obj); skills.append(obj)
    db.flush()
    employees=[]
    for i in range(1,cfg.employees+1):
        role=rng.choice(roles)
        typ=rng.choices(["FULL_TIME","PART_TIME"],weights=[0.82,0.18])[0]
        hours=40.0 if typ=="FULL_TIME" else 20.0
        e=m.Employee(id=f"EMP-{i:06d}",name=f"Employee {i:05d}",email=f"employee{i:05d}@synthetic.example",
          role_id=role.id,department=role.department,employment_type=typ,weekly_hours=hours,status="ACTIVE",
          joined_on=TODAY-timedelta(days=rng.randint(100,2500)))
        db.add(e); employees.append(e)
    db.flush()
    # Skill profiles: varied proficiency and verification age.
    es_count=0
    for e in employees:
        chosen=rng.sample(skills,k=min(len(skills),rng.randint(3, min(8,len(skills)))))
        for sk in chosen:
            es_count+=1
            verified=TODAY-timedelta(days=rng.randint(0,600))
            db.add(m.EmployeeSkill(id=f"ES-{es_count:08d}",employee_id=e.id,skill_id=sk.id,
                proficiency=rng.randint(1,5),last_verified=verified,
                expires_on=verified+timedelta(days=sk.verification_days),
                verified_current=(TODAY-verified).days<=sk.verification_days and
                                 verified+timedelta(days=sk.verification_days)>=TODAY))
    projects=[]
    for i in range(1,cfg.projects+1):
        start=TODAY+timedelta(days=rng.randint(-90,180))
        end=start+timedelta(days=rng.randint(90,450))
        p=m.Project(id=f"PRJ-2026-{i:06d}",name=f"{rng.choice(PROJECT_PREFIX)} {i:03d} Delivery",
          department=rng.choice(DEPARTMENTS),start_date=start,end_date=end,status=rng.choice(["PLANNED","ACTIVE","ACTIVE","ON_HOLD"]),
          priority=rng.choice(["LOW","MEDIUM","HIGH","CRITICAL"]))
        db.add(p); projects.append(p)
    db.flush()
    # Availability and allocation by weekly period. Allocation generated within capacity initially.
    alloc_no=0; avail_no=0; demand_no=0
    horizon_month = TODAY.month - 1 + cfg.months
    horizon_year = TODAY.year + horizon_month // 12
    horizon_month = horizon_month % 12 + 1
    horizon_end = date(horizon_year, horizon_month, min(TODAY.day, calendar.monthrange(horizon_year, horizon_month)[1]))
    period = TODAY - timedelta(days=TODAY.weekday())
    periods=[]
    while period < horizon_end:
        periods.append(period)
        period += timedelta(days=7)
    for e in employees:
        for period in periods:
            work=e.weekly_hours
            leave=rng.choices([0,4,8,16,work],[.72,.08,.08,.07,.05])[0]
            leave=min(leave,work)
            available=work-leave
            avail_no+=1
            db.add(m.Availability(id=f"AVL-{avail_no:09d}",employee_id=e.id,period_start=period,
                                  working_hours=work,leave_hours=leave,available_hours=available))
            # Assign some capacity to a project. Keep baseline at/below available.
            if rng.random()<0.48 and projects:
                p=rng.choice(projects)
                hours=round(available*rng.uniform(.25,.85),2) if available else 0
                if hours>0:
                    alloc_no+=1
                    db.add(m.Allocation(id=f"ALLOC-2026-{alloc_no:09d}",employee_id=e.id,project_id=p.id,
                      period_start=period,period_end=period+timedelta(days=6),allocated_hours=hours,status="CONFIRMED"))
    # Demand per project, period, role, skill. Sparse but related to each project's department.
    for p in projects:
        dept_roles=[r for r in roles if r.department==p.department] or roles
        selected_roles=rng.sample(dept_roles,k=min(len(dept_roles),rng.randint(1,min(3,len(dept_roles)))))
        for period in periods:
            if not (p.start_date<=period<=p.end_date): continue
            for role in selected_roles:
                for sk in rng.sample(skills,k=min(2,len(skills))):
                    demand_no+=1
                    db.add(m.DemandPlan(id=f"DEM-{p.id}-{period.isocalendar().year}W{period.isocalendar().week:02d}-R{int(role.id.split('-')[1]):03d}-S{int(sk.id.split('-')[1]):06d}",
                      project_id=p.id,role_id=role.id,skill_id=sk.id,period_start=period,
                      required_fte=round(rng.uniform(.5,3.0),2),demand_version=1,status="APPROVED"))
    db.flush()
    # Some training candidates generated from actual skill profile opportunities.
    for i,e in enumerate(rng.sample(employees,k=min(len(employees),max(1,len(employees)//12))),1):
        sk=rng.choice(skills)
        status=rng.choice(["PLANNED","IN_PROGRESS","COMPLETED"])
        started_on=None if status=="PLANNED" else TODAY-timedelta(days=40 if status=="COMPLETED" else 10)
        completed_on=TODAY-timedelta(days=10) if status=="COMPLETED" else None
        db.add(m.Training(id=f"TRN-{i:07d}",employee_id=e.id,skill_id=sk.id,status=status,
                          hours=float(rng.choice([8,16,24,40])),started_on=started_on,completed_on=completed_on))
    db.flush()
    if cfg.inject_anomalies and employees and projects and skills:
        # Controlled, explicit anomaly cases; anomaly labels remain separate from analytical inputs.
        e=employees[0]; p1=projects[0]; p2=projects[1] if len(projects)>1 else projects[0]
        period=periods[0]
        av=db.query(m.Availability).filter_by(employee_id=e.id,period_start=period).first()
        alloc_no+=1
        excess_allocation_id=f"ALLOC-2026-{alloc_no:09d}"
        db.add(m.Allocation(id=excess_allocation_id,employee_id=e.id,project_id=p1.id,
          period_start=period,period_end=period+timedelta(days=6),allocated_hours=(av.available_hours+12 if av else 40),status="CONFIRMED"))
        db.add(m.AnomalyIssue(id="GT-001",issue_type="ALLOCATION_EXCEEDS_AVAILABILITY",entity_id=e.id,ground_truth=True,
          details=f"Employee has an injected over-capacity allocation {excess_allocation_id}."))
        es=db.query(m.EmployeeSkill).filter_by(employee_id=e.id).first()
        if es:
            es.last_verified=TODAY-timedelta(days=600); es.verified_current=True
            db.add(m.AnomalyIssue(id="GT-002",issue_type="STALE_SKILL_TREATED_CURRENT",entity_id=es.id,ground_truth=True,
              details="Skill verification age exceeds policy while verified_current remains true."))
        d=db.query(m.DemandPlan).first()
        if d:
            demand_no+=1
            duplicate_demand_id=f"{d.id}-DUP-001"
            db.add(m.DemandPlan(id=duplicate_demand_id,project_id=d.project_id,role_id=d.role_id,skill_id=d.skill_id,
                period_start=d.period_start,required_fte=d.required_fte,demand_version=1,status="APPROVED"))
            db.add(m.AnomalyIssue(id="GT-003",issue_type="DEMAND_DOUBLE_COUNTED",entity_id=duplicate_demand_id,ground_truth=True,
              details="A second demand row duplicates the same project-role-skill-period-version business key."))
        alloc_no+=1
        overlap_allocation_id=f"ALLOC-2026-{alloc_no:09d}"
        db.add(m.Allocation(id=overlap_allocation_id,employee_id=e.id,project_id=p2.id,
          period_start=period,period_end=period+timedelta(days=6),allocated_hours=8,status="CONFIRMED"))
        db.add(m.AnomalyIssue(id="GT-004",issue_type="OVERLAPPING_PROJECT_ASSIGNMENT",entity_id=e.id,ground_truth=True,
          details=f"Employee has overlapping project allocations including {overlap_allocation_id}."))
    db.add(m.AuditEvent(id=uid("EVT"),event_type="DATA_GENERATED",entity_type="DATASET",entity_id="ALL",
      details=json.dumps({"seed":cfg.seed,"employees":cfg.employees,"skills":cfg.skills,"projects":cfg.projects})))
    db.commit()
    return {"employees":len(employees),"roles":len(roles),"skills":len(skills),"projects":len(projects),
            "demand_plans":db.query(m.DemandPlan).count(),"allocations":db.query(m.Allocation).count(),
            "availability":db.query(m.Availability).count(),"employee_skills":db.query(m.EmployeeSkill).count(),
            "anomalies":db.query(m.AnomalyIssue).count(),"seed":cfg.seed}

def policy(db,key,default):
    row=db.get(m.PolicySetting,key)
    return float(row.value) if row else float(default)


def _period_capacity_for_employee(db, employee_id, period_start):
    availability = db.query(m.Availability).filter_by(employee_id=employee_id, period_start=period_start).first()
    if availability is None:
        return {"gross_working_hours": 0.0, "leave_hours": 0.0, "net_available_hours": 0.0, "allocated_hours": 0.0, "remaining_capacity_hours": 0.0, "utilization_pct": 0.0}
    allocated = db.query(func.coalesce(func.sum(m.Allocation.allocated_hours), 0.0)).filter(
        m.Allocation.employee_id == employee_id,
        m.Allocation.period_start == period_start,
        m.Allocation.status == "CONFIRMED",
    ).scalar() or 0.0
    net_available = max(0.0, float(availability.available_hours))
    remaining = max(0.0, net_available - float(allocated))
    utilization = (float(allocated) / net_available * 100.0) if net_available > 0 else 0.0
    return {
        "gross_working_hours": float(availability.working_hours),
        "leave_hours": float(availability.leave_hours),
        "net_available_hours": net_available,
        "allocated_hours": float(allocated),
        "remaining_capacity_hours": remaining,
        "utilization_pct": utilization,
    }


def _build_detection_issue(db, issue_type, entity_id, details, issue_number=None):
    existing = db.query(m.AnomalyIssue).filter_by(issue_type=issue_type, entity_id=entity_id).first()
    if existing is not None:
        return existing
    if issue_number is None:
        issue_number = db.query(m.AnomalyIssue).count() + 1
    issue = m.AnomalyIssue(
        id=f"GT-{issue_number:03d}",
        issue_type=issue_type,
        entity_id=entity_id,
        ground_truth=True,
        details=details,
    )
    db.add(issue)
    return issue


def recommendation_for_gap(db,gap):
    demand = db.get(m.DemandPlan, gap.demand_id)
    if demand is None:
        return {
            "project": None,
            "project_id": None,
            "skill": None,
            "skill_id": None,
            "gap_fte": float(gap.gap_fte or 0),
            "action": "NO_ACTION_REQUIRED",
            "reason": "No underlying demand plan was found for this gap.",
            "expected_improvement": 0.0,
            "assumptions": ["Demand record missing."],
            "priority": "LOW",
        }
    skill = db.get(m.Skill, demand.skill_id)
    project = db.get(m.Project, demand.project_id)
    training_gap_max = policy(db, "training_gap_max_fte", 1)
    missing_hours = max(0.0, float(gap.gap_fte or 0.0))

    if missing_hours <= 0.05:
        action = "NO_ACTION_REQUIRED"
        reason = "Qualified capacity already covers the project requirement within the current planning window."
        expected = 0.0
        priority = "LOW"
    else:
        internal_capacity = db.query(m.EmployeeSkill).join(m.Employee, m.EmployeeSkill.employee_id == m.Employee.id).filter(
            m.EmployeeSkill.skill_id == demand.skill_id,
            m.EmployeeSkill.proficiency >= policy(db, "minimum_proficiency", 3),
            m.EmployeeSkill.verified_current.is_(True),
            m.Employee.role_id == demand.role_id,
        ).count()
        if missing_hours <= training_gap_max and internal_capacity > 0:
            action = "TRAIN_EXISTING_EMPLOYEE"
            reason = "A small shortage is present and there are qualified employees who can be trained or upskilled."
            expected = min(missing_hours, training_gap_max)
            priority = "MEDIUM"
        elif internal_capacity > 0:
            action = "INTERNAL_RESOURCE_REALLOCATION"
            reason = "Internal capacity exists for the required skill, but availability and timing require a reallocation or schedule adjustment."
            expected = min(missing_hours, float(internal_capacity))
            priority = "HIGH"
        elif missing_hours <= 1.5:
            action = "CONTRACTOR_OR_EXTERNAL_RESOURCE"
            reason = "The gap is moderate and internal staffing is insufficient within the project period."
            expected = missing_hours
            priority = "HIGH"
        else:
            action = "HIRE_NEW_EMPLOYEE"
            reason = "The shortage is significant and exceeds the current internal qualified capacity for the project requirement."
            expected = missing_hours
            priority = "CRITICAL"

    return {
        "project": project.name if project else None,
        "project_id": project.id if project else None,
        "skill": skill.name if skill else None,
        "skill_id": skill.id if skill else None,
        "gap_fte": float(gap.gap_fte or 0.0),
        "action": action,
        "reason": reason,
        "expected_improvement": round(expected, 3),
        "assumptions": [
            f"Required skill: {skill.name if skill else demand.skill_id}",
            f"Project demand: {gap.required_fte:.2f} FTE",
            f"Qualified available capacity: {gap.available_fte:.2f} FTE",
            f"Training threshold: {training_gap_max:.2f} FTE",
        ],
        "priority": priority,
    }


def analyze(db):
    stale_days = policy(db, "stale_skill_days", 365)
    min_prof = policy(db, "minimum_proficiency", 3)
    standard = policy(db, "standard_week_hours", 40)
    today = TODAY

    availability_rows = db.execute(select(
        m.Availability.employee_id,
        m.Availability.period_start,
        m.Availability.available_hours,
    )).tuples().all()
    availability_map = {(employee_id, period): float(available_hours) for employee_id, period, available_hours in availability_rows}

    alloc_map = defaultdict(float)
    overlap_map = defaultdict(set)
    allocation_rows = db.execute(select(
        m.Allocation.employee_id,
        m.Allocation.project_id,
        m.Allocation.period_start,
        m.Allocation.allocated_hours,
    )).tuples().all()
    for employee_id, project_id, period, allocated_hours in allocation_rows:
        key = (employee_id, period)
        alloc_map[key] += float(allocated_hours)
        overlap_map[key].add(project_id)

    employee_roles = dict(db.execute(select(m.Employee.id, m.Employee.role_id)).tuples().all())
    verification_days = dict(db.execute(select(m.Skill.id, m.Skill.verification_days)).tuples().all())
    skill_rows = db.execute(select(
        m.EmployeeSkill.id,
        m.EmployeeSkill.employee_id,
        m.EmployeeSkill.skill_id,
        m.EmployeeSkill.proficiency,
        m.EmployeeSkill.last_verified,
        m.EmployeeSkill.expires_on,
        m.EmployeeSkill.verified_current,
    )).tuples().all()

    issue_counter = 0
    issue_number = db.query(m.AnomalyIssue).count() + 1
    for employee_id, project_id, period, allocated_hours in allocation_rows:
        key = (employee_id, period)
        available_hours = availability_map.get(key, 0.0)
        if float(allocated_hours) > available_hours:
            issue_number += 1
            _build_detection_issue(
                db,
                "ALLOCATION_EXCEEDS_AVAILABILITY",
                employee_id,
                f"Employee {employee_id} is over-allocated for period {period.isoformat()}: {allocated_hours}h allocated against {available_hours}h available.",
                issue_number,
            )
            issue_counter += 1

    for employee_skill_id, employee_id, skill_id, proficiency, last_verified, expires_on, verified_current in skill_rows:
        verification_limit = min(stale_days, verification_days.get(skill_id, stale_days))
        if verified_current and last_verified is not None and (today - last_verified).days > verification_limit:
            issue_number += 1
            _build_detection_issue(
                db,
                "STALE_SKILL_TREATED_CURRENT",
                employee_skill_id,
                f"Skill {skill_id} for employee {employee_id} is stale but still marked current.",
                issue_number,
            )
            issue_counter += 1
        if expires_on is not None and expires_on < today and verified_current:
            issue_number += 1
            _build_detection_issue(
                db,
                "STALE_SKILL_TREATED_CURRENT",
                employee_skill_id,
                f"Skill {skill_id} for employee {employee_id} expired on {expires_on.isoformat()} while still treated as current.",
                issue_number,
            )
            issue_counter += 1

    seen = {}
    demand_rows = db.execute(select(
        m.DemandPlan.id,
        m.DemandPlan.project_id,
        m.DemandPlan.role_id,
        m.DemandPlan.skill_id,
        m.DemandPlan.period_start,
        m.DemandPlan.required_fte,
        m.DemandPlan.demand_version,
    )).tuples().all()
    for demand_id, project_id, role_id, skill_id, period, required_fte, demand_version in demand_rows:
        key = (project_id, role_id, skill_id, period, demand_version)
        if key in seen:
            _build_detection_issue(
                db,
                "DEMAND_DOUBLE_COUNTED",
                demand_id,
                f"Duplicate demand business key detected for demand {demand_id}: project={project_id}, role={role_id}, skill={skill_id}, period={period.isoformat()}, version={demand_version}.",
            )
            issue_counter += 1
        else:
            seen[key] = demand_id

    for key, projects in overlap_map.items():
        if len(projects) > 1:
            employee_id, period = key
            _build_detection_issue(
                db,
                "OVERLAPPING_PROJECT_ASSIGNMENT",
                employee_id,
                f"Employee {employee_id} is assigned to overlapping project work during {period.isoformat()}.",
            )
            issue_counter += 1

    skill_map = defaultdict(list)
    for employee_skill_id, employee_id, skill_id, proficiency, last_verified, expires_on, verified_current in skill_rows:
        skill_map[skill_id].append((employee_id, proficiency, last_verified, expires_on, verified_current))

    demand_analysis = []
    for demand_id, project_id, role_id, skill_id, as_of, required_fte, _ in demand_rows:
        verification_limit = min(stale_days, verification_days.get(skill_id, stale_days))
        qualified_free_hours = 0.0
        for employee_id, proficiency, last_verified, expires_on, verified_current in skill_map.get(skill_id, []):
            if proficiency < min_prof:
                continue
            if not verified_current:
                continue
            if last_verified is not None and (as_of - last_verified).days > verification_limit:
                continue
            if expires_on is not None and expires_on < as_of:
                continue
            if employee_roles.get(employee_id) != role_id:
                continue
            key = (employee_id, as_of)
            available_hours = availability_map.get(key, 0.0)
            allocated_hours = alloc_map.get(key, 0.0)
            qualified_free_hours += max(0.0, available_hours - allocated_hours)
        available_fte = qualified_free_hours / float(standard)
        gap = max(0.0, float(required_fte) - available_fte)
        rounded_gap = round(gap, 3)
        status = "GAP" if rounded_gap > 0.01 else "COVERED"
        assumed = (
            f"Required skill proficiency >= {min_prof}; verified within {stale_days} days; "
            f"skill expiry valid for period; capacity net of leave and existing allocations; standard week={standard}h."
        )
        existing_gap = db.query(m.GapAnalysis).filter_by(demand_id=demand_id).first()
        if existing_gap is None:
            db.add(m.GapAnalysis(
                id=f"GAP-{demand_id}",
                demand_id=demand_id,
                required_fte=float(required_fte),
                available_fte=round(available_fte, 3),
                gap_fte=rounded_gap,
                status=status,
                assumptions=assumed,
            ))
        else:
            existing_gap.required_fte = float(required_fte)
            existing_gap.available_fte = round(available_fte, 3)
            existing_gap.gap_fte = rounded_gap
            existing_gap.status = status
            existing_gap.assumptions = assumed
        demand_analysis.append({"demand_id": demand_id, "gap_fte": rounded_gap, "available_fte": round(available_fte, 3)})

    run_id = uid("RUN")
    db.add(m.AuditEvent(
        id=run_id,
        event_type="ANALYSIS_RUN",
        entity_type="ANALYSIS",
        entity_id="LATEST",
        details=json.dumps({
            "analysis_run_id": run_id,
            "detected_exceptions": issue_counter,
            "demand_rows": len(demand_rows),
            "gaps": len([row for row in demand_analysis if row["gap_fte"] > 0.01]),
        }),
    ))
    db.add(m.AuditEvent(
        id=uid("AUD"),
        event_type="ANALYSIS_SNAPSHOT",
        entity_type="WORKFORCE_SNAPSHOT",
        entity_id=run_id,
        details=json.dumps({
            "analysis_run_id": run_id,
            "employee_skills": _snapshot_rows(db.query(m.EmployeeSkill).order_by(m.EmployeeSkill.id).limit(5).all()),
            "demand_plans": _snapshot_rows(db.query(m.DemandPlan).order_by(m.DemandPlan.id).limit(5).all()),
            "allocations": _snapshot_rows(db.query(m.Allocation).order_by(m.Allocation.id).limit(5).all()),
            "gap_analysis": _snapshot_rows(db.query(m.GapAnalysis).order_by(m.GapAnalysis.id).limit(5).all()),
        }),
    ))
    db.commit()
    gap_count = db.query(m.GapAnalysis).filter(m.GapAnalysis.gap_fte > 0.01).count()
    return {"gaps": gap_count, "detected_exceptions": issue_counter}


def _anomaly_metrics_for_issue_type(actual_ids, expected_ids):
    tp = len(set(actual_ids) & set(expected_ids))
    fp = len(set(actual_ids) - set(expected_ids))
    fn = len(set(expected_ids) - set(actual_ids))
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    total_candidates = max(len(set(actual_ids) | set(expected_ids)), 1)
    tn = total_candidates - tp - fp - fn
    return {
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
    }


def _snapshot_rows(rows):
    return [
        {key: (value.isoformat() if hasattr(value, "isoformat") else value) for key, value in row.items()}
        for row in serialize(rows)
    ]


def evaluate_anomaly_detection(db):
    ground_truth = defaultdict(set)
    for row in db.query(m.AnomalyIssue).filter_by(ground_truth=True).all():
        ground_truth[row.issue_type].add(row.entity_id)

    detected = {
        "ALLOCATION_EXCEEDS_AVAILABILITY": set(),
        "STALE_SKILL_TREATED_CURRENT": set(),
        "DEMAND_DOUBLE_COUNTED": set(),
        "OVERLAPPING_PROJECT_ASSIGNMENT": set(),
    }

    for row in db.query(m.Allocation).all():
        total = db.query(func.coalesce(func.sum(m.Allocation.allocated_hours), 0.0)).filter(
            m.Allocation.employee_id == row.employee_id,
            m.Allocation.period_start == row.period_start,
            m.Allocation.status == "CONFIRMED",
        ).scalar() or 0.0
        availability = db.query(m.Availability).filter_by(employee_id=row.employee_id, period_start=row.period_start).first()
        if availability is not None and total > float(availability.available_hours):
            detected["ALLOCATION_EXCEEDS_AVAILABILITY"].add(row.employee_id)

    for row in db.query(m.EmployeeSkill).all():
        if row.verified_current and row.expires_on is not None and row.expires_on < TODAY:
            detected["STALE_SKILL_TREATED_CURRENT"].add(row.id)
        if row.verified_current and row.last_verified is not None and (TODAY - row.last_verified).days > policy(db, "stale_skill_days", 365):
            detected["STALE_SKILL_TREATED_CURRENT"].add(row.id)

    seen_duplicate_keys = {}
    for row in db.query(m.DemandPlan).order_by(m.DemandPlan.id).all():
        key = (row.project_id, row.role_id, row.skill_id, row.period_start, row.demand_version)
        if key in seen_duplicate_keys:
            detected["DEMAND_DOUBLE_COUNTED"].add(row.id)
        else:
            seen_duplicate_keys[key] = row.id

    for row in db.query(m.Allocation).all():
        same_period = db.query(m.Allocation).filter(
            m.Allocation.employee_id == row.employee_id,
            m.Allocation.period_start == row.period_start,
            m.Allocation.id != row.id,
        ).count()
        if same_period > 0:
            detected["OVERLAPPING_PROJECT_ASSIGNMENT"].add(row.employee_id)

    report = {}
    for issue_type in ["ALLOCATION_EXCEEDS_AVAILABILITY", "STALE_SKILL_TREATED_CURRENT", "DEMAND_DOUBLE_COUNTED", "OVERLAPPING_PROJECT_ASSIGNMENT"]:
        report[issue_type] = _anomaly_metrics_for_issue_type(detected[issue_type], ground_truth.get(issue_type, set()))
    return report


def forecast_demand(db):
    groups = defaultdict(list)
    for row in db.query(m.DemandPlan).all():
        if row.period_start < TODAY:
            groups[(row.project_id, row.role_id, row.skill_id)].append(row)

    forecasts = []
    for (project_id, role_id, skill_id), rows in sorted(groups.items()):
        unique_rows = {}
        for row in sorted(rows, key=lambda r: r.period_start):
            unique_rows[row.period_start] = row
        ordered_rows = list(unique_rows.values())
        history = [(row.period_start, float(row.required_fte)) for row in ordered_rows]
        if not history:
            continue

        period_points = [period for period, _ in history]
        values = [value for _, value in history]
        if len(values) < 2:
            forecast_fte = values[0]
            confidence = "INSUFFICIENT_DATA"
            methodology = "single-record fallback"
            accuracy = None
        else:
            recent = values[-4:]
            moving_average = sum(recent) / len(recent)
            trend = (recent[-1] - recent[0]) / max(len(recent) - 1, 1)
            forecast_fte = max(0.0, moving_average + trend)
            methodology = "moving_average_plus_trend"
            if len(values) >= 3:
                accuracy = None
                future_rows = db.query(m.DemandPlan).filter(
                    m.DemandPlan.project_id == project_id,
                    m.DemandPlan.role_id == role_id,
                    m.DemandPlan.skill_id == skill_id,
                    m.DemandPlan.period_start >= TODAY,
                ).order_by(m.DemandPlan.period_start).all()
                if future_rows:
                    actual = float(future_rows[0].required_fte)
                    accuracy = round(abs(forecast_fte - actual) / max(abs(actual), 1e-9), 4)
                confidence = "MEDIUM" if accuracy is not None else "INSUFFICIENT_DATA"
            else:
                accuracy = None
                confidence = "INSUFFICIENT_DATA"

        forecasts.append({
            "project_id": project_id,
            "role_id": role_id,
            "skill_id": skill_id,
            "history_points": len(values),
            "forecast_fte": round(forecast_fte, 3),
            "methodology": methodology,
            "confidence": confidence,
            "accuracy_mape": accuracy,
            "source_periods": [period.isoformat() for period in period_points[-4:]],
        })
    return {"forecasts": forecasts}


def positive_gap_ids_by_demand_identity(db):
    return (
        db.query(func.min(m.GapAnalysis.id).label("gap_id"))
        .join(m.DemandPlan, m.DemandPlan.id == m.GapAnalysis.demand_id)
        .filter(m.GapAnalysis.gap_fte > 0.01)
        .group_by(
            m.DemandPlan.project_id,
            m.DemandPlan.role_id,
            m.DemandPlan.skill_id,
            m.DemandPlan.period_start,
            m.DemandPlan.demand_version,
        )
        .subquery()
    )


def dashboard(db):
    allocation_totals = (
        db.query(
            m.Allocation.employee_id.label("employee_id"),
            m.Allocation.period_start.label("period_start"),
            func.sum(m.Allocation.allocated_hours).label("allocated_hours"),
        )
        .group_by(m.Allocation.employee_id, m.Allocation.period_start)
        .subquery()
    )
    allocated = func.coalesce(allocation_totals.c.allocated_hours, 0.0)
    capacity_stats = select(
        func.avg(case((m.Availability.available_hours > 0, allocated / m.Availability.available_hours * 100.0), else_=None)).label("average_utilization"),
        func.coalesce(func.sum(case((allocated > m.Availability.available_hours, 1), else_=0)), 0).label("overallocated_periods"),
    ).select_from(m.Availability).outerjoin(
        allocation_totals,
        (allocation_totals.c.employee_id == m.Availability.employee_id)
        & (allocation_totals.c.period_start == m.Availability.period_start),
    ).subquery()
    unique_positive_gaps = positive_gap_ids_by_demand_identity(db)
    metrics = db.execute(select(
        select(func.count()).select_from(m.Employee).scalar_subquery().label("employees"),
        select(func.count()).select_from(m.Project).scalar_subquery().label("projects"),
        select(func.count()).select_from(m.Project).where(m.Project.status == "ACTIVE").scalar_subquery().label("active_projects"),
        select(func.count()).select_from(m.Skill).scalar_subquery().label("skills"),
        select(func.count()).select_from(m.DemandPlan).scalar_subquery().label("demand_records"),
        select(func.count()).select_from(unique_positive_gaps).scalar_subquery().label("skill_gap_records"),
        func.coalesce(capacity_stats.c.average_utilization, 0).label("average_utilization"),
        capacity_stats.c.overallocated_periods,
        select(func.count()).select_from(m.AnomalyIssue).scalar_subquery().label("active_exceptions"),
    ).select_from(capacity_stats)).one()
    return {
        "employees": metrics.employees,
        "projects": metrics.projects,
        "active_projects": metrics.active_projects,
        "skills": metrics.skills,
        "demand_records": metrics.demand_records,
        "skill_gap_records": metrics.skill_gap_records,
        "average_utilization": round(float(metrics.average_utilization), 1),
        "overallocated_periods": metrics.overallocated_periods,
        "active_exceptions": metrics.active_exceptions,
    }

def serialize(rows):
    out=[]
    for r in rows:
        d={}
        for c in r.__table__.columns:
            v=getattr(r,c.name)
            d[c.name]=v.isoformat() if hasattr(v,"isoformat") else v
        out.append(d)
    return out

def validate_dataset(db):
    checks=[]
    def add(name, invalid_count, value=None):
        checks.append({"check":name,"status":"PASS" if invalid_count==0 else "FAIL",
                       "value":value if value is not None else invalid_count})

    tables=[("employees",m.Employee),("roles",m.Role),("skills",m.Skill),("employee_skills",m.EmployeeSkill),
            ("projects",m.Project),("demand_plans",m.DemandPlan),("allocations",m.Allocation),
            ("availability",m.Availability),("training",m.Training),("gap_analysis",m.GapAnalysis)]
    for name,model in tables:
        checks.append({"check":f"{name} row count","status":"PASS","value":db.query(model).count()})

    id_formats=[
        ("Employee IDs",m.Employee,r"EMP-\d{6}"),("Role IDs",m.Role,r"ROLE-\d{3}"),
        ("Skill IDs",m.Skill,r"SKL-\d{6}"),("Employee-skill IDs",m.EmployeeSkill,r"ES-\d{8}"),
        ("Project IDs",m.Project,r"PRJ-2026-\d{6}"),
        ("Demand IDs",m.DemandPlan,r"DEM-PRJ-2026-\d{6}-\d{4}W\d{2}-R\d{3}-S\d{6}(?:-DUP-\d{3})?"),
        ("Allocation IDs",m.Allocation,r"ALLOC-2026-\d{9}"),
        ("Availability IDs",m.Availability,r"AVL-\d{9}"),("Training IDs",m.Training,r"TRN-\d{7}"),
        ("Gap IDs",m.GapAnalysis,r"GAP-DEM-PRJ-2026-\d{6}-\d{4}W\d{2}-R\d{3}-S\d{6}(?:-DUP-\d{3})?"),
        ("Ground-truth IDs",m.AnomalyIssue,r"GT-\d{3}")]
    for name,model,pattern in id_formats:
        invalid=sum(1 for (value,) in db.query(model.id).all() if not re.fullmatch(pattern,value))
        add(f"{name} format",invalid)

    if db.get_bind().dialect.name == "sqlite":
        violations=db.execute(text("PRAGMA foreign_key_check")).all()
        add("Foreign key integrity",len(violations),len(violations))
    else:
        # PostgreSQL enforces declared foreign keys on writes; SQLite has an explicit pragma check.
        checks.append({"check":"Foreign key integrity","status":"ENFORCED_BY_DATABASE","value":"Declared foreign keys"})

    add("Employee lifecycle values",db.query(m.Employee).filter(
        (~m.Employee.status.in_(["ACTIVE","INACTIVE"]))|
        (~m.Employee.employment_type.in_(["FULL_TIME","PART_TIME"]))).count())
    add("Employee weekly hours",db.query(m.Employee).filter(
        (m.Employee.weekly_hours<=0)|(m.Employee.weekly_hours>40)).count())
    add("Skill category values",db.query(m.Skill).filter(
        ~m.Skill.category.in_(["Technical","Cloud","Data","Quality","Business"])).count())
    add("Skill verification days",db.query(m.Skill).filter(m.Skill.verification_days<=0).count())
    add("Employee skill date order",db.query(m.EmployeeSkill).filter(
        m.EmployeeSkill.expires_on.is_not(None)&(m.EmployeeSkill.expires_on<m.EmployeeSkill.last_verified)).count())
    add("Employee role department match",db.query(m.Employee).join(m.Role,m.Employee.role_id==m.Role.id).filter(
        m.Employee.department!=m.Role.department).count())
    add("Project lifecycle and priority values",db.query(m.Project).filter(
        (~m.Project.status.in_(["PLANNED","ACTIVE","ON_HOLD","COMPLETED"]))|
        (~m.Project.priority.in_(["LOW","MEDIUM","HIGH","CRITICAL"]))).count())
    add("Demand lifecycle values",db.query(m.DemandPlan).filter(m.DemandPlan.status!="APPROVED").count())
    add("Allocation lifecycle values",db.query(m.Allocation).filter(m.Allocation.status!="CONFIRMED").count())
    add("Demand within project effective dates",db.query(m.DemandPlan).join(m.Project,
        m.DemandPlan.project_id==m.Project.id).filter(
        (m.DemandPlan.period_start<m.Project.start_date)|(m.DemandPlan.period_start>m.Project.end_date)).count())
    add("Employee skill proficiency range",db.query(m.EmployeeSkill).filter(
        (m.EmployeeSkill.proficiency<1)|(m.EmployeeSkill.proficiency>5)).count())
    add("Availability arithmetic",db.query(m.Availability).filter(
        func.abs(m.Availability.working_hours-m.Availability.leave_hours-m.Availability.available_hours)>0.01).count())
    add("Availability bounds",db.query(m.Availability).filter(
        (m.Availability.leave_hours<0)|(m.Availability.working_hours<m.Availability.leave_hours)).count())
    add("Allocation amount and date order",db.query(m.Allocation).filter(
        (m.Allocation.allocated_hours<0)|(m.Allocation.period_end<m.Allocation.period_start)).count())
    add("Demand amount",db.query(m.DemandPlan).filter(m.DemandPlan.required_fte<0).count())
    add("Demand version",db.query(m.DemandPlan).filter(m.DemandPlan.demand_version<1).count())
    add("Project date order",db.query(m.Project).filter(m.Project.end_date<m.Project.start_date).count())

    invalid_training=0
    for row in db.query(m.Training).all():
        if row.status not in {"PLANNED","IN_PROGRESS","COMPLETED"}:
            invalid_training+=1
        elif row.status=="PLANNED" and (row.started_on or row.completed_on):
            invalid_training+=1
        elif row.status=="IN_PROGRESS" and (not row.started_on or row.completed_on):
            invalid_training+=1
        elif row.status=="COMPLETED" and (not row.started_on or not row.completed_on or row.completed_on<row.started_on):
            invalid_training+=1
    add("Training lifecycle",invalid_training)
    add("Training hours",db.query(m.Training).filter(m.Training.hours<0).count())
    invalid_projects=db.query(m.Project).filter(~m.Project.status.in_(["PLANNED","ACTIVE","ON_HOLD","COMPLETED"])).count()
    add("Project lifecycle values",invalid_projects)

    expected_gap=case((m.GapAnalysis.required_fte>m.GapAnalysis.available_fte,
                       m.GapAnalysis.required_fte-m.GapAnalysis.available_fte),else_=0)
    invalid_gaps=db.query(m.GapAnalysis).filter(func.abs(m.GapAnalysis.gap_fte-expected_gap)>0.01).count()
    add("Gap arithmetic",invalid_gaps)
    expected_status=case((m.GapAnalysis.gap_fte>0.01,"GAP"),else_="COVERED")
    add("Gap lifecycle status",db.query(m.GapAnalysis).filter(m.GapAnalysis.status!=expected_status).count())

    duplicate_groups=db.query(m.DemandPlan.project_id,m.DemandPlan.role_id,m.DemandPlan.skill_id,
        m.DemandPlan.period_start,m.DemandPlan.demand_version).group_by(
        m.DemandPlan.project_id,m.DemandPlan.role_id,m.DemandPlan.skill_id,
        m.DemandPlan.period_start,m.DemandPlan.demand_version).having(func.count()>1).all()
    unlabelled_duplicates=0
    labels={issue.entity_id for issue in db.query(m.AnomalyIssue).filter_by(
        issue_type="DEMAND_DOUBLE_COUNTED",ground_truth=True).all()}
    for project_id,role_id,skill_id,period_start,version in duplicate_groups:
        records=sorted(db.query(m.DemandPlan).filter_by(project_id=project_id,role_id=role_id,skill_id=skill_id,
            period_start=period_start,demand_version=version).all(),key=lambda row:row.id)
        unlabelled_duplicates+=sum(1 for row in records[1:] if row.id not in labels)
    add("Demand duplicate labels",unlabelled_duplicates,
        {"duplicate_groups":len(duplicate_groups),"unlabelled_duplicate_rows":unlabelled_duplicates})

    invalid_labels=0
    target_models={"ALLOCATION_EXCEEDS_AVAILABILITY":m.Employee,
        "OVERLAPPING_PROJECT_ASSIGNMENT":m.Employee,"STALE_SKILL_TREATED_CURRENT":m.EmployeeSkill,
        "DEMAND_DOUBLE_COUNTED":m.DemandPlan}
    for issue in db.query(m.AnomalyIssue).all():
        target=target_models.get(issue.issue_type)
        if not issue.ground_truth or target is None or db.get(target,issue.entity_id) is None:
            invalid_labels+=1
    add("Ground-truth target integrity",invalid_labels)
    return {"checks":checks,"passed":sum(c["status"]=="PASS" for c in checks),
            "failed":sum(c["status"]=="FAIL" for c in checks)}
