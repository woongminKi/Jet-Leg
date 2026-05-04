# Jet-Rag Makefile — KPI / 평가 / 회귀 검증 entry-point
#
# W25 D7 — Ragas mini-Ragas (Phase 1) 도입과 함께 신규 작성. DoD ③ "make eval".
# 기존 검증 도구 (golden_batch_smoke.py / monitor_search_slo.py) 도 같은 entry-point 로 묶음.

.PHONY: help eval golden slo

help:
	@echo "Jet-Rag — 평가 / KPI 측정 entry-point"
	@echo ""
	@echo "  make eval     - Ragas mini 검색 품질 측정 (Context Recall / Precision)"
	@echo "                  · evals/golden_v0.4_sonata.csv (10 QA, SONATA 1건)"
	@echo "                  · 결과: work-log/<오늘> ragas-mini-result.md"
	@echo "                  · 전제: uvicorn 8000 포트 + .env 의 SUPABASE_* 유효"
	@echo ""
	@echo "  make golden   - golden batch (20건) top-1/top-3 hit 율 회귀 측정"
	@echo "                  · 결과: stdout markdown"
	@echo ""
	@echo "  make slo      - search SLO 모니터링 (latency / cache_hit / mode 분포)"
	@echo "                  · 결과: stdout markdown"
	@echo ""

# Phase 1 mini-Ragas — Context Recall / Context Precision (검색만).
# 결과는 날짜 기반 파일명으로 work-log 에 떨어뜨려 변경 이력 누적.
EVAL_DATE := $(shell date +%Y-%m-%d)
EVAL_OUTPUT := work-log/$(EVAL_DATE) ragas-mini-result.md
eval:
	@echo "[eval] Ragas mini 검색 품질 측정 시작..."
	@echo "[eval] (uvicorn 8000 떠있어야 함 — 미실행 시 cd api && uv run uvicorn app.main:app --reload)"
	cd api && uv run python ../evals/run_ragas.py --top_k 10 --output "../$(EVAL_OUTPUT)"
	@echo "[eval] 완료 — '$(EVAL_OUTPUT)' 확인"

# 기존 회귀 보호 도구 — golden batch (Ragas 도입 전부터 ship) 호환 entry-point.
golden:
	@echo "[golden] golden 20건 batch 회귀 측정 (mode=hybrid)..."
	cd api && uv run python scripts/golden_batch_smoke.py --mode all --require-top1-min 0.85

# search SLO 모니터링 — W14 Day 2 도입.
slo:
	@echo "[slo] search SLO baseline 측정..."
	cd api && uv run python scripts/monitor_search_slo.py
