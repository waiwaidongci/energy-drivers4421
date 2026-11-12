import csv,io,json
from datetime import datetime
from sqlalchemy import select,inspect,text,update
from fastapi import HTTPException
from src.models import RetrofitHypothesis,HypothesisRevision,DriverFinding,ModelRun
from src.constants.enums import HypothesisStatus,Role
def _revision_dict(r):
    return {'id':r.id,'hypothesis_id':r.hypothesis_id,'version':r.version,'finding_id':r.finding_id,'action':r.action,'verification':r.verification,'status':r.status,'created_by':r.created_by,'created_at':r.created_at.isoformat() if r.created_at else None,'reviewed_by':r.reviewed_by,'reviewed_at':r.reviewed_at.isoformat() if r.reviewed_at else None,'snapshot':r.snapshot}
def _head_dict(h,revisions):
    return {'id':h.id,'title':h.title,'finding_id':h.finding_id,'action':h.action,'verification':h.verification,'status':h.status,'approved_by':h.approved_by,'current_version':h.current_version,'created_at':h.created_at.isoformat() if h.created_at else None,'revisions':revisions}
def list_hypotheses(db,user):
    heads=db.scalars(select(RetrofitHypothesis).order_by(RetrofitHypothesis.id.desc())).all()
    revisions=db.scalars(select(HypothesisRevision).order_by(HypothesisRevision.version.desc())).all()
    grouped={}
    for r in revisions:grouped.setdefault(r.hypothesis_id,[]).append(r)
    readonly=user.role==Role.VIEWER
    out=[]
    for h in heads:
        revs=grouped.get(h.id,[])
        if readonly:revs=[r for r in revs if r.status==HypothesisStatus.APPROVED]
        out.append(_head_dict(h,[_revision_dict(r) for r in revs]))
    return out
def create_hypothesis(db,data,user):
    finding=db.get(DriverFinding,data.finding_id)
    if not finding:raise HTTPException(404,'驱动解释不存在，请先完成研究')
    if db.scalar(select(RetrofitHypothesis).where(RetrofitHypothesis.title==data.title)):raise HTTPException(409,'假设标题已存在')
    item=RetrofitHypothesis(title=data.title,finding_id=data.finding_id,action=data.action,verification=data.verification,status=HypothesisStatus.DRAFT,current_version=1)
    db.add(item);db.flush()
    db.add(HypothesisRevision(hypothesis_id=item.id,version=1,finding_id=data.finding_id,action=data.action,verification=data.verification,status=HypothesisStatus.DRAFT,created_by=user.email));db.commit();return item
def create_revision(db,id,data,user):
    item=db.scalar(select(RetrofitHypothesis).where(RetrofitHypothesis.id==id).with_for_update())
    if not item:raise HTTPException(404,'改造假设不存在')
    if not db.get(DriverFinding,data.finding_id):raise HTTPException(404,'驱动解释不存在，请先完成研究')
    claimed=db.execute(update(RetrofitHypothesis).where(RetrofitHypothesis.id==id,RetrofitHypothesis.current_version==data.base_version).values(current_version=data.base_version+1),execution_options={'synchronize_session':False})
    if claimed.rowcount==0:
        db.rollback();current=db.get(RetrofitHypothesis,id).current_version
        raise HTTPException(409,f'假设已更新到第{current}版，请刷新后基于最新稿修改')
    revision=HypothesisRevision(hypothesis_id=id,version=data.base_version+1,finding_id=data.finding_id,action=data.action,verification=data.verification,status=HypothesisStatus.DRAFT,created_by=user.email)
    db.add(revision)
    if item.status==HypothesisStatus.DRAFT:item.finding_id,item.action,item.verification=data.finding_id,data.action,data.verification
    db.commit();return revision
def approve_hypothesis(db,id,user,data):
    item=db.scalar(select(RetrofitHypothesis).where(RetrofitHypothesis.id==id).with_for_update())
    if not item:raise HTTPException(404,'改造假设不存在')
    version=data.version if data and data.version else item.current_version
    if version!=item.current_version:raise HTTPException(409,f'审阅的是第{version}版，但假设已更新到第{item.current_version}版；为避免批准他人的新稿，请刷新后重新审阅')
    revision=db.scalar(select(HypothesisRevision).where(HypothesisRevision.hypothesis_id==id,HypothesisRevision.version==version))
    if not revision:raise HTTPException(404,'该版本不存在')
    now=datetime.utcnow();snapshot=build_snapshot(revision,user.email,db,approved_at=now)
    claimed=db.execute(update(HypothesisRevision).where(HypothesisRevision.id==revision.id,HypothesisRevision.status==HypothesisStatus.DRAFT).values(status=HypothesisStatus.APPROVED,reviewed_by=user.email,reviewed_at=now,snapshot=snapshot),execution_options={'synchronize_session':False})
    if claimed.rowcount==0:
        db.rollback();raise HTTPException(409,'该版本已审阅，没有待批准的新稿')
    item.status=HypothesisStatus.APPROVED;item.approved_by=user.email
    item.finding_id,item.action,item.verification=revision.finding_id,revision.action,revision.verification
    db.commit();return item
