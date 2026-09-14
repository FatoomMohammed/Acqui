# AcquiPredict — Predict. Explain. Prevent.

# AcquiPredict — Predictive Analytics System for Early Detection of Land Acquisition Delays

## Working prototype
This SIH 2026 prototype demonstrates an early-warning workflow for land-acquisition cases:

**Enter → Predict → Explain → Alert → Recommend → Prevent**

### Implemented in this version
- Risk score with Low / Medium / High classification
- Estimated delay in days
- Dashboard with automatic priority ordering
- Search and filters by state, risk and acquisition stage
- Project/case detail view
- Explainable risk drivers
- Document completeness checklist
- Early-warning/priority alert center
- Recommended preventive actions
- What-if scenario simulation
- Analytics by acquisition stage and infrastructure type
- **GIS-enabled risk map** (Leaflet + OpenStreetMap) plotting every case by district, colour-coded by risk
- **Role-based access** — Administrator / Field Officer / Viewer, switchable live from the header, gating case creation, simulation and export
- **Audit trail** — every case creation, simulation and export is logged with timestamp, role and detail
- CSV export and JSON API (for integration with existing land-acquisition systems)
- SQLite local database
- Responsive web interface
- Real trained ML model: scikit-learn Random Forest Regressor (200 trees), not hand-set weights

## Data and ML honesty
The prediction engine is a real trained **scikit-learn Random Forest Regressor** (`model.py`), not hand-set weights. It is trained on a domain-calibrated **synthetic** dataset of 3,000 land-acquisition cases (80/20 train/test split) that encodes the delay relationships described in the problem statement, because authorized historical land-acquisition records were not available for this prototype.

Explainability is derived from the forest's own learned `feature_importances_`, combined with each case's signal strength, to rank the top delay drivers per case — shown on the case detail page and the `/model-info` page (which also reports the test-set MAE).

For production deployment: swap `generate_synthetic_dataset()`'s output for authorized historical case records and re-run `train_model()` — no other code changes are required. Keep final thresholds (Low/Medium/High cut-offs) data-driven once real outcomes are available.

## Future production enhancements
- Authorized integration with relevant government systems through APIs
- Parcel-level GeoJSON GIS layers (BhoomiRashi / state land-record systems) in place of district centroids
- Automated email/SMS/notification workflows
- Historical timeline and longitudinal trend analytics
- State/UT and district comparative dashboards at national scale
- Model monitoring, calibration, drift detection and scheduled retraining once real case outcomes are available
- Full authentication (current roles are session-based for demo purposes)
- Richer explainability (e.g. SHAP values) once the model is trained on real data at scale

## Run
```bash
pip install -r requirements.txt
python app.py
```
Open `http://127.0.0.1:5000` (internet connection needed only for the GIS Map page, which loads OpenStreetMap tiles from a CDN — every other page works fully offline).

## Judge-safe statement
> “AcquiPredict trains a real scikit-learn Random Forest Regressor to predict land-acquisition delay and derives its explanations directly from the model’s learned feature importances. It is trained on a domain-calibrated synthetic dataset because authorized historical case data wasn’t available for this prototype — the training pipeline is built to retrain unchanged on real historical records. Around that core model sits the full workflow: risk classification, GIS map, document checks, recommendations, alerts, what-if simulation, role-based access and an audit trail.”
