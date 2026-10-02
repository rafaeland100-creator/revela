"""Exporta a RevelaNet-Tom treinada para o formato que o app lê (revela_tom.bin) e gera vetores de teste.

uso: python exportar_tom.py <pasta_saida_do_treino> <destino.bin> [foto_de_teste.jpg]

Formato do .bin (tudo little-endian):
  16 inteiros de 32 bits: "RVT1", versão, K, NB, NS, nº de convoluções, larguras (5), camada do histograma,
                          camada oculta, nº de saídas, 0, 0
  depois números de 32 bits em ponto flutuante, na ordem: cada convolução (pesos O×I×3×3 já com o
  BatchNorm embutido, depois os O desvios), histograma (pesos, desvios), oculta (pesos, desvios), saída (pesos, desvios).
O app refaz a conta em JavaScript puro, sem depender de biblioteca de IA.
"""
import os, sys, json, struct
import numpy as np
import torch
from revela_tom import RevelaTom, Exportavel, histograma, parametros, aplicar, K, NB, NS, NP

SAIDA, DEST = sys.argv[1], sys.argv[2]
rede = RevelaTom()
rede.load_state_dict(torch.load(os.path.join(SAIDA, "revela_tom.pt"), map_location="cpu"))
rede.eval()

partes, larg = [], []
for bloco in rede.conv:
    w, bn = bloco.c.weight.detach(), bloco.b
    escala = bn.weight.detach() / torch.sqrt(bn.running_var + bn.eps)
    partes += [(w * escala.view(-1, 1, 1, 1)).numpy(), (bn.bias.detach() - bn.running_mean * escala).numpy()]
    larg.append(w.shape[0])
for lin in (rede.hist[0], rede.fc[0], rede.fc[2]):
    partes += [lin.weight.detach().numpy(), lin.bias.detach().numpy()]
cab = struct.pack("<16I", 0x31545652, 1, K, NB, NS, len(larg), *larg, rede.hist[0].out_features, rede.fc[0].out_features, NP, 0, 0)
corpo = b"".join(np.ascontiguousarray(p, dtype="<f4").tobytes() for p in partes)
os.makedirs(os.path.dirname(DEST) or ".", exist_ok=True)
with open(DEST, "wb") as f:
    f.write(cab + corpo)
print(f"{DEST}: {os.path.getsize(DEST) / 1024:.0f} KB | {len(corpo) // 4} números")

# vetores de teste: o app tem de chegar aos mesmos 62 números e às mesmas cores
g = torch.Generator().manual_seed(42)
if len(sys.argv) > 3:
    from PIL import Image
    im = Image.open(sys.argv[3]).convert("RGB").resize((128, 128), Image.BOX)
    img = torch.from_numpy(np.asarray(im)).permute(2, 0, 1).float().unsqueeze(0) / 255
else:
    img = (torch.rand(1, 3, 8, 8, generator=g).repeat_interleave(16, 2).repeat_interleave(16, 3) * 0.7 + 0.1)
    img = (img * 255).round() / 255
h = histograma(img)
with torch.no_grad():
    p = Exportavel(rede).eval()(img, h)
    cores = torch.tensor([[0.0, 0.0, 0.0], [1, 1, 1], [0.5, 0.5, 0.5], [0.8, 0.3, 0.2], [0.1, 0.6, 0.9], [0.9, 0.85, 0.2], [0.25, 0.2, 0.18], [0.62, 0.48, 0.4]])
    saida = aplicar(cores.t().reshape(1, 3, -1, 1), *parametros(rede(img, h))).reshape(3, -1).t()
json.dump({"img": (img[0].permute(1, 2, 0).reshape(-1) * 255).round().int().tolist(), "hist": h[0].tolist(), "params": p[0].tolist(),
           "cores": cores.tolist(), "saida": saida.tolist()}, open(os.path.splitext(DEST)[0] + "_teste.json", "w"))
print("vetores de teste gravados | primeiros parâmetros:", [round(v, 4) for v in p[0, :6].tolist()])
