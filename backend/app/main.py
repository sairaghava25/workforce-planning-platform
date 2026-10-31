import csv, io, json
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session
from .database import Base, engine, get_db
from . import models as m
from .schemas import GenerateRequest
from .services import generate, analyze, dashboard, serialize, validate_dataset, recommendation_for_gap, forecast_demand, evaluate_anomaly_detection, positive_gap_ids_by_demand_identity

Base.metadata.create_all(bind=engine)
app=FastAPI(title="Workforce Planning API",version="1.0.0",description="Database-driven workforce demand, capacity and skill gap analysis.")

@app.get("/api/health")
def health(): return {"status":"ok"}

@app.post("/api/generator/run")
def run_generator(payload:GenerateRequest,db:Session=Depends(get_db)):
    try:
        return {"message":"Synthetic dataset generated","counts":generate(db,payload)}
    except Exception as e:
        db.rollback(); raise HTTPException(500,str(e))

@app.post("/api/analysis/run")
def run_analysis(db:Session=Depends(get_db)):
    try: return analyze(db)
    except Exception as e:
        db.rollback(); raise HTTPException(500,str(e))

@app.get("/api/dashboard")
def get_dashboard(db:Session=Depends(get_db)): return dashboard(db)

@app.get("/api/forecast")
def get_forecast(db:Session=Depends(get_db)):
    return forecast_demand(db)

@app.get("/api/anomaly-evaluation")
def anomaly_evaluation(db:Session=Depends(get_db)):
    return evaluate_anomaly_detection(db)

@app.get("/api/employees")
def employees(limit:int=100,offset:int=0,db:Session=Depends(get_db)):
    return serialize(db.query(m.Employee).offset(offset).limit(min(limit,500)).all())

@app.get("/api/projects")
def projects(limit:int=100,offset:int=0,db:Session=Depends(get_db)):
    return serialize(db.query(m.Project).offset(offset).limit(min(limit,500)).all())

@app.get("/api/demand")
def demand(limit:int=100,db:Session=Depends(get_db)):
    return serialize(db.query(m.DemandPlan).limit(min(limit,500)).all())

@app.get("/api/gaps")
def gaps(limit:int=200,offset:int=0,db:Session=Depends(get_db)):
    unique_gap_ids = positive_gap_ids_by_demand_identity(db)
    return serialize(
        db.query(m.GapAnalysis)
        .filter(m.GapAnalysis.id.in_(db.query(unique_gap_ids.c.gap_id)))
        .order_by(m.GapAnalysis.id)
        .offset(offset)
        .limit(min(limit,1000))
        .all()
    )

@app.get("/api/recommendations")
def recommendations(db:Session=Depends(get_db)):
    return [recommendation_for_gap(db,g) for g in
        db.query(m.GapAnalysis).filter(m.GapAnalysis.gap_fte>0.01).limit(500).all()]

@app.get("/api/exceptions")
def exceptions(db:Session=Depends(get_db)):
    return serialize(db.query(m.AnomalyIssue).all())

@app.get("/api/validation")
def validation(db:Session=Depends(get_db)):
    return validate_dataset(db)

@app.get("/api/exports/{entity}")
def export_entity(entity:str,db:Session=Depends(get_db)):
    mapping={"employees":m.Employee,"roles":m.Role,"skills":m.Skill,"employee_skills":m.EmployeeSkill,
      "projects":m.Project,"demand":m.DemandPlan,"allocations":m.Allocation,"availability":m.Availability,
      "training":m.Training,"gaps":m.GapAnalysis,"ground_truth":m.AnomalyIssue,"audit":m.AuditEvent}
    if entity not in mapping: raise HTTPException(404,"Unknown export entity")
    rows=serialize(db.query(mapping[entity]).all())
    if entity=="ground_truth":
        rows=[{"case_id":r["id"],"issue_type":r["issue_type"],"entity_id":r["entity_id"],"expected_label":r["ground_truth"],"details":r["details"]} for r in rows]
    if not rows: return JSONResponse({"message":"No records available. Generate data first."},status_code=404)
    output=io.StringIO(); writer=csv.DictWriter(output,fieldnames=list(rows[0].keys())); writer.writeheader(); writer.writerows(rows)
    return StreamingResponse(iter([output.getvalue()]),media_type="text/csv",headers={"Content-Disposition":f"attachment; filename={entity}.csv"})
