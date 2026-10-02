"""Baixa uma amostra reduzida do Unsplash Lite Dataset para treinar a IA do Revela.

As fotos servem só para treino (termos do Unsplash Lite: pode treinar modelos, inclusive
para uso comercial; não pode republicar as fotos). Por isso elas ficam fora do repositório.

uso: python baixar_fotos.py <pasta_dados> [quantidade] [largura]
"""
import csv, os, random, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

DADOS = sys.argv[1]
N = int(sys.argv[2]) if len(sys.argv) > 2 else 12000
W = int(sys.argv[3]) if len(sys.argv) > 3 else 384
IMG = os.path.join(DADOS, "img")
os.makedirs(IMG, exist_ok=True)
csv.field_size_limit(10**9)

rows = list(csv.DictReader(open(os.path.join(DADOS, "photos.tsv"), encoding="utf-8"), delimiter="\t"))
PESSOAS = ["person", "woman", "man ", "girl", "boy", "people", "portrait", "face", "child", "couple", "bride", "selfie"]
OUTROS = ["food", "city", "street", "building", "room", "indoor", "car", "night", "dog", "cat"]

def tem(r, termos):
    d = ((r.get("ai_description") or "") + " " + (r.get("photo_description") or "")).lower()
    return any(t in d for t in termos)

random.seed(7)
pessoas = [r for r in rows if tem(r, PESSOAS)]
outros = [r for r in rows if not tem(r, PESSOAS) and tem(r, OUTROS)]
resto = [r for r in rows if not tem(r, PESSOAS) and not tem(r, OUTROS)]
random.shuffle(resto)
escolha = pessoas + outros + resto[: max(0, N - len(pessoas) - len(outros))]
escolha = escolha[:N]
print(f"pessoas {len(pessoas)} | cidade/comida/animais {len(outros)} | natureza {len(escolha) - len(pessoas) - len(outros)} | total {len(escolha)}", flush=True)

def baixar(r):
    dst = os.path.join(IMG, r["photo_id"] + ".jpg")
    if os.path.exists(dst) and os.path.getsize(dst) > 2000:
        return 0
    url = r["photo_image_url"] + f"?w={W}&q=82&fm=jpg&fit=max"
    for tent in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "revela-treino/0.1"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            if len(data) > 2000:
                with open(dst, "wb") as f:
                    f.write(data)
                return len(data)
        except Exception:
            time.sleep(1.5 * (tent + 1))
    return -1

t0 = time.time(); ok = falhou = bytes_ = 0
with ThreadPoolExecutor(max_workers=12) as ex:
    futs = [ex.submit(baixar, r) for r in escolha]
    for i, f in enumerate(as_completed(futs), 1):
        v = f.result()
        if v < 0: falhou += 1
        else: ok += 1; bytes_ += v
        if i % 500 == 0 or i == len(futs):
            print(f"{i}/{len(futs)} | ok {ok} falhas {falhou} | {bytes_ / 1e6:.0f} MB | {time.time() - t0:.0f} s", flush=True)
ids_pessoas = {r["photo_id"] for r in pessoas}
with open(os.path.join(DADOS, "lista.txt"), "w", encoding="utf-8") as f:
    for r in escolha:
        p = os.path.join(IMG, r["photo_id"] + ".jpg")
        if os.path.exists(p) and os.path.getsize(p) > 2000:
            f.write(r["photo_id"] + "\t" + ("p" if r["photo_id"] in ids_pessoas else "o") + "\n")
print("PRONTO", flush=True)