def build_snapshot(revision,approver,db,approved_at=None):
    finding=db.get(DriverFinding,revision.finding_id)
    if not finding:raise HTTPException(409,'依据的驱动解释不存在，无法冻结批准快照')
    run=db.get(ModelRun,finding.run_id);result=run.result if run else {}
    moment=approved_at or revision.reviewed_at or datetime.utcnow()
    return {'feature':finding.feature,'coefficient':finding.coefficient,'importance_mean':finding.importance_mean,'importance_low':finding.importance_low,'importance_high':finding.importance_high,'repeats':finding.repeats,'action':revision.action,'verification':revision.verification,'approved_by':approver,'approved_at':moment.isoformat(),'version':revision.version,'model_input_fingerprint':result.get('input_fingerprint',''),'selection_fingerprint':result.get('selection_fingerprint','')}
def _latest_approved(db,id):
    return db.scalar(select(HypothesisRevision).where(HypothesisRevision.hypothesis_id==id,HypothesisRevision.status==HypothesisStatus.APPROVED).order_by(HypothesisRevision.version.desc()))
def export_hypothesis(db,id):
    item=db.get(RetrofitHypothesis,id)
    if not item:raise HTTPException(404,'改造假设不存在')
    revision=_latest_approved(db,id)
    if not revision:raise HTTPException(409,'负责人审阅后才能导出')
    return render_csv(revision.snapshot or build_snapshot(revision,revision.reviewed_by or item.approved_by,db))
def export_revision(db,id,version):
    item=db.get(RetrofitHypothesis,id)
    if not item:raise HTTPException(404,'改造假设不存在')
    revision=db.scalar(select(HypothesisRevision).where(HypothesisRevision.hypothesis_id==id,HypothesisRevision.version==version))
    if not revision:raise HTTPException(404,'该版本不存在')
    if revision.status!=HypothesisStatus.APPROVED:raise HTTPException(409,'该版本尚未审阅，不能导出')
    return render_csv(revision.snapshot or build_snapshot(revision,revision.reviewed_by or item.approved_by,db))
def render_csv(snap):
    def safe(value):
        value=str(value);return "'"+value if value.startswith(('=','+','-','@','\t','\r')) else value
    out=io.StringIO();out.write('\ufeff');writer=csv.writer(out);writer.writerow(['feature','coefficient_per_original_unit','permutation_delta_mae','repeat_low','repeat_high','repeated_deltas','action','verification','approved_by','model_input_fingerprint','selection_fingerprint','hypothesis_version','approved_at'])
    writer.writerow([snap['feature'],snap['coefficient'],snap['importance_mean'],snap['importance_low'],snap['importance_high'],json.dumps(snap['repeats']),safe(snap['action']),safe(snap['verification']),safe(snap['approved_by']),snap['model_input_fingerprint'],snap['selection_fingerprint'],snap['version'],snap['approved_at']]);return out.getvalue()
def ensure_revision_schema(db):
    if 'current_version' not in {c['name'] for c in inspect(db.get_bind()).get_columns('retrofit_hypotheses')}:
        db.execute(text('ALTER TABLE retrofit_hypotheses ADD COLUMN current_version INTEGER NOT NULL DEFAULT 1'));db.commit()
def backfill_revisions(db):
    for h in db.scalars(select(RetrofitHypothesis)).all():
        if not h.current_version or h.current_version<1:h.current_version=1
        if db.scalar(select(HypothesisRevision).where(HypothesisRevision.hypothesis_id==h.id,HypothesisRevision.version==1)):continue
        approved=h.status==HypothesisStatus.APPROVED
        revision=HypothesisRevision(hypothesis_id=h.id,version=1,finding_id=h.finding_id,action=h.action,verification=h.verification,status=h.status,created_by='',created_at=h.created_at,reviewed_by=h.approved_by if approved else '',reviewed_at=h.created_at if approved else None)
        if approved:revision.snapshot=build_snapshot(revision,h.approved_by,db,approved_at=h.created_at)
        db.add(revision)
    db.commit()
