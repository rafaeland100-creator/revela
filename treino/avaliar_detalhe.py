"""Avalia a RevelaNet-Detalhe: números na validação e pranchas de recortes de fotos de verdade.

uso: python avaliar_detalhe.py <pasta_dados> <pasta_saida_do_treino> <nome> <pasta_das_pranchas> [fotos...]

A prancha mostra, para cada foto, um recorte ampliado 3x: como está | depois da rede.
"""
import os, sys
import numpy as np
import torch
from PIL import Image
from revela_detalhe import RevelaDetalhe, estragar_detalhe

DADOS, SAIDA, NOME, OUT = sys.argv[1:5]
os.makedirs(OUT, exist_ok=True)
torch.set_num_threads(6)
rede = RevelaDetalhe()
rede.load_state_dict(torch.load(os.path.join(SAIDA, NOME + ".pt"), map_location="cpu"))
rede.eval()

d = torch.from_numpy(np.load(os.path.join(DADOS, "det96.npy"), mmap_mode="r")[-256:].copy())
alvo = d.permute(0, 3, 1, 2).float() / 255
ent = estragar_detalhe(alvo, torch.Generator().manual_seed(77))
with torch.no_grad():
    sai = torch.cat([rede(ent[i:i + 64]) for i in range(0, 256, 64)]).clamp(0, 1)
    limpa = torch.cat([rede(alvo[i:i + 64]) for i in range(0, 256, 64)]).clamp(0, 1)
mse = lambda a, b: ((a - b) ** 2).flatten(1).mean(1)
m0, m1 = mse(ent, alvo), mse(sai, alvo)
estr = m0 > 1e-7
db = lambda v: 10 * np.log10(1 / max(1e-12, float(v)))
print(f"validação ({int(estr.sum())} recortes estragados de 256):")
print(f"  PSNR do conjunto (erro somado): sem a rede {db(m0[estr].mean()):.2f} dB -> com a rede {db(m1[estr].mean()):.2f} dB")
print(f"  ganho por recorte: mediana {np.median((10 * torch.log10(m0[estr] / m1[estr])).numpy()):+.2f} dB | melhorou em {(m1[estr] < m0[estr]).float().mean() * 100:.0f}%")
print(f"  foto já limpa: a rede mexe {((limpa - alvo).abs().mean() * 255):.2f} de 255 em média (PSNR {db(mse(limpa, alvo).mean()):.1f} dB)")

celulas = []
for f in sys.argv[5:]:
    im = Image.open(f).convert("RGB")
    if max(im.size) > 1600:
        k = 1600 / max(im.size); im = im.resize((round(im.width * k) // 2 * 2, round(im.height * k) // 2 * 2), Image.LANCZOS)
    im = im.crop((0, 0, im.width // 2 * 2, im.height // 2 * 2))
    x = torch.from_numpy(np.asarray(im)).permute(2, 0, 1).float().unsqueeze(0) / 255
    with torch.no_grad():
        y = rede(x).clamp(0, 1)
    dep = Image.fromarray((y[0].permute(1, 2, 0).numpy() * 255).round().astype(np.uint8))
    print(f"{os.path.basename(f)}: {im.width}x{im.height} | mudança média {(y - x).abs().mean().item() * 255:.2f} de 255")
    cx, cy, r = im.width // 2, int(im.height * 0.38), 84
    cx, cy = min(max(r, cx), im.width - r), min(max(r, cy), im.height - r)
    caixa = (cx - r, cy - r, cx + r, cy + r)
    par = Image.new("RGB", (r * 6 * 2 + 6, r * 6), (0, 0, 0))
    par.paste(im.crop(caixa).resize((r * 6, r * 6), Image.BICUBIC), (0, 0))
    par.paste(dep.crop(caixa).resize((r * 6, r * 6), Image.BICUBIC), (r * 6 + 6, 0))
    celulas.append(par)
for s in range(0, len(celulas), 2):
    g = celulas[s:s + 2]
    folha = Image.new("RGB", (g[0].width, sum(c.height + 6 for c in g)), (34, 34, 34))
    y0 = 0
    for c in g:
        folha.paste(c, (0, y0)); y0 += c.height + 6
    folha.save(os.path.join(OUT, f"detalhe{s // 2}.png"))
print("pranchas:", (len(celulas) + 1) // 2)
