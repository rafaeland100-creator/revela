"""Aplica a RevelaNet-Tom e depois a RevelaNet-Luz em fotos de verdade e monta pranchas para olhar.

uso: python avaliar_luz.py <pasta_saida_do_treino> <pasta_das_pranchas> <foto ou pasta> [mais fotos...]

Cada linha da prancha: original | só a correção global (Tom) | global + luz por região | mapa de ganho
(cinza médio = não mexe, claro = levanta, escuro = segura). As fotos de teste não entram no treino.
"""
import os, sys
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, ImageDraw
from revela_tom import RevelaTom, histograma, parametros, aplicar as aplicar_tom
from revela_luz import RevelaLuz, ampliar, luma, GMAX, RAIO, EPS

SAIDA, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
fotos = []
for a in sys.argv[3:]:
    if os.path.isdir(a):
        fotos += [os.path.join(a, f) for f in sorted(os.listdir(a)) if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]
    else:
        fotos.append(a)
tom = RevelaTom(); tom.load_state_dict(torch.load(os.path.join(SAIDA, "revela_tom.pt"), map_location="cpu")); tom.eval()
luz = RevelaLuz(); luz.load_state_dict(torch.load(os.path.join(SAIDA, "revela_luz.pt"), map_location="cpu")); luz.eval()

H, por = 300, 5
linhas = []
for f in fotos:
    im = Image.open(f).convert("RGB")
    peq = torch.from_numpy(np.asarray(im.resize((128, 128), Image.BOX))).permute(2, 0, 1).float().unsqueeze(0) / 255
    k = H / im.height
    vis = im.resize((max(1, round(im.width * k)), H), Image.LANCZOS)
    x = torch.from_numpy(np.asarray(vis)).permute(2, 0, 1).float().unsqueeze(0) / 255
    with torch.no_grad():
        P = parametros(tom(peq, histograma(peq)))
        y = aplicar_tom(x, *P)                       # correção global na imagem de exibição
        peq2 = aplicar_tom(peq, *P)                  # a rede de luz olha a miniatura já corrigida
        ganho = luz(peq2)
        # no tamanho de exibição o raio do filtro guiado cresce na mesma proporção
        r = max(2, round(RAIO * max(y.shape[-2:]) / 128))
        Gm = ampliar(ganho, luma(y), r=r, eps=EPS).clamp(-GMAX, GMAX)
        z = (y * torch.exp(Gm)).clamp(0, 1)
    def img(t):
        return Image.fromarray((t[0].permute(1, 2, 0).numpy() * 255).round().astype(np.uint8))
    mapa = Image.fromarray(((Gm[0, 0].numpy() / GMAX * 0.5 + 0.5).clip(0, 1) * 255).astype(np.uint8)).convert("RGB")
    info = f"{os.path.basename(f)} | ganho min {Gm.min().item():+.2f} max {Gm.max().item():+.2f} medio {Gm.abs().mean().item():.2f} | luz {y.mean().item():.2f}>{z.mean().item():.2f}"
    print(info)
    w = vis.width
    lin = Image.new("RGB", (w * 4 + 18, H + 14), (20, 20, 20))
    for i, c in enumerate([vis, img(y), img(z), mapa]):
        lin.paste(c, (i * (w + 6), 14))
    ImageDraw.Draw(lin).text((4, 1), info + "   [original | global | global + luz por regiao | mapa de ganho]", fill=(255, 255, 255))
    linhas.append(lin)
for s in range(0, len(linhas), por):
    grupo = linhas[s:s + por]
    folha = Image.new("RGB", (max(c.width for c in grupo), sum(c.height + 6 for c in grupo)), (34, 34, 34))
    yy = 0
    for c in grupo:
        folha.paste(c, (0, yy)); yy += c.height + 6
    folha.save(os.path.join(OUT, f"luz{s // por}.png"))
print("pranchas:", (len(linhas) + por - 1) // por)
