"""Monta os arquivos de treino a partir das fotos baixadas por baixar_fotos.py.

uso: python preparar_dados.py <pasta_dados>

gera em <pasta_dados>:
  tom128.npy  (N, 128, 128, 3) uint8  foto inteira reduzida, para a rede de tom e cor
  det96.npy   (2N, 96, 96, 3) uint8   recortes com textura em tamanho real, para a rede de detalhe
  ordem.txt   id e grupo de cada linha de tom128.npy (as últimas 500 ficam fora do treino)
"""
import os, sys, random
import numpy as np
from PIL import Image
from concurrent.futures import ThreadPoolExecutor

DADOS = sys.argv[1]
IMG = os.path.join(DADOS, "img")
T, C, NC = 128, 96, 2

linhas = [l.split("\t") for l in open(os.path.join(DADOS, "lista.txt"), encoding="utf-8").read().split("\n") if l]
random.seed(11)
random.shuffle(linhas)


def textura(a):
    y = a.astype(np.float32).mean(axis=2)
    return float(np.abs(y[1:-1, 1:-1] * 4 - y[:-2, 1:-1] - y[2:, 1:-1] - y[1:-1, :-2] - y[1:-1, 2:]).mean())


def uma(par):
    pid, grupo = par
    try:
        im = Image.open(os.path.join(IMG, pid + ".jpg")).convert("RGB")
    except Exception:
        return None
    w, h = im.size
    if min(w, h) < C + 8:
        return None
    pequena = np.asarray(im.resize((T, T), Image.BICUBIC), dtype=np.uint8)
    cheia = np.asarray(im, dtype=np.uint8)
    rnd = random.Random(pid)
    cand = []
    for _ in range(8):
        x, y = rnd.randint(0, w - C), rnd.randint(0, h - C)
        rec = cheia[y:y + C, x:x + C]
        cand.append((textura(rec), rec))
    cand.sort(key=lambda t: -t[0])
    return pid, grupo, pequena, [c[1] for c in cand[:NC]]


with ThreadPoolExecutor(max_workers=8) as ex:
    res = [r for r in ex.map(uma, linhas) if r]

n = len(res)
tom = np.stack([r[2] for r in res])
det = np.stack([c for r in res for c in r[3]])
np.save(os.path.join(DADOS, "tom128.npy"), tom)
np.save(os.path.join(DADOS, "det96.npy"), det)
with open(os.path.join(DADOS, "ordem.txt"), "w", encoding="utf-8") as f:
    for r in res:
        f.write(r[0] + "\t" + r[1] + "\n")
print(f"fotos {n} | tom {tom.shape} {tom.nbytes / 1e6:.0f} MB | detalhe {det.shape} {det.nbytes / 1e6:.0f} MB | media {tom.mean():.1f}")
