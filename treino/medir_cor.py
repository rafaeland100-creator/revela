"""Mede o quanto a RevelaNet-Tom corrige uma dominante de cor (foto amarelada ou azulada).

uso: python medir_cor.py <pasta_saida_do_treino> <foto> [mais fotos...]

Para cada foto aplica tintas de força crescente e mostra o que a rede faz com um cinza médio:
se ela compensa a tinta, o cinza sai puxado para o lado oposto.
"""
import os, sys
import numpy as np
import torch
from PIL import Image
from revela_tom import RevelaTom, histograma, parametros, aplicar

rede = RevelaTom()
rede.load_state_dict(torch.load(os.path.join(sys.argv[1], "revela_tom.pt"), map_location="cpu"))
rede.eval()
TINTAS = {"sem tinta": (1, 1, 1), "amarela leve": (1, 0.94, 0.85), "amarela forte": (1, 0.843, 0.604), "azul leve": (0.87, 0.94, 1), "azul forte": (0.68, 0.84, 1), "verde": (0.9, 1, 0.86)}
cinza = torch.full((1, 3, 1, 1), 0.5)
for f in sys.argv[2:]:
    im = Image.open(f).convert("RGB").resize((128, 128), Image.BOX)
    x0 = torch.from_numpy(np.asarray(im)).permute(2, 0, 1).float().unsqueeze(0) / 255
    print(os.path.basename(f))
    for nome, t in TINTAS.items():
        x = (x0 * torch.tensor(t).view(1, 3, 1, 1)).clamp(0, 1)
        x = (x * 255).round() / 255
        with torch.no_grad():
            P = parametros(rede(x, histograma(x)))
            y = aplicar(x, *P)
            c = aplicar(cinza * torch.tensor(t).view(1, 3, 1, 1), *P).flatten()
        rb_in = (x[0, 0].mean() / x[0, 2].mean()).item(); rb_out = (y[0, 0].mean() / y[0, 2].mean()).item(); rb0 = (x0[0, 0].mean() / x0[0, 2].mean()).item()
        desfeito = 0.0 if abs(rb_in - rb0) < 1e-6 else (rb_in - rb_out) / (rb_in - rb0)
        print(f"   {nome:14s} vermelho/azul: original {rb0:.2f} | com tinta {rb_in:.2f} | depois da rede {rb_out:.2f} | tinta desfeita {desfeito * 100:5.0f}% | cinza tingido vira ({c[0]:.2f}, {c[1]:.2f}, {c[2]:.2f})")
