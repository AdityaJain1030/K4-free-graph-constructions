"""
Regression & dimensionality analysis of c_log across the graph_db catalog.

Ask: does c_log collapse onto a low-dimensional surface defined by
structural / spectral / local / expansion features?

Pulls every K4-free graph with complete cached properties, computes
derived features, runs:
  1. Pairwise correlations with c_log
  2. OLS regression c_log ~ features   (with and without α)
  3. OLS regression α/n ~ features     (predict α from non-α structure)
  4. PCA on standardized features, project c_log onto PC1/PC2
  5. Residual analysis: which points are poorly predicted?

Writes: logs/analysis/c_log_surface_<TS>.log
         plots/c_log_surface_*.png
"""
from __future__ import annotations
import datetime
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import sqlite3

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_data() -> pd.DataFrame:
    con = sqlite3.connect(os.path.join(REPO, "cache.db"))
    q = """
      SELECT n, m, density, d_min, d_max, d_avg, is_regular, is_connected,
             n_components, diameter, radius, girth, n_triangles,
             avg_clustering, assortativity, codegree_avg, codegree_max,
             spectral_radius, spectral_gap, algebraic_connectivity,
             clique_num, greedy_chromatic_bound, alpha, c_log, beta,
             lovasz_theta, eigenvalues_adj, source
      FROM cache
      WHERE is_k4_free=1 AND c_log IS NOT NULL
        AND lovasz_theta IS NOT NULL
        AND spectral_radius IS NOT NULL
        AND eigenvalues_adj IS NOT NULL
        AND avg_clustering IS NOT NULL
        AND codegree_avg IS NOT NULL
    """
    df = pd.read_sql_query(q, con)
    con.close()

    # λ_min from the eigenvalue JSON list
    def parse_lam_min(s):
        try:
            vals = json.loads(s) if isinstance(s, str) else s
            return float(min(vals)) if vals else np.nan
        except Exception:
            return np.nan

    def parse_lam_2(s):
        try:
            vals = json.loads(s) if isinstance(s, str) else s
            vals_sorted = sorted(vals, reverse=True)
            return float(vals_sorted[1]) if len(vals_sorted) > 1 else np.nan
        except Exception:
            return np.nan

    df["lambda_min"] = df["eigenvalues_adj"].apply(parse_lam_min)
    df["lambda_2"]   = df["eigenvalues_adj"].apply(parse_lam_2)
    df = df.drop(columns=["eigenvalues_adj"])

    # Derived features
    df["alpha_over_n"]   = df["alpha"] / df["n"]
    df["d_over_n"]       = df["d_max"] / df["n"]
    df["tri_per_n"]      = df["n_triangles"] / df["n"]
    df["mantel_sat"]     = np.where(
        df["d_max"] >= 2,
        3 * df["n_triangles"] / (df["n"] * (df["d_max"].astype(int)**2 // 4).replace(0, 1)),
        0.0,
    )
    df["hoffman_upper_alpha"] = np.where(
        df["lambda_min"] < 0,
        df["n"] * (-df["lambda_min"]) / (df["d_max"] - df["lambda_min"]),
        np.nan,
    )
    df["alpha_over_hoffman"]  = df["alpha"] / df["hoffman_upper_alpha"]
    df["alpha_over_theta"]    = df["alpha"] / df["lovasz_theta"]
    df["spectral_gap_ratio"]  = (df["spectral_radius"] - df["lambda_2"]) / df["spectral_radius"]
    df["lam_range"]           = df["spectral_radius"] - df["lambda_min"]
    df["regularity_spread"]   = df["d_max"] - df["d_min"]
    df["normalized_alg_conn"] = df["algebraic_connectivity"] / df["d_max"].replace(0, np.nan)

    # Drop rows with NaN in feature set we'll use
    return df


FEATURES_NO_ALPHA = [
    # structural/local
    "n", "d_max", "d_min", "d_avg", "density", "regularity_spread",
    "n_components", "avg_clustering", "tri_per_n", "mantel_sat",
    "codegree_avg", "codegree_max",
    # spectral
    "spectral_radius", "spectral_gap", "algebraic_connectivity",
    "normalized_alg_conn", "lambda_min", "lambda_2",
    "spectral_gap_ratio", "lam_range",
    # expansion / upper bound related
    "hoffman_upper_alpha", "lovasz_theta",
]

FEATURES_WITH_ALPHA = FEATURES_NO_ALPHA + ["alpha", "alpha_over_n",
                                            "alpha_over_hoffman",
                                            "alpha_over_theta"]


def _standardize(X):
    mu = np.nanmean(X, axis=0)
    sd = np.nanstd(X, axis=0)
    sd[sd == 0] = 1.0
    return (X - mu) / sd, mu, sd


def fit_linear(df: pd.DataFrame, feature_cols: list[str], target: str):
    """OLS via numpy.lstsq on standardized features. Returns R², coefs, residuals."""
    X = df[feature_cols].values
    y = df[target].values
    mask = ~np.isnan(X).any(axis=1) & ~np.isnan(y)
    X = X[mask]; y = y[mask]
    Xs, mu, sd = _standardize(X)
    # prepend intercept
    A = np.column_stack([np.ones(len(Xs)), Xs])
    beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    y_pred = A @ beta
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - y.mean()) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    # beta[0] is intercept; beta[1:] are standardized coefs
    coefs = list(zip(feature_cols, beta[1:]))
    coefs.sort(key=lambda t: -abs(t[1]))
    # wrap in a lightweight object for downstream
    class _R: pass
    r = _R(); r.coef_ = beta[1:]; r.intercept_ = beta[0]
    r.predict = lambda Xnew: np.column_stack([np.ones(len(Xnew)), Xnew]) @ beta
    return r2, coefs, r, Xs, y, mask


def fit_kfold_linear(df, feature_cols, target, k=5, seed=0):
    """k-fold cross-validated R² for OLS."""
    rng = np.random.default_rng(seed)
    X = df[feature_cols].values
    y = df[target].values
    mask = ~np.isnan(X).any(axis=1) & ~np.isnan(y)
    X = X[mask]; y = y[mask]
    n = len(y)
    order = rng.permutation(n)
    folds = np.array_split(order, k)
    r2s = []
    for i in range(k):
        test = folds[i]; train = np.concatenate([folds[j] for j in range(k) if j != i])
        Xs_tr, mu, sd = _standardize(X[train])
        Xs_te = (X[test] - mu) / sd
        A_tr = np.column_stack([np.ones(len(Xs_tr)), Xs_tr])
        beta, *_ = np.linalg.lstsq(A_tr, y[train], rcond=None)
        A_te = np.column_stack([np.ones(len(Xs_te)), Xs_te])
        y_pred = A_te @ beta
        ss_res = np.sum((y[test] - y_pred) ** 2)
        ss_tot = np.sum((y[test] - y[train].mean()) ** 2)
        r2s.append(1 - ss_res / ss_tot if ss_tot > 0 else 0.0)
    return float(np.mean(r2s)), float(np.std(r2s))


def main():
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = os.path.join(REPO, "logs", "analysis")
    plot_dir = os.path.join(REPO, "plots")
    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(plot_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"c_log_surface_{ts}.log")

    def log(msg: str):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        print(line, flush=True)
        with open(log_path, "a") as f:
            f.write(line + "\n")

    log("== c_log surface regression ==")
    log(f"log_path={log_path}")

    df = load_data()
    log(f"loaded {len(df)} complete-feature K4-free rows "
        f"across {df['n'].nunique()} distinct n values")
    log(f"c_log range: {df['c_log'].min():.3f} .. {df['c_log'].max():.3f}  "
        f"median={df['c_log'].median():.3f}")

    # 1. Pairwise correlations
    log("\n--- (1) Pearson correlation with c_log, sorted by |r| ---")
    all_feats = FEATURES_WITH_ALPHA + ["alpha"]
    corrs = []
    for f in set(all_feats):
        if f not in df.columns: continue
        x = df[f].values; y = df["c_log"].values
        m = ~np.isnan(x) & ~np.isnan(y)
        if m.sum() < 10: continue
        r = np.corrcoef(x[m], y[m])[0, 1]
        corrs.append((f, r))
    corrs.sort(key=lambda t: -abs(t[1]))
    for f, r in corrs[:20]:
        log(f"  {f:<24} r = {r:+.4f}")

    # 2. Linear regression: c_log ~ non-α features
    log("\n--- (2a) Linear regression: c_log ~ non-α features ---")
    r2, coefs, reg, Xs, y, mask = fit_linear(df, FEATURES_NO_ALPHA, "c_log")
    log(f"  n_rows = {mask.sum()}  R² = {r2:.4f}")
    log("  top standardized coefs:")
    for f, c in coefs[:10]:
        log(f"    {f:<24} β = {c:+.4f}")

    # 2b. Same but including α features
    log("\n--- (2b) Linear regression: c_log ~ ALL features (incl. α) ---")
    r2b, coefs_b, _, _, _, _ = fit_linear(df, FEATURES_WITH_ALPHA, "c_log")
    log(f"  R² = {r2b:.4f}  (trivial — α appears directly in c_log)")
    for f, c in coefs_b[:6]:
        log(f"    {f:<24} β = {c:+.4f}")

    # 3. Predict α/n from non-α features
    log("\n--- (3) Linear regression: α/n ~ non-α features ---")
    r2c, coefs_c, _, _, _, _ = fit_linear(df, FEATURES_NO_ALPHA, "alpha_over_n")
    log(f"  R² = {r2c:.4f}")
    for f, c in coefs_c[:10]:
        log(f"    {f:<24} β = {c:+.4f}")

    # 4. 5-fold CV R² (non-linear models would need sklearn; skipping)
    log("\n--- (4) 5-fold CV for c_log ~ non-α linear ---")
    cv_r2, cv_std = fit_kfold_linear(df, FEATURES_NO_ALPHA, "c_log", k=5, seed=0)
    log(f"  CV R² = {cv_r2:.4f}  ± {cv_std:.4f}")
    cv_r2b, cv_stdb = fit_kfold_linear(df, FEATURES_NO_ALPHA, "alpha_over_n", k=5, seed=0)
    log(f"  CV R² (α/n target) = {cv_r2b:.4f}  ± {cv_stdb:.4f}")
    r2_rf = cv_r2
    imps = coefs  # reuse

    # 5. PCA on standardized features via SVD
    log("\n--- (5) PCA of non-α features, projected with c_log color ---")
    X_valid = df[FEATURES_NO_ALPHA].dropna()
    y_valid = df.loc[X_valid.index, "c_log"].values
    Xs, mu, sd = _standardize(X_valid.values)
    # SVD-based PCA: Xs = U S Vt. Principal components = Xs @ V = U S
    U, S, Vt = np.linalg.svd(Xs, full_matrices=False)
    var = (S**2) / (len(Xs) - 1)
    var_ratio = var / var.sum()
    P = U * S  # shape (n, k)
    log(f"  explained variance ratio (first 5 PCs): "
        f"{[round(float(x), 3) for x in var_ratio[:5]]}")
    log(f"  cumulative: {round(float(var_ratio[:3].sum()),3)} at PC3")
    log("  PC correlations with c_log:")
    for i in range(min(5, P.shape[1])):
        r = np.corrcoef(P[:, i], y_valid)[0, 1]
        log(f"    PC{i+1}  r(PC, c_log) = {r:+.4f}")
    # For plotting
    class _PCA: pass
    pca = _PCA()
    pca.explained_variance_ratio_ = var_ratio

    # 6. Plots
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    sc = axes[0].scatter(P[:, 0], P[:, 1], c=y_valid, cmap="viridis",
                         s=14, alpha=0.75)
    axes[0].set_xlabel("PC1"); axes[0].set_ylabel("PC2")
    axes[0].set_title(f"PCA of non-α features, colored by c_log  (n={len(y_valid)})")
    fig.colorbar(sc, ax=axes[0], label="c_log")

    # Residuals from the linear fit (c_log ~ non-α)
    Xs_plot, _, _ = _standardize(X_valid.values)
    A_plot = np.column_stack([np.ones(len(Xs_plot)), Xs_plot])
    beta_plot, *_ = np.linalg.lstsq(A_plot, y_valid, rcond=None)
    y_pred_lin = A_plot @ beta_plot
    ss_res = np.sum((y_valid - y_pred_lin)**2)
    ss_tot = np.sum((y_valid - y_valid.mean())**2)
    r2_plot = 1 - ss_res/ss_tot
    axes[1].scatter(y_valid, y_pred_lin, s=14, alpha=0.6)
    axes[1].plot([y_valid.min(), y_valid.max()], [y_valid.min(), y_valid.max()], 'k--', alpha=0.4)
    axes[1].set_xlabel("actual c_log"); axes[1].set_ylabel("predicted c_log")
    axes[1].set_title(f"Linear fit (non-α): R²={r2_plot:.3f}")
    fig.tight_layout()
    out_path = os.path.join(plot_dir, f"c_log_surface_{ts}.png")
    fig.savefig(out_path, dpi=140)
    log(f"  saved {out_path}")

    # 7. Residual outliers: which graphs poorly fit?
    log("\n--- (7) Largest residuals (poorly-fit graphs) ---")
    valid_df = df.loc[X_valid.index].copy()
    valid_df["c_log_pred"] = y_pred_lin
    valid_df["resid"] = y_valid - y_pred_lin
    outliers = valid_df.iloc[np.argsort(-np.abs(valid_df["resid"].values))][:10]
    log(f"{'n':>4} {'α':>3} {'d':>3} {'c_log':>6} {'pred':>6} {'resid':>7} {'src':<20}")
    for _, r in outliers.iterrows():
        log(f"{int(r['n']):>4} {int(r['alpha']):>3} {int(r['d_max']):>3} "
            f"{r['c_log']:>6.3f} {r['c_log_pred']:>6.3f} {r['resid']:>+7.3f} "
            f"{r['source'][:20]:<20}")

    log("\n--- (8) Summary ---")
    log(f"  (1) Best single predictor of c_log (by |r|): {corrs[0][0]} (r={corrs[0][1]:+.3f})")
    log(f"  (2) Non-α linear fit: R² = {r2:.3f}")
    log(f"  (3) Non-α → α/n linear fit: R² = {r2c:.3f}")
    log(f"  (4) Non-α RF fit of c_log: R² = {r2_rf:.3f}")
    log(f"  (5) First 3 PCs explain {pca.explained_variance_ratio_[:3].sum()*100:.1f}% of feature variance")
    log(f"  (6) Max |PC-c_log| correlation across PC1..5: "
        f"{max(abs(np.corrcoef(P[:,i], y_valid)[0,1]) for i in range(5)):.3f}")


if __name__ == "__main__":
    main()
