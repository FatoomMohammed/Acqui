import os, json, random, pickle
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error

# ---------------------------------------------------------------------------
# AcquiPredict prediction engine - real scikit-learn Random Forest Regressor.
#
# The model is trained on a domain-calibrated SYNTHETIC dataset (see
# generate_synthetic_dataset) that encodes the same delay relationships the
# problem statement describes: approval delays, legal disputes, ownership
# conflicts, compensation/R&R progress, missing documents and stage.
# It is a genuine trained ML model (not hand-set weights) and can be
# retrained on authorized historical land-acquisition records simply by
# replacing generate_synthetic_dataset()'s output with real case data and
# re-running train_model() - no other code changes required.
# ---------------------------------------------------------------------------

FEATURES = [
    'approval_delay_days', 'compensation_pct', 'legal_disputes', 'land_dispute_flag',
    'rr_completion_pct', 'avg_response_days', 'land_area_acres', 'affected_families',
    'missing_document_count'
]
STAGES = [
    'Planning', 'Notification', 'Land Verification', 'Compensation Processing',
    'R&R Processing', 'Legal Review', 'Acquisition', 'Award / Possession', 'Acquisition Complete'
]
FEATURE_LABELS = {
    'approval_delay_days': 'Pending approvals', 'compensation_pct': 'Low compensation completion',
    'legal_disputes': 'Legal disputes', 'land_dispute_flag': 'Ownership / land dispute',
    'rr_completion_pct': 'Incomplete R&R', 'avg_response_days': 'Slow departmental response',
    'land_area_acres': 'Large acquisition area', 'affected_families': 'Large affected population',
    'missing_document_count': 'Missing documents',
}
FEATURE_NAMES = FEATURES + [f'stage_{s}' for s in STAGES]

# Ground-truth generative relationship used ONLY to build the synthetic
# training set - the model itself never sees these coefficients, it learns
# the pattern purely from the (features -> delay_days) examples.
STAGE_TRUTH_EFFECT = {
    'Planning': 0, 'Notification': 5, 'Land Verification': 10,
    'Compensation Processing': 15, 'R&R Processing': 12, 'Legal Review': 18,
    'Acquisition': 12, 'Award / Possession': 8, 'Acquisition Complete': -8
}

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
MODEL_PATH = os.path.join(DATA_DIR, 'risk_model.pkl')
META_PATH = os.path.join(DATA_DIR, 'risk_model_meta.json')


def generate_synthetic_dataset(n=3000, seed=42):
    """Domain-calibrated synthetic training data (stand-in for authorized
    historical case records, which are not available for this prototype)."""
    rng = random.Random(seed)
    rows = []
    for _ in range(n):
        r = {
            'approval_delay_days': rng.randrange(0, 180),
            'compensation_pct': rng.uniform(0, 100),
            'legal_disputes': min(8, max(0, int(rng.expovariate(1 / 1.2)))),
            'land_dispute_flag': rng.randrange(0, 2),
            'rr_completion_pct': rng.uniform(0, 100),
            'avg_response_days': rng.randrange(1, 45),
            'land_area_acres': rng.uniform(1, 500),
            'affected_families': rng.randrange(5, 2000),
            'missing_document_count': rng.randrange(0, 6),
        }
        stage = rng.choice(STAGES)
        r['acquisition_stage'] = stage
        noise = rng.gauss(0, 12)
        y = (
            0.75 * r['approval_delay_days'] + 1.35 * r['legal_disputes'] * 30
            + 42 * r['land_dispute_flag'] - 0.55 * r['compensation_pct']
            - 0.45 * r['rr_completion_pct'] + 1.1 * r['avg_response_days']
            + 0.018 * r['affected_families'] + 14 * r['missing_document_count']
            + STAGE_TRUTH_EFFECT[stage] + noise
        )
        rows.append((r, max(0.0, y)))
    return rows


def stage_vector(stage):
    return [1.0 if stage == s else 0.0 for s in STAGES]


