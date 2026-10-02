"""Exporta a RevelaNet-Luz treinada para o formato que o app lê (revela_luz.bin) e gera vetores de teste.

uso: python exportar_luz.py <pasta_saida_do_treino> <destino.bin> [aleatoria]

Com "aleatoria" no fim, em vez da rede treinada grava uma rede com pesos sorteados (sempre os mesmos). Ela não
serve para foto nenhuma; serve para o teste que confere a conta do app contra a do PyTorch, porque dá ganhos
grandes e variados em qualquer imagem.

Formato do .bin (tudo little-endian):
  16 inteiros de 32 bits: "RVL1", versão, lado do mapa (16), larguras das convoluções (3), largura da mistura,
                          ganho máximo x1000, raio do filtro guiado em 128 px, eps x1e6, zeros
  depois números de 32 bits em ponto flutuante, na ordem: as 4 convoluções 3x3 (pesos O×I×3×3 já com o
  BatchNorm embutido, depois os O desvios; as três primeiras têm passo 2, a quarta tem dilatação 2), o contexto
  (pesos, desvios), a mistura 1x1 (pesos, desvios) e a saída 3x3 (pesos, desvio).
O app refaz a conta em JavaScript puro.
"""
import os, sys, json, struct
import numpy as np
import torch
from revela_luz import RevelaLuz, ampliar, luma, G, GMAX, RAIO, EPS

SAIDA, DEST = sys.argv[1], sys.argv[2]
rede = RevelaLuz()
if len(sys.argv) > 3 and sys.argv[3] == "aleatoria":
    torch.manual_seed(123)
    rede = RevelaLuz()
    for m in rede.modules():
        if isinstance(m, torch.nn.BatchNorm2d):
            m.running_mean.normal_(0, 0.3); m.running_var.uniform_(0.5, 1.5); m.weight.data.uniform_(0.6, 1.4); m.bias.data.normal_(0, 0.2)
    torch.nn.init.normal_(rede.out.weight, 0, 0.4); torch.nn.init.normal_(rede.out.bias, 0, 0.1)
else:
    rede.load_state_dict(torch.load(os.path.join(SAIDA, "revela_luz.pt"), map_location="cpu"))
rede.eval()

partes, larg = [], []
for bloco in rede.conv:
    w, bn = bloco.c.weight.detach(), bloco.b
    escala = bn.weight.detach() / torch.sqrt(bn.running_var + bn.eps)
    partes += [(w * escala.view(-1, 1, 1, 1)).numpy(), (bn.bias.detach() - bn.running_mean * escala).numpy()]
    larg.append(w.shape[0])
partes += [rede.ctx[0].weight.detach().numpy(), rede.ctx[0].bias.detach().numpy()]
partes += [rede.mix.weight.detach().numpy(), rede.mix.bias.detach().numpy(), rede.out.weight.detach().numpy(), rede.out.bias.detach().numpy()]
assert larg[2] == larg[3]
cab = struct.pack("<16I", 0x314C5652, 1, G, larg[0], larg[1], larg[2], rede.mix.out_channels, round(GMAX * 1000), RAIO, round(EPS * 1e6), 0, 0, 0, 0, 0, 0)
corpo = b"".join(np.ascontiguousarray(p, dtype="<f4").tobytes() for p in partes)
os.makedirs(os.path.dirname(DEST) or ".", exist_ok=True)
with open(DEST, "wb") as f:
    f.write(cab + corpo)
print(f"{DEST}: {os.path.getsize(DEST) / 1024:.0f} KB | {len(corpo) // 4} números")

# vetores de teste (imagem sintética, nunca uma foto de alguém): o app tem de chegar ao mesmo mapa de ganho
g = torch.Generator().manual_seed(42)
img = torch.rand(1, 3, 8, 8, generator=g).repeat_interleave(16, 2).repeat_interleave(16, 3) * 0.7 + 0.1
img[:, :, 40:100, 30:90] *= 0.25                      # uma região escura no meio, para a rede ter o que levantar
img = (img * 255).round() / 255
with torch.no_grad():
    ganho = rede(img)
    amp = ampliar(ganho, luma(img)).clamp(-GMAX, GMAX)
pts = [(8, 8), (64, 64), (70, 40), (100, 100), (30, 90), (120, 5), (45, 35), (95, 85)]
json.dump({"img": (img[0].permute(1, 2, 0).reshape(-1) * 255).round().int().tolist(), "ganho": ganho.flatten().tolist(),
           "pontos": pts, "ampliado": [amp[0, 0, y, x].item() for (x, y) in pts]}, open(os.path.splitext(DEST)[0] + "_teste.json", "w"))
print("vetores de teste gravados | ganho min %.3f max %.3f | no meio escuro %.3f" % (ganho.min(), ganho.max(), amp[0, 0, 70, 60]))
