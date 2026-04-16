from src.envs.kfour import KFourDataPoint
for N, t in [(17,5),(17,6),(17,7),(25,6),(25,7),(25,8)]:
    KFourDataPoint.T = t
    pars = KFourDataPoint._save_class_params()
    batch = KFourDataPoint._batch_generate_and_score(10, N, pars)
    scores = sorted(set(d.score for d in batch))
    print(f"N={N} t={t}: {len(batch)}/10 valid  scores={scores}")
