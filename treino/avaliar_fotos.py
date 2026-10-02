"""Aplica a RevelaNet-Tom em fotos de verdade e monta pranchas antes/depois, para olhar o resultado.

uso: python avaliar_fotos.py <pasta_saida_do_treino> <pasta_das_pranchas> <foto ou pasta> [mais fotos...]

As fotos de teste não entram no treino; servem só para conferir.
"""
import os, sys
import numpy as np
import torch
from PIL import Image, ImageDraw
from revela_tom import RevelaTom, histograma, parametros, aplicar, luma

SAIDA, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
fotos = []
for a in sys.argv[3:]:
    if os.path.isdir(a):
        fotos += [os.path.join(a, f) for f in sorted(os.listdir(a)) if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]
    else:
        fotos.append(a)
rede = RevelaTom()
rede.load_state_dict(torch.load(os.path.join(SAIDA, "revela_tom.pt"), map_location="cpu"))
rede.eval()

H, por = 330, 6
celulas = []
for f in fotos:
    im = Image.open(f).convert("RGB")
    peq = torch.from_numpy(np.asarray(im.resize((128, 128), Image.BOX))).permute(2, 0, 1).float().unsqueeze(0) / 255
    k = H / im.height
    vis = im.resize((max(1, round(im.width * k)), H), Image.LANCZOS)
    x = torch.from_numpy(np.asarray(vis)).permute(2, 0, 1).float().unsqueeze(0) / 255
    with torch.no_grad():
        M, cv, sat, vib = parametros(rede(peq, histograma(peq)))
        y = aplicar(x, M, cv, sat, vib)
        g = torch.linspace(0, 1, 5).view(1, 1, 5, 1).repeat(1, 3, 1, 1)
        cinza = luma(aplicar(g, M, cv, sat, vib)).flatten().tolist()
    dep = Image.fromarray((y[0].permute(1, 2, 0).numpy() * 255).round().astype(np.uint8))
    info = f"{os.path.basename(f)} | luz {x.mean().item():.2f}>{y.mean().item():.2f} | cinzas " + " ".join(f"{v:.2f}" for v in cinza) + f" | sat {sat.item():.2f} vib {vib.item():+.2f}"
    print(info)
    w = min(vis.width, 372)
    par = Image.new("RGB", (750, H), (0, 0, 0))
    ox = (372 - w) // 2
    par.paste(vis.crop(((vis.width - w) // 2, 0, (vis.width - w) // 2 + w, H)), (ox, 0))
    par.paste(dep.crop(((vis.width - w) // 2, 0, (vis.width - w) // 2 + w, H)), (378 + ox, 0))
    d = ImageDraw.Draw(par)
    d.rectangle((0, 0, 750, 13), fill=(0, 0, 0))
    d.text((4, 1), info[:124], fill=(255, 255, 255))
    celulas.append(par)
for s in range(0, len(celulas), por):
    grupo = celulas[s:s + por]
    folha = Image.new("RGB", (1506, (H + 6) * ((len(grupo) + 1) // 2)), (34, 34, 34))
    for i, c in enumerate(grupo):
        folha.paste(c, ((i % 2) * 756, (i // 2) * (H + 6)))
    folha.save(os.path.join(OUT, f"tom{s // por}.png"))
print("pranchas:", (len(celulas) + por - 1) // por)
