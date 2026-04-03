# ML Personalization Pipeline - Thesis Redesign Summary

## ✅ Completed Work

### 1. **Completely Rewritten Section 5: Multi-User Personalization**
**File:** `docs/content/sec5_tinyML.tex`

**Old Focus:** TinyML thermal comfort prediction (ESP32 deployment)  
**New Focus:** Multi-user behavior learning & personalization pipeline (backend server)

---

## 📐 New Architecture Diagrams (TikZ)

### Diagram 1: System Architecture (`fig:personalization-architecture`)
- Shows complete integration with HERA multi-agent system
- UserContext injection layer
- Per-user ML models with lazy loading
- Async behavior logging pipeline
- Conflict resolution engine

### Diagram 2: Data Pipeline (`fig:data-pipeline`)
- Real-time behavior logging (blue/green arrows)
- Offline training pipeline (orange arrows)
- Model export and reload (red arrows)
- Feedback loop for inference

### Diagram 3: Integration Flow (`fig:integration-flow`)
- Request flow from Telegram through orchestrator
- UserContext injection (purple)
- ML inference (red)
- Device control execution (blue)
- Asynchronous logging (gray)

### Diagram 4: Learning Cycle (`fig:learning-cycle`)
- 6-step continuous improvement loop
- User actions → Logging → Training → Deployment → Inference → Suggestions → Feedback

---

## 📊 New Comparison Tables

### Table 1: Rule-Based vs ML Boundary (`tab:rule-ml-boundary`)
Clarifies separation between:
- Rule-based threshold system (safety bounds)
- ML personalization pipeline (learned preferences)
- HERA LLM agents (NLU/NLG)

### Table 2: Model Architecture Comparison (`tab:model-comparison`)
Compares 5 candidate models:
- Logistic Regression (baseline)
- Random Forest (interpretable)
- **LightGBM (recommended primary)**
- MLP (if data grows large)
- LSTM/GRU (not recommended)

### Table 3: Database Schema (`tab:database-schema`)
5 new tables:
- `users` - User identity mapping
- `user_behaviors` - Behavior logs with env context (JSON)
- `learned_patterns` - Discovered patterns cache
- `suggestion_feedback` - Acceptance/rejection tracking
- `model_metadata` - Version control and metrics

### Table 4: Old vs New ML Approach (`tab:old-vs-new`)
Contrasts 10 aspects:
- Deployment target (ESP32 → Backend server)
- Prediction task (3-class comfort → Multi-task next action + device states)
- User modeling (Single shared → Per-user models)
- Data source (ASHRAE public → Implicit from all actions)
- Model (Tiny MLP → LightGBM)
- Integration (MQTT only → Deep HERA integration)
- Scope (Thermal comfort → All device patterns)
- Actionability (Reactive → Proactive)
- Memory (Strict <100KB → Relaxed MB)
- Training (Manual → Automated nightly)

---

## 📝 New Content Sections

### 1. **Why Personalization Requires ML** (`subsec:1`)
- Limitations of rule-based approaches
- Context dependency, individual differences, temporal patterns
- Clear system boundary table

### 2. **System Architecture Overview** (`sec:personalization-architecture`)
- Complete architecture diagram with 8 key components
- UserContext injection mechanism
- Per-user model rationale
- Conflict resolution strategies (role-based, temporal, compromise, LLM-mediated)

### 3. **Data Pipeline & Feature Engineering** (`sec:data-pipeline`)
- 3 feature groups: Temporal, Environmental, Historical
- 2 prediction tasks: Next action + Preferred device state
- Compact design for fast inference

### 4. **Model Architecture & Training** (`sec:model-training`)
- LightGBM as recommended baseline
- Temporal data splitting (70/15/15)
- Evaluation metrics: Top-3 accuracy, Precision@1, Recall@3, MAE
- Cold start handling (global default → personal model after 50+ interactions)
- Continuous learning (nightly retraining)

### 5. **Integration with HERA** (`sec:hera-integration`)
- UserContext injection flow
- Proactive suggestion mechanism (10-min background inference)
- Multi-user conflict resolution examples

### 6. **Database Schema Extensions** (`sec:database-schema`)
- 5 new PostgreSQL tables
- JSON structure for environmental context
- Flexible schema for future extensions

### 7. **Complete Behavior Learning Cycle**
- Circular feedback loop diagram
- Dual timescales: Real-time (seconds) + Batch (daily)

### 8. **Implementation Roadmap** (`sec:implementation-roadmap`)
- 4-phase deployment (8 weeks total):
  - Phase 1: Data collection (Week 1-2)
  - Phase 2: Model training (Week 3-4)
  - Phase 3: HERA integration (Week 5-6)
  - Phase 4: Proactive suggestions (Week 7-8)
