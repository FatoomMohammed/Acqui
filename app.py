from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file, flash, session
import sqlite3, os, csv, io
from datetime import datetime
from model import load_model, predict_risk, STAGES
import geo

app = Flask(__name__)
app.secret_key = 'acquipredict-local-key'
BASE = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE, 'data', 'projects.db')
model = load_model()

ROLES = ['Administrator', 'Field Officer', 'Viewer']
ROLE_PERMISSIONS = {
    'Administrator': {'add_case', 'simulate', 'export'},
    'Field Officer': {'add_case', 'simulate'},
    'Viewer': set(),
}


def current_role():
    return session.get('role', 'Administrator')


def can(action):
    return action in ROLE_PERMISSIONS.get(current_role(), set())


@app.context_processor
def inject_role():
    return dict(current_role=current_role(), roles=ROLES, can=can)


@app.route('/set-role', methods=['POST'])
def set_role():
    role = request.form.get('role', 'Administrator')
    if role in ROLES:
        session['role'] = role
        flash(f'Active role switched to {role}.')
    return redirect(request.referrer or url_for('dashboard'))

DOCS = [
    ('ownership_doc', 'Ownership document'), ('land_record', 'Land record'),
    ('compensation_doc', 'Compensation document'), ('approval_doc', 'Approval document'),
    ('notification_doc', 'Notification document')
]
# STAGES is imported from model.py so the app and the trained model always agree on stage encoding.
INFRA = ['National Highway','Metro / Rail','Airport','Water Infrastructure','Renewable Energy','Industrial Corridor','Urban Development','Other']


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, state TEXT DEFAULT 'Telangana', district TEXT,
        infrastructure_type TEXT DEFAULT 'National Highway', acquisition_stage TEXT DEFAULT 'Land Verification',
        approval_delay_days INTEGER DEFAULT 0, compensation_pct REAL DEFAULT 0, legal_disputes INTEGER DEFAULT 0,
        land_dispute_flag INTEGER DEFAULT 0, rr_completion_pct REAL DEFAULT 0, avg_response_days INTEGER DEFAULT 0,
        land_area_acres REAL DEFAULT 0, affected_families INTEGER DEFAULT 0,
        ownership_doc INTEGER DEFAULT 1, land_record INTEGER DEFAULT 1, compensation_doc INTEGER DEFAULT 1,
        approval_doc INTEGER DEFAULT 1, notification_doc INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    cols = {r['name'] for r in conn.execute('PRAGMA table_info(projects)').fetchall()}
    additions = {
        'state': "TEXT DEFAULT 'Telangana'", 'updated_at': "TEXT DEFAULT CURRENT_TIMESTAMP"
    }
    for c, typ in additions.items():
        if c not in cols:
            conn.execute(f'ALTER TABLE projects ADD COLUMN {c} {typ}')
    conn.execute('''CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT DEFAULT CURRENT_TIMESTAMP,
        role TEXT, action TEXT, detail TEXT
    )''')
    conn.commit(); conn.close()


def log_action(action, detail=''):
    conn = get_db()
    conn.execute('INSERT INTO audit_log (ts, role, action, detail) VALUES (?,?,?,?)',
                 (datetime.now().isoformat(timespec='seconds'), current_role(), action, detail))
    conn.commit(); conn.close()