def build_feature_row(project):
    numeric = [float(project.get(f, 0) or 0) for f in FEATURES]
    stage = str(project.get('acquisition_stage', STAGES[0]))
    if stage not in STAGES:
        stage = STAGES[0]
    return numeric + stage_vector(stage)


def train_model():
    os.makedirs(DATA_DIR, exist_ok=True)
    data = generate_synthetic_dataset(3000, 42)
    X = np.array([build_feature_row(r) for r, _ in data])
    y = np.array([yy for _, yy in data])
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    rf = RandomForestRegressor(
        n_estimators=200, max_depth=10, min_samples_leaf=4,
        random_state=42, n_jobs=-1
    )
    rf.fit(X_train, y_train)
    mae = float(mean_absolute_error(y_test, rf.predict(X_test)))

    with open(MODEL_PATH, 'wb') as f:
        pickle.dump(rf, f)

    importances = dict(zip(FEATURE_NAMES, rf.feature_importances_.tolist()))
    meta = {
        'algorithm': 'Random Forest Regressor (scikit-learn)',
        'n_estimators': 200, 'max_depth': 10,
        'trained_rows': len(X_train), 'test_rows': len(X_test),
        'test_mae_days': round(mae, 1),
        'features': FEATURES, 'feature_names': FEATURE_NAMES, 'stages': STAGES,
        'importances': importances,
        'note': ('Trained on a domain-calibrated synthetic dataset of 3,000 land-acquisition '
                 'cases (80/20 train-test split). Designed to be retrained on authorized '
                 'historical case records with no other code changes.'),
    }
    with open(META_PATH, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2)

    print(f'Random Forest trained: {len(X_train)} rows, test MAE = {mae:.1f} days')
    return {'sk_model': rf, **meta}


def load_model():
    if os.path.exists(MODEL_PATH) and os.path.exists(META_PATH):
        try:
            with open(MODEL_PATH, 'rb') as f:
                rf = pickle.load(f)
            with open(META_PATH, encoding='utf-8') as f:
                meta = json.load(f)
            return {'sk_model': rf, **meta}
        except Exception:
            return train_model()
    return train_model()


def predict_days(project, model):
    rf = model['sk_model']
    row = np.array([build_feature_row(project)])
    return max(0.0, float(rf.predict(row)[0]))


def predict_risk(project, model=None, max_days=180):
    if model is None:
        model = load_model()
    doc_keys = ['ownership_doc', 'land_record', 'compensation_doc', 'approval_doc', 'notification_doc']
    missing = sum(1 - int(project.get(k, 1)) for k in doc_keys)
    d = dict(project)
    d['missing_document_count'] = missing

    pred = predict_days(d, model)
    risk = max(0, min(100, pred / max_days * 100))

    # Explainability: rank drivers by (how bad this case's signal is) x
    # (how much the trained forest actually relies on that feature overall).
    signals = {
        'approval_delay_days': max(0, float(d.get('approval_delay_days', 0))),
        'compensation_pct': max(0, 100 - float(d.get('compensation_pct', 0))),
        'legal_disputes': max(0, float(d.get('legal_disputes', 0)) * 30),
        'land_dispute_flag': max(0, float(d.get('land_dispute_flag', 0)) * 60),
        'rr_completion_pct': max(0, 100 - float(d.get('rr_completion_pct', 0))),
        'avg_response_days': max(0, float(d.get('avg_response_days', 0))),
        'land_area_acres': max(0, float(d.get('land_area_acres', 0))),
        'affected_families': max(0, float(d.get('affected_families', 0))),
        'missing_document_count': max(0, float(missing) * 25),
    }
    importances = model.get('importances', {})
    weighted = {f: signals[f] * importances.get(f, 0.01) for f in FEATURES}
    top = [FEATURE_LABELS[f] for f, _ in sorted(weighted.items(), key=lambda z: z[1], reverse=True) if signals[f] > 0][:4]
    if not top:
        top = ['No major risk signal detected']

    level = 'High' if risk >= 66 else ('Medium' if risk >= 33 else 'Low')
    return round(risk, 1), top, round(pred, 1), level


if __name__ == '__main__':
    train_model()
