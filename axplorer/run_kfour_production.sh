#!/usr/bin/env bash
set -uo pipefail

cd ~/k4free/axplorer
mkdir -p logs results/kfour/validation results/kfour/production

exec > logs/logs.txt 2>&1
export PYTHONUNBUFFERED=1

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
#
# Reference: README Turán example for N=30 uses defaults:
#   n_layer=4  n_embd=256  batch=32  gensize=100000  pop=200000  max_steps=50000
#   temperature=0.6  inc_temp=0.1  max_len=100
#
# For kfour the sequences are longer than Turán (H is K_t-free, so denser than
# 4-cycle-free).  The densest K_t-free graph is the Turán graph T(N, t-1) with
# (t-2)/(t-1) * N²/2 edges.  max_len must cover this:
#
#   Tier A  t=5  N≤24  Turán T(24,4)=216 edges   → same model as README N=30
#   Tier B  t=6  N≤35  Turán T(35,5)=490 edges   → slightly deeper
#   Tier C  t=7  N≤48  Turán T(48,6)=960 edges   → wider + deeper
#   Tier D  t=8  N≤55  Turán T(55,7)=1296 edges  → widest
#
# ───────────────────────────────────────────────────────────────────────────────

CONDA_ENV=env_axplorer
NUM_WORKERS=16          # use all 16 CPU cores for data generation

# Sampling temperature — README uses 0.6 / inc 0.1 for Turán N=30
TEMPERATURE=0.6
INC_TEMP=0.1

# ── max_steps sizing ───────────────────────────────────────────────────────────
# max_steps is gradient updates PER EPOCH (README default = 50000).
# Rule of thumb: ~25 passes through the training pool per epoch.
#   max_steps = 25 * pop_size / batch_size
# Retune: change pop or batch, then recompute max_steps with the formula above.
# ───────────────────────────────────────────────────────────────────────────────
#
# num_samples_from_model is the main exploration knob — how many new candidates
# the model proposes each epoch before local search + selection.  README uses
# 500,000.  kfour local search is more expensive than Turán's C₄ check, so we
# scale back, but staying in the 10k–100k range keeps exploration healthy.
# ───────────────────────────────────────────────────────────────────────────────

# ── gen_batch_size VRAM sizing ────────────────────────────────────────────────
# The model uses KV caching (CausalSelfAttention.forward builds past_kv via
# torch.cat).  During the forward pass, both the old and new KV tensors exist
# simultaneously (old is freed only after the call returns), so peak KV is 2×
# the stored cache:
#
#   peak_GB = 2 × n_layer × 2 × gen_batch × max_len × n_embd × 4 / 1e9
#
# Solving for gen_batch with 38 GB budget (40 GB - 2 GB headroom):
#   gen_batch = 38e9 / (2 × n_layer × 2 × max_len × n_embd × 4)
#
# With gen_batch_size=1000 (default):
#   Tier A  peak =  3.8 GB  → fine; can increase to 8192
#   Tier B  peak = 11.9 GB  → fine; can increase to 2048
#   Tier C  peak = 34.3 GB  → OOM with overhead at 40 GB; use 800
#   Tier D  peak = 64.1 GB  → OOM on 48 GB A40; use 500
# ───────────────────────────────────────────────────────────────────────────────

# ── Validation (quick convergence check against 5 known scores) ────────────────
VAL_MAX_EPOCHS=150
VAL_GENSIZE=5000        # initial random graphs generated
VAL_POP=5000            # best examples kept as training pool
VAL_SAMPLES=10000       # model samples drawn each epoch
VAL_BATCH=32
VAL_MAX_STEPS=4000      # 25 passes: 25 * 5000 / 32 ≈ 4000
VAL_N_LAYER=4
VAL_N_EMBD=256
VAL_MAX_LEN=300         # covers Turán T(24,6)=240 edges (largest val target N=24 t=7)
VAL_GEN_BATCH=1000      # peak KV = 2*4*2*1000*300*256*4 ≈ 4.6 GB — fine

# ── Tier A: t=5, N=18..24  (max sequence ≈ 216 edges) ─────────────────────────
# Same model as README Turán N=30 baseline (n_layer=4, n_embd=256).
A_MAX_EPOCHS=1000
A_GENSIZE=100000
A_POP=100000
A_SAMPLES=100000        # README uses 500k; 100k is healthy for kfour cost
A_BATCH=64              # short sequences, A40 can afford large batch
A_MAX_STEPS=39000       # 25 passes: 25 * 100000 / 64 ≈ 39000
A_N_LAYER=4
A_N_EMBD=256
A_MAX_LEN=250
A_GEN_BATCH=8192        # peak KV = 2*4*2*8192*250*256*4 ≈ 31.5 GB — fits 40 GB

