"""Mede luz, contraste e cor de cada foto de treino, para escolher quais servem de alvo.

uso: python estatisticas.py <pasta_dados>
grava estat.npy com colunas: p01, p50, p99, desvio da luz, saturação média, fração de pixels com cor
"""
import os, sys
import numpy as np

DADOS = sys.argv[1]
d = np.load(os.path.join(DADOS, "tom128.npy"), mmap_mode="r")
N = d.shape[0]
out = np.zeros((N, 6), np.float32)
for i in range(0, N, 500):
    x = d[i:i + 500].astype(np.float32) / 255
    y = 0.2126 * x[..., 0] + 0.7152 * x[..., 1] + 0.0722 * x[..., 2]
    mx, mn = x.max(-1), x.min(-1)
    s = (mx - mn) / (mx + 1e-4)
    yf = y.reshape(len(x), -1)
    out[i:i + 500, 0:3] = np.percentile(yf, [1, 50, 99], axis=1).T
    out[i:i + 500, 3] = yf.std(1)
    out[i:i + 500, 4] = s.reshape(len(x), -1).mean(1)
    out[i:i + 500, 5] = ((mx - mn) > 0.045).reshape(len(x), -1).mean(1)
np.save(os.path.join(DADOS, "estat.npy"), out)
nomes = ["p01", "p50", "p99", "desvio", "sat", "frac_cor"]
qs = [5, 25, 50, 75, 95]
for k, n in enumerate(nomes):
    print(f"{n:9s}", " ".join(f"{v:.3f}" for v in np.percentile(out[:, k], qs)))
p01, p50, p99, dv, sat, fc = out.T
pb = fc < 0.01
boa = (p01 <= 0.08) & (p99 >= 0.90) & (dv >= 0.17) & (p50 >= 0.12) & (p50 <= 0.78) & ((sat >= 0.16) & (sat <= 0.62) | pb)
print(f"total {N} | preto e branco {pb.sum()} | pretos firmes {(p01 <= 0.08).mean():.2f} | brancos {(p99 >= 0.9).mean():.2f} | contraste {(dv >= 0.17).mean():.2f} | cor {((sat >= 0.16) & (sat <= 0.62)).mean():.2f} | luz {((p50 >= 0.12) & (p50 <= 0.78)).mean():.2f}")
print(f"passam em tudo: {boa.sum()} ({boa.mean() * 100:.0f}%)")
