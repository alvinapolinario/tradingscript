import csv, math, random, sys
from datetime import datetime, timezone
random.seed(7)
days = int(sys.argv[2]); out = sys.argv[1]
t = int(datetime(2025,1,6,tzinfo=timezone.utc).timestamp()); px = 2650.0
with open(out,"w",newline="") as fh:
    w = csv.writer(fh); w.writerow(["time","open","high","low","close","tick_volume","spread"])
    vol = 1.2
    for _ in range(days*288):
        d = datetime.fromtimestamp(t, tz=timezone.utc)
        if d.weekday() >= 5: t += 300; continue
        vol = max(0.4, min(4.0, vol*math.exp(random.gauss(0,0.05))))
        o = px; c = o + random.gauss(0.01, vol)
        h = max(o,c) + abs(random.gauss(0, vol*0.6)); l = min(o,c) - abs(random.gauss(0, vol*0.6))
        w.writerow([d.strftime("%Y-%m-%d %H:%M:%S"), f"{o:.2f}", f"{h:.2f}", f"{l:.2f}", f"{c:.2f}", random.randint(100,900), random.randint(15,40)])
        px = c; t += 300