# ── Tier B: t=6, N=25..35  (max sequence ≈ 490 edges) ─────────────────────────
# Slightly deeper model for longer sequences.
B_MAX_EPOCHS=1000
B_GENSIZE=50000
B_POP=50000
B_SAMPLES=50000
B_BATCH=32
B_MAX_STEPS=39000       # 25 passes: 25 * 50000 / 32 ≈ 39000
B_N_LAYER=6
B_N_EMBD=256
B_MAX_LEN=520
B_GEN_BATCH=2048        # peak KV = 2*6*2*2048*520*256*4 ≈ 26.2 GB — fits 40 GB

# ── Tier C: t=7, N=36..48  (max sequence ≈ 960 edges) ─────────────────────────
# Wider embeddings for longer sequences; batch reduced to stay in VRAM.
C_MAX_EPOCHS=500
C_GENSIZE=20000
C_POP=20000
C_SAMPLES=20000
C_BATCH=16
C_MAX_STEPS=31000       # 25 passes: 25 * 20000 / 16 ≈ 31000
C_N_LAYER=6
C_N_EMBD=384
C_MAX_LEN=1000
C_GEN_BATCH=800         # peak KV = 2*6*2*800*1000*384*4 ≈ 29.5 GB — fits 40 GB

# ── Tier D: t=8, N=49..55  (max sequence ≈ 1300 edges) ────────────────────────
# Longest sequences; smallest batch to fit in VRAM.
D_MAX_EPOCHS=500
D_GENSIZE=10000
D_POP=10000
D_SAMPLES=10000
D_BATCH=8
D_MAX_STEPS=31000       # 25 passes: 25 * 10000 / 8 ≈ 31000
D_N_LAYER=8
D_N_EMBD=384
D_MAX_LEN=1400
D_GEN_BATCH=500         # peak KV = 2*8*2*500*1400*384*4 ≈ 34.4 GB — fits 40 GB

# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

PY="micromamba run -n $CONDA_ENV python -u"
ts() { date '+%Y-%m-%d %H:%M:%S'; }

best_from_log() {
    grep -oP '(?<=Max score: )\S+' "$1" \
        | awk 'BEGIN{m=-1}{v=int($1);if(v>m)m=v}END{print m}'
}

# ═══════════════════════════════════════════════════════════════════════════════
# VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

echo "[$(ts)] ===== VALIDATION ====="

run_val() {
    local N=$1 t=$2 target=$3
    local out=results/kfour/validation/${N}_${t}
    mkdir -p "$out"
    echo "[$(ts)] val  N=$N  t=$t  known=$target"

    $PY train.py \
        --env_name kfour --N $N --t $t \
        --exp_name kfour_val_N${N}_t${t} --dump_path $out/checkpoint \
        --num_workers $NUM_WORKERS --process_pool true --always_search true \
        --encoding_tokens single_integer \
        --temperature $TEMPERATURE --inc_temp $INC_TEMP \
        --max_epochs $VAL_MAX_EPOCHS --max_steps $VAL_MAX_STEPS \
        --gensize $VAL_GENSIZE --pop_size $VAL_POP \
        --num_samples_from_model $VAL_SAMPLES \
        --batch_size $VAL_BATCH --n_layer $VAL_N_LAYER \
        --n_embd $VAL_N_EMBD --max_len $VAL_MAX_LEN \
        --gen_batch_size $VAL_GEN_BATCH \
        2>&1 | tee $out/train.log

    local best; best=$(best_from_log $out/train.log)
    echo "[$(ts)] val  N=$N  t=$t  best=$best  known=$target"
    [[ "$best" -gt "$target" ]] 2>/dev/null \
        && echo "[$(ts)] *** NEW BOUND  N=$N t=$t  best=$best > known=$target ***"
}

run_val 17 4  68
run_val 18 5  99
run_val 20 5 120
run_val 22 5 132
run_val 24 7 228

# ═══════════════════════════════════════════════════════════════════════════════
# PRODUCTION
# ═══════════════════════════════════════════════════════════════════════════════

echo "[$(ts)] ===== PRODUCTION ====="

run_prod() {
    local N=$1 t=$2
    shift 2
    local out=results/kfour/production/${N}_${t}

    if [[ -f "$out/best_score.txt" ]]; then
        echo "[$(ts)] skip  N=$N  t=$t  (best=$(cat $out/best_score.txt))"
        return
    fi
    mkdir -p "$out"
    echo "[$(ts)] start  N=$N  t=$t"

    $PY train.py \
        --env_name kfour --N $N --t $t \
        --exp_name kfour_N${N}_t${t} --dump_path $out/checkpoint \
        --num_workers $NUM_WORKERS --process_pool true --always_search true \
        --encoding_tokens single_integer \
        --temperature $TEMPERATURE --inc_temp $INC_TEMP \
        "$@" 2>&1 | tee $out/train.log \
    || echo "[$(ts)] WARNING  train.py non-zero exit for N=$N t=$t"

    local best; best=$(best_from_log $out/train.log)
    echo "$best" > $out/best_score.txt
    echo "[$(ts)] done  N=$N  t=$t  best=$best"
}