- 4 technical challenges + mitigations:
  - Cold start → Global default model
  - Concept drift → Exponential decay weighting
  - Privacy → Local storage, retention policies
  - Debugging → Feature importance, admin dashboard

### 9. **Related Work & Academic Context**
- Smart home behavior learning (activity recognition, routine mining)
- Recommender systems (Netflix embeddings, context-aware rec)
- Multi-agent personalization (novel contribution)

### 10. **Summary & Contributions**
6 key contributions:
1. Clear separation of concerns
2. Per-user modeling at family scale
3. Hybrid reactive-proactive system
4. LLM-ML integration via UserContext
5. Multi-user conflict resolution
6. Privacy-preserving design

---

## 📚 New References Added

**file:** `docs/style/ref.bib`

1. `cook_smart_homes_2012` - CASAS smart home behavior recognition
2. `roy_routine_mining_2016` - Routine mining in multi-inhabitant environments
3. `netflix_embeddings_2016` - Deep neural networks for YouTube recommendations
4. `context_aware_rec_2015` - Context-aware recommender systems handbook
5. `langchain_agents_2023` - Multi-agent framework documentation

**Removed:**
- ❌ `ashrae_db2_2018` - No longer using thermal comfort dataset
- ❌ `cbe_occupant_survey_2026` - Not relevant to behavior learning approach

---

## 🔧 Files Modified

| File | Change Type | Description |
|------|-------------|-------------|
| `docs/content/sec5_tinyML.tex` | **Complete rewrite** | 950+ lines, all new content |
| `docs/style/ref.bib` | **Updated** | Added 5 new refs, removed 2 old refs |
| `docs/content/sec5_personalization_ending.tex` | **Created then merged** | Temporary file (can delete) |

---

## ⚠️ TODO: Manual Verification Needed

### LaTeX Compilation
**Action Required:** Compile the thesis to verify:
```bash
cd docs
pdflatex -interaction=nonstopmode main.tex
bibtex main
pdflatex -interaction=nonstopmode main.tex
pdflatex -interaction=nonstopmode main.tex
```

**Expected Issues:**
- TikZ compilation may be slow (4 complex diagrams)
- Check for undefined references (should resolve after 2nd pdflatex)
- Verify all citations render correctly

### Visual Inspection
1. **Diagrams:** Check that all 4 TikZ figures render properly
2. **Tables:** Verify table formatting (4 new tables)
3. **References:** Ensure new citations [1-6] appear in bibliography
4. **Section flow:** Read through to check logical flow

### Optional Cleanup
- Delete `docs/content/sec5_personalization_ending.tex` (temporary file)
- Check `docs/image/` folder for old TinyML diagrams (none found in initial scan)

---

## 🎯 Key Architectural Decisions

### 1. **Server-Side vs Edge Deployment**
**Choice:** Backend server (Python)  
**Rationale:** Family smart home doesn't need ESP32 constraints; server has sufficient resources

### 2. **Per-User Models vs Shared Model**
**Choice:** Individual models per user  
**Rationale:** Better personalization for 3-5 users; lazy loading handles memory

### 3. **LightGBM vs Neural Networks**
**Choice:** LightGBM as primary model  
**Rationale:** Best balance for tabular behavioral data; fast training/inference

### 4. **Real-Time vs Batch Learning**
**Choice:** Hybrid approach  
**Rationale:** Real-time logging + nightly batch retraining balances responsiveness with improvement

### 5. **Proactive Suggestions**
**Choice:** Enable with confidence threshold  
**Rationale:** Transforms from reactive executor to proactive assistant

---

## 📈 Impact Summary

**Before (Old TinyML):**
- Narrow use case (thermal comfort only)
- Resource-constrained (ESP32, <100KB)
- Single shared model
- Reactive only
- Overlapped with rule-based thresholds

**After (ML Personalization):**
- Broad value (all user interactions)
- Sufficient resources (backend server)
- Per-user personalized models
- Reactive + Proactive
- Clear separation from rules (safety vs preference)

**Transformation:**
HERA evolves from **command executor** → **adaptive assistant** that learns each family member's preferences and proactively supports daily routines.

---

## 📞 Next Steps (Implementation)

If you want to implement this pipeline:

1. **Week 1-2:** Extend PostgreSQL schema, implement async logging
2. **Week 3-4:** Build feature extraction pipeline, train initial models
3. **Week 5-6:** Create PersonalizationAgent, integrate UserContext
4. **Week 7-8:** Enable proactive suggestions, tune thresholds

**Estimated effort:** 8 weeks (phased deployment with incremental validation)

---

**Redesign Completed:** 2026-04-03  
**Total New Content:** ~950 lines LaTeX, 4 diagrams, 4 tables, 6 citations  
**Files Changed:** 2 (sec5_tinyML.tex, ref.bib)
