"""Quick A/B: joint optimization vs c_log-ordered feasibility sweep."""
import sys, time, math
sys.path.insert(0, '.')
from search.SAT import SAT, SATJoint

def c_log(a, d, n):
    if d <= 1 or a == 0: return float('inf')
    return a*d/(n*math.log(d))

def sweep(n, alpha_max, budget_per_box=3.0, total_budget=60.0):
    boxes = sorted(((c_log(a,d,n), a, d) for a in range(1, alpha_max+1) for d in range(1, n)))
    t0 = time.time()
    total = 0.0
    for _, a, d in boxes:
        if time.time() - t0 >= total_budget: return None
        r = SAT(n=n, alpha=a, d_max=d, time_limit_s=budget_per_box).run()[0]
        total += r.metadata['wall_time_s']
        if r.metadata['status'] == 'SAT':
            return dict(alpha=a, d_max=d, c_log=c_log(a,d,n), wall=time.time()-t0, solver=total, calls=boxes.index((c_log(a,d,n),a,d))+1)
    return None

def joint(n, alpha_max, budget=60.0):
    t0 = time.time()
    r = SATJoint(n=n, alpha_max=alpha_max, time_limit_s=budget).run()[0]
    return dict(alpha=r.alpha, d_max=r.d_max, c_log=r.c_log, wall=time.time()-t0,
                solver=r.metadata['wall_time_s'], A=r.metadata.get('A_solver'),
                D=r.metadata.get('D_solver'), status=r.metadata['status'],
                obj=r.metadata.get('objective'))

print(f"{'n':>3}  {'mode':<6s}  {'a':>2s} {'d':>2s}  {'c_log':>7s}  {'wall':>7s}  {'solver':>7s}", flush=True)
print('-'*60, flush=True)
for n in [10, 13, 15, 17]:
    amax = max(4, math.ceil(n**0.6))
    s = sweep(n, amax, total_budget=60.0)
    print(f"{n:>3}  sweep   {s['alpha']:>2d} {s['d_max']:>2d}  {s['c_log']:>7.4f}  {s['wall']:>6.2f}s  {s['solver']:>6.2f}s", flush=True) if s else print(f"{n}  sweep   TIMEOUT", flush=True)
    j = joint(n, amax, budget=60.0)
    cl = f"{j['c_log']:.4f}" if j['c_log'] else '   inf '
    print(f"{n:>3}  joint   {j['alpha']:>2d} {j['d_max']:>2d}  {cl:>7s}  {j['wall']:>6.2f}s  {j['solver']:>6.2f}s   [{j['status']}, A={j['A']} D={j['D']} obj={j['obj']}]", flush=True)