# Shorthand to avoid repeating the flag list at every call site
run_A() { run_prod $1 $2 --max_epochs $A_MAX_EPOCHS --max_steps $A_MAX_STEPS --gensize $A_GENSIZE --pop_size $A_POP --num_samples_from_model $A_SAMPLES --batch_size $A_BATCH --n_layer $A_N_LAYER --n_embd $A_N_EMBD --max_len $A_MAX_LEN --gen_batch_size $A_GEN_BATCH; }
run_B() { run_prod $1 $2 --max_epochs $B_MAX_EPOCHS --max_steps $B_MAX_STEPS --gensize $B_GENSIZE --pop_size $B_POP --num_samples_from_model $B_SAMPLES --batch_size $B_BATCH --n_layer $B_N_LAYER --n_embd $B_N_EMBD --max_len $B_MAX_LEN --gen_batch_size $B_GEN_BATCH; }
run_C() { run_prod $1 $2 --max_epochs $C_MAX_EPOCHS --max_steps $C_MAX_STEPS --gensize $C_GENSIZE --pop_size $C_POP --num_samples_from_model $C_SAMPLES --batch_size $C_BATCH --n_layer $C_N_LAYER --n_embd $C_N_EMBD --max_len $C_MAX_LEN --gen_batch_size $C_GEN_BATCH; }
run_D() { run_prod $1 $2 --max_epochs $D_MAX_EPOCHS --max_steps $D_MAX_STEPS --gensize $D_GENSIZE --pop_size $D_POP --num_samples_from_model $D_SAMPLES --batch_size $D_BATCH --n_layer $D_N_LAYER --n_embd $D_N_EMBD --max_len $D_MAX_LEN --gen_batch_size $D_GEN_BATCH; }

# ── Priority: N = R(4,t)-1 for each t ─────────────────────────────────────────
# These are the boundary cases — hardest to satisfy, tightest c_lb if valid
# graphs exist.  Run first so results are available before the full sweep.
#   R(4,5)=25 → N=24, t=5   (Tier A)
#   R(4,6)=36 → N=35, t=6   (Tier B)
#   R(4,7)=49 → N=48, t=7   (Tier C)
#   R(4,8)>55 → N=55, t=8   (Tier D, conservative bound)
echo "[$(ts)] -- priority: boundary cases (N = R(4,t)-1) --"
run_A 24 5
run_B 35 6
run_C 48 7
run_D 55 8

# ── Full sweep ─────────────────────────────────────────────────────────────────
# Already-completed pairs (including the priority cases above) are skipped.
echo "[$(ts)] -- full sweep --"

# t=5  R(4,5)=25
for N in 18 19 20 21 22 23 24;              do run_A $N 5; done
# t=6  R(4,6)=36
for N in 25 26 27 28 29 30 31 32 33 34 35;  do run_B $N 6; done
# t=7  R(4,7)=49
for N in $(seq 36 48);                       do run_C $N 7; done
# t=8  R(4,8)>55
for N in $(seq 49 55);                       do run_D $N 8; done

# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

echo "[$(ts)] ===== SUMMARY ====="

$PY - <<'PYEOF'
import os, math, csv
from collections import defaultdict

prod_dir = "results/kfour/production"
csv_out  = "results/kfour/summary.csv"
rows     = []
c_by_N   = defaultdict(list)

for entry in sorted(os.listdir(prod_dir)):
    score_file = os.path.join(prod_dir, entry, "best_score.txt")
    if not os.path.isfile(score_file):
        continue
    try:
        N, t = map(int, entry.split("_", 1))
    except ValueError:
        continue
    try:
        best_H = int(open(score_file).read().strip())
    except ValueError:
        continue
    if best_H <= 0:
        continue

    E_G   = N * (N - 1) // 2 - best_H
    d_avg = 2.0 * E_G / N
    if d_avg <= 1.0:
        continue
    c_lb = (t - 1) * d_avg / (N * math.log(d_avg))
    rows.append({"N": N, "t": t, "best_H": best_H, "E_G": E_G,
                 "d_avg": round(d_avg, 4), "c_lb": round(c_lb, 6)})
    c_by_N[N].append((t, c_lb))

rows.sort(key=lambda r: (r["N"], r["t"]))

print(f"\n{'N':>4} {'t':>3} {'|E(H)|':>8} {'E(G)':>7} {'d_avg':>8} {'c_lb':>10}")
print("-" * 46)
for r in rows:
    print(f"{r['N']:>4} {r['t']:>3} {r['best_H']:>8} {r['E_G']:>7}"
          f" {r['d_avg']:>8.4f} {r['c_lb']:>10.6f}")

print("\nc_min per N:")
for N in sorted(c_by_N):
    best_t, c_min = min(c_by_N[N], key=lambda x: x[1])
    print(f"  N={N}  t={best_t}  c_min={c_min:.6f}")

with open(csv_out, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["N","t","best_H","E_G","d_avg","c_lb"])
    w.writeheader(); w.writerows(rows)
print(f"\nWrote {csv_out}")
PYEOF

echo "[$(ts)] ===== DONE ====="