def seed_if_empty():
    conn = get_db()
    if conn.execute('SELECT COUNT(*) FROM projects').fetchone()[0] == 0:
        sample = [
            ('NH-44 Widening','Maharashtra','Nagpur','National Highway','Compensation Processing',20,80,0,0,90,5,45,120,1,1,1,1,1),
            ('Metro Rail Phase 2','Maharashtra','Pune','Metro / Rail','Legal Review',95,30,3,1,40,25,12,890,0,1,0,0,1),
            ('Irrigation Canal Ext.','Maharashtra','Solapur','Water Infrastructure','Land Verification',150,15,5,1,20,38,200,1500,0,0,0,1,1),
            ('Solar Park Site A','Maharashtra','Kolhapur','Renewable Energy','Acquisition Complete',10,95,0,0,100,3,300,40,1,1,1,1,1),
            ('Urban Ring Road','Telangana','Hyderabad','Urban Development','Notification',55,55,1,0,60,14,85,260,1,1,0,1,1),
        ]
        conn.executemany('''INSERT INTO projects
        (name,state,district,infrastructure_type,acquisition_stage,approval_delay_days,compensation_pct,legal_disputes,land_dispute_flag,rr_completion_pct,avg_response_days,land_area_acres,affected_families,ownership_doc,land_record,compensation_doc,approval_doc,notification_doc)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', sample)
        conn.commit()
    conn.close()


def enrich(row):
    d = dict(row)
    d['document_fields'] = [x[0] for x in DOCS]
    d['missing_docs'] = [label for key, label in DOCS if not d.get(key, 1)]
    d['doc_complete_pct'] = round(100 * (len(DOCS) - len(d['missing_docs'])) / len(DOCS), 1)
    risk, drivers, pred_days, level = predict_risk(d, model=model)
    d.update(risk=risk, drivers=drivers, pred_days=pred_days, level=level)
    actions = []
    if d['missing_docs']:
        actions.append('Complete missing documents: ' + ', '.join(d['missing_docs'][:2]))
    if d.get('legal_disputes', 0) > 0 or d.get('land_dispute_flag', 0):
        actions.append('Prioritize ownership and legal verification')
    if d.get('compensation_pct', 0) < 70:
        actions.append('Review pending compensation cases')
    if d.get('approval_delay_days', 0) > 30:
        actions.append('Escalate pending approvals')
    if d.get('rr_completion_pct', 0) < 60:
        actions.append('Review R&R progress and pending cases')
    if not actions:
        actions.append('Continue routine monitoring')
    d['recommendations'] = actions[:4]
    d['alert'] = level == 'High'
    return d


def all_projects():
    conn = get_db(); rows = conn.execute('SELECT * FROM projects').fetchall(); conn.close()
    return sorted([enrich(r) for r in rows], key=lambda x: x['risk'], reverse=True)


def parse_form(f):
    def num(k, cast=float, default=0):
        try: return cast(f.get(k, default))
        except (TypeError, ValueError): return default
    return (
        f.get('name','').strip(), f.get('state','Telangana').strip(), f.get('district','').strip(),
        f.get('infrastructure_type','National Highway'), f.get('acquisition_stage','Land Verification'),
        num('approval_delay_days', int), num('compensation_pct'), num('legal_disputes', int), int(f.get('land_dispute_flag',0)),
        num('rr_completion_pct'), num('avg_response_days',int), num('land_area_acres'), num('affected_families',int),
        int(f.get('ownership_doc',0)), int(f.get('land_record',0)), int(f.get('compensation_doc',0)), int(f.get('approval_doc',0)), int(f.get('notification_doc',0))
    )


@app.route('/')
def dashboard():
    projects = all_projects()
    state = request.args.get('state','').strip()
    level = request.args.get('level','').strip()
    stage = request.args.get('stage','').strip()
    search = request.args.get('q','').strip().lower()
    filtered = [p for p in projects if (not state or p['state']==state) and (not level or p['level']==level) and (not stage or p['acquisition_stage']==stage) and (not search or search in p['name'].lower() or search in (p['district'] or '').lower())]
    high = sum(p['level']=='High' for p in filtered); medium = sum(p['level']=='Medium' for p in filtered); low = sum(p['level']=='Low' for p in filtered)
    avg = round(sum(p['risk'] for p in filtered)/len(filtered),1) if filtered else 0
    avg_delay = round(sum(p['pred_days'] for p in filtered)/len(filtered),1) if filtered else 0
    districts = {}
    for p in filtered:
        districts.setdefault(p['district'] or 'Unknown', {'total':0,'high':0,'risk':0})
        districts[p['district'] or 'Unknown']['total'] += 1; districts[p['district'] or 'Unknown']['risk'] += p['risk']; districts[p['district'] or 'Unknown']['high'] += p['level']=='High'
    district_rows = sorted([{'name':k,'total':v['total'],'high':v['high'],'avg':round(v['risk']/v['total'],1)} for k,v in districts.items()], key=lambda x:x['avg'], reverse=True)
    states = sorted({p['state'] for p in projects if p['state']})
    return render_template('dashboard.html', projects=filtered, all_count=len(projects), high=high, medium=medium, low=low, avg=avg, avg_delay=avg_delay, district_rows=district_rows, states=states, stages=STAGES, filters={'state':state,'level':level,'stage':stage,'q':search})


@app.route('/project/new', methods=['GET','POST'])
def new_project():
    if not can('add_case'):
        flash(f'Your role ({current_role()}) has read-only access. Switch to Administrator or Field Officer to add a case.')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        vals = parse_form(request.form)
        if not vals[0] or not vals[2]:
            flash('Project name and district are required.')
            return render_template('new_project.html', stages=STAGES, infra=INFRA, form=request.form)
        conn=get_db(); cur=conn.execute('''INSERT INTO projects (name,state,district,infrastructure_type,acquisition_stage,approval_delay_days,compensation_pct,legal_disputes,land_dispute_flag,rr_completion_pct,avg_response_days,land_area_acres,affected_families,ownership_doc,land_record,compensation_doc,approval_doc,notification_doc,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', vals + (datetime.now().isoformat(timespec='seconds'),)); pid=cur.lastrowid; conn.commit(); conn.close()
        log_action('Case created', f'{vals[0]} ({vals[2]}, {vals[1]})')
        flash('Case analyzed successfully.')
        return redirect(url_for('project_detail', project_id=pid))
    return render_template('new_project.html', stages=STAGES, infra=INFRA, form={})


@app.route('/project/<int:project_id>')
def project_detail(project_id):
    conn=get_db(); row=conn.execute('SELECT * FROM projects WHERE id=?',(project_id,)).fetchone(); conn.close()
    if not row: return 'Project not found',404
    return render_template('project_detail.html', p=enrich(row), docs=DOCS)


@app.route('/project/<int:project_id>/what-if', methods=['POST'])
def what_if(project_id):
    if not can('simulate'):
        flash(f'Your role ({current_role()}) cannot run simulations. Switch to Administrator or Field Officer.')
        return redirect(url_for('project_detail', project_id=project_id))
    conn=get_db(); row=conn.execute('SELECT * FROM projects WHERE id=?',(project_id,)).fetchone(); conn.close()
    if not row: return 'Project not found',404
    d=dict(row)
    numeric = ['approval_delay_days','compensation_pct','legal_disputes','rr_completion_pct','avg_response_days','land_area_acres','affected_families']
    for k in numeric:
        if request.form.get(k,'') != '':
            try: d[k]=float(request.form[k])
            except ValueError: pass
    for k in ['land_dispute_flag','ownership_doc','land_record','compensation_doc','approval_doc','notification_doc']:
        if k in request.form: d[k]=int(request.form[k])
    if request.form.get('acquisition_stage'): d['acquisition_stage']=request.form['acquisition_stage']
    result=enrich(d); current=enrich(row)
    result['current_risk']=current['risk']; result['risk_change']=round(result['risk']-current['risk'],1)
    result['current_days']=current['pred_days']; result['days_change']=round(result['pred_days']-current['pred_days'],1)
    log_action('What-if simulation run', f'{current["name"]} · risk {current["risk"]}→{result["risk"]}')
    return render_template('what_if.html', p=current, result=result, stages=STAGES)


@app.route('/analytics')
def analytics():
    projects=all_projects()
    stage_map={}
    infra_map={}
    for p in projects:
        stage_map.setdefault(p['acquisition_stage'], []).append(p['risk'])
        infra_map.setdefault(p['infrastructure_type'], []).append(p['risk'])
    stage_rows=sorted([{'name':k,'count':len(v),'avg':round(sum(v)/len(v),1)} for k,v in stage_map.items()], key=lambda x:x['avg'], reverse=True)
    infra_rows=sorted([{'name':k,'count':len(v),'avg':round(sum(v)/len(v),1)} for k,v in infra_map.items()], key=lambda x:x['avg'], reverse=True)
    state_map={}
    driver_map={}
    for p in projects:
        state_map.setdefault(p.get('state') or 'Unknown', []).append(p['risk'])
        for driver in p['drivers'][:2]: driver_map[driver]=driver_map.get(driver,0)+1
    state_rows=sorted([{'name':k,'count':len(v),'avg':round(sum(v)/len(v),1)} for k,v in state_map.items()], key=lambda x:x['avg'], reverse=True)
    driver_rows=sorted([{'name':k,'count':v} for k,v in driver_map.items()], key=lambda x:x['count'], reverse=True)[:8]
    total=len(projects)
    data_quality=round(sum(p['doc_complete_pct'] for p in projects)/total,1) if total else 0
    return render_template('analytics.html', projects=projects, stage_rows=stage_rows, infra_rows=infra_rows, state_rows=state_rows, driver_rows=driver_rows, data_quality=data_quality)


@app.route('/alerts')
def alerts():
    projects=[p for p in all_projects() if p['level']=='High']
    return render_template('alerts.html', projects=projects)


@app.route('/map')
def gis_map():
    projects = all_projects()
    points = []
    for p in projects:
        lat, lon = geo.locate(p.get('state'), p.get('district'))
        points.append({
            'id': p['id'], 'name': p['name'], 'district': p['district'], 'state': p['state'],
            'lat': lat, 'lon': lon, 'risk': p['risk'], 'level': p['level'],
            'pred_days': p['pred_days'], 'driver': p['drivers'][0], 'stage': p['acquisition_stage']
        })
    high = sum(p['level']=='High' for p in projects); medium = sum(p['level']=='Medium' for p in projects); low = sum(p['level']=='Low' for p in projects)
    return render_template('map.html', points=points, high=high, medium=medium, low=low, total=len(projects))


@app.route('/audit')
def audit():
    conn = get_db()
    rows = conn.execute('SELECT * FROM audit_log ORDER BY id DESC LIMIT 200').fetchall()
    conn.close()
    return render_template('audit.html', logs=rows)


@app.route('/api/projects')
def api_projects():
    return jsonify({'projects': all_projects(), 'generated_at': datetime.now().isoformat(timespec='seconds')})


@app.route('/export/csv')
def export_csv():
    if not can('export'):
        flash(f'Your role ({current_role()}) cannot export data. Switch to Administrator.')
        return redirect(url_for('dashboard'))
    log_action('CSV export', 'Full case list exported')
    projects=all_projects(); out=io.StringIO(); writer=csv.writer(out)
    writer.writerow(['Project','State','District','Infrastructure','Stage','Risk Score','Risk Level','Predicted Delay (days)','Document Completeness','Main Risk Factor'])
    for p in projects:
        writer.writerow([p['name'],p['state'],p['district'],p['infrastructure_type'],p['acquisition_stage'],p['risk'],p['level'],p['pred_days'],p['doc_complete_pct'],p['drivers'][0]])
    mem=io.BytesIO(out.getvalue().encode('utf-8')); mem.seek(0)
    return send_file(mem, mimetype='text/csv', as_attachment=True, download_name='acquipredict_cases.csv')


@app.route('/model-info')
def model_info():
    return render_template('model_info.html', model=model, feature_count=len(model.get('features', [])), model_note=model.get('note','Lightweight explainable prediction engine'))

if __name__=='__main__':
    init_db(); seed_if_empty(); app.run(debug=True, port=5000)
