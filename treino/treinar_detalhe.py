"""Treina a RevelaNet-Detalhe na CPU.

uso: python treinar_detalhe.py <pasta_dados> <pasta_saida> [passos] [lote] [canais] [camadas] [nome]

Precisa de det96.npy (preparar_dados.py). Grava revela_detalhe.pt e, no fim, revela_detalhe.onnx.
"""
import os, sys, time, json, math
import numpy as np
import torch
import torch.nn.functional as F
from revela_detalhe import RevelaDetalhe, estragar_detalhe

DADOS, SAIDA = sys.argv[1], sys.argv[2]
PASSOS = int(sys.argv[3]) if len(sys.argv) > 3 else 5000
LOTE = int(sys.argv[4]) if len(sys.argv) > 4 else 24
CANAIS = int(sys.argv[5]) if len(sys.argv) > 5 else 32
CAMADAS = int(sys.argv[6]) if len(sys.argv) > 6 else 4
NOME = sys.argv[7] if len(sys.argv) > 7 else "revela_detalhe"
BORRAO = (sys.argv[8] if len(sys.argv) > 8 else "com") != "sem"   # "sem": treina só para ruído e JPEG
PERDA = sys.argv[9] if len(sys.argv) > 9 else "mista"            # "l2": só erro ao quadrado
NVAL, MEDIR, REC = 256, 1000, 64
os.makedirs(SAIDA, exist_ok=True)
torch.set_num_threads(6)
torch.manual_seed(4)

dados = torch.from_numpy(np.load(os.path.join(DADOS, "det96.npy")))  # (N,96,96,3) uint8
N = dados.shape[0]
treino, val = dados[:N - NVAL], dados[N - NVAL:]
print(f"recortes {N} | treino {treino.shape[0]} | validacao {NVAL} | lote {LOTE} | passos {PASSOS}", flush=True)


def lote_f(t):
    return t.permute(0, 3, 1, 2).float() / 255


def grad(x):
    return x[:, :, :, 1:] - x[:, :, :, :-1], x[:, :, 1:, :] - x[:, :, :-1, :]


def perda(s, a):
    d = s - a
    rec = torch.sqrt(d * d + 1e-6).mean()
    if PERDA == "l2":
        return 100 * (d * d).mean(), rec
    gx, gy = grad(s); hx, hy = grad(a)
    # erro absoluto + erro ao quadrado (puxa mais os recortes muito borrados) + bordas
    return rec + 10 * (d * d).mean() + 0.5 * ((gx - hx).abs().mean() + (gy - hy).abs().mean()), rec


def psnr(a, b, quais=None):
    """PSNR do conjunto (erro somado). A média de PSNR por recorte enganava: os recortes que entram limpos
    valem 80 dB sem a rede e puxavam a média para baixo assim que a rede mexia um fio neles."""
    m = ((a - b) ** 2).flatten(1).mean(1)
    if quais is not None:
        m = m[quais]
    return 10 * torch.log10(1 / m.mean().clamp(min=1e-10))


rede = RevelaDetalhe(CANAIS, CAMADAS)
print(f"rede {CANAIS} canais x {CAMADAS} camadas | parametros:", sum(p.numel() for p in rede.parameters()), flush=True)
# passo de aprendizado baixo e com aquecimento: com 2e-3 a rede ficava presa em "não mexer em nada"
LR = float(sys.argv[10]) if len(sys.argv) > 10 else 1e-3
opt = torch.optim.Adam(rede.parameters(), lr=LR)


def lr_em(passo):
    if passo < 300:
        return LR * passo / 300
    return 1e-5 + (LR - 1e-5) * 0.5 * (1 + math.cos(math.pi * (passo - 300) / max(1, PASSOS - 300)))


gv = torch.Generator().manual_seed(77)
val_alvo = lote_f(val)
val_ent = estragar_detalhe(val_alvo, gv, BORRAO)
estragados = ((val_ent - val_alvo) ** 2).flatten(1).mean(1) > 1e-7
p0 = psnr(val_ent, val_alvo, estragados).item()
print(f"validacao sem a rede: PSNR {p0:.2f} dB ({int(estragados.sum())} recortes estragados)", flush=True)

g = torch.Generator().manual_seed(8)
t0, soma, n, log = time.time(), 0.0, 0, []
rede.train()
for passo in range(1, PASSOS + 1):
    idx = torch.randint(0, treino.shape[0], (LOTE,), generator=g)
    alvo = lote_f(treino[idx])
    if torch.rand(1, generator=g).item() < 0.5:
        alvo = alvo.flip(3)
    if torch.rand(1, generator=g).item() < 0.5:
        alvo = alvo.transpose(2, 3)
    ent = estragar_detalhe(alvo, g, BORRAO)
    # recorte em posição qualquer: a grade de blocos do JPEG cai cada vez num lugar, como numa foto já cortada
    ox, oy = (int(v) for v in torch.randint(0, 96 - REC + 1, (2,), generator=g))
    alvo, ent = alvo[:, :, oy:oy + REC, ox:ox + REC], ent[:, :, oy:oy + REC, ox:ox + REC]
    L, rec = perda(rede(ent), alvo)
    for grupo in opt.param_groups:
        grupo["lr"] = lr_em(passo)
    opt.zero_grad(set_to_none=True)
    L.backward()
    opt.step()
    soma += rec.item(); n += 1
    if passo % MEDIR == 0 or passo == PASSOS:
        rede.eval()
        with torch.no_grad():
            s = torch.cat([rede(val_ent[i:i + 64]) for i in range(0, NVAL, 64)]).clamp(0, 1)
            limpa = torch.cat([rede(val_alvo[i:i + 64]) for i in range(0, NVAL, 64)]).clamp(0, 1)
        rede.train()
        pv = psnr(s, val_alvo, estragados).item()
        m = {"passo": passo, "treino": soma / n * 255, "psnr": pv, "ganho": pv - p0, "limpa": psnr(limpa, val_alvo).item(), "min": (time.time() - t0) / 60}
        log.append(m); soma = n = 0
        torch.save(rede.state_dict(), os.path.join(SAIDA, NOME + ".pt"))
        json.dump(log, open(os.path.join(SAIDA, NOME + ".json"), "w"), indent=1)
        print(f"passo {passo:5d}/{PASSOS} | treino {m['treino']:.2f} | val PSNR {pv:.2f} dB (sem a rede {p0:.2f}, ganho {m['ganho']:+.2f}) | foto limpa continua em {m['limpa']:.1f} dB | {m['min']:.1f} min", flush=True)
rede.eval()
torch.onnx.export(rede, (torch.rand(1, 3, 128, 128),), os.path.join(SAIDA, NOME + ".onnx"), input_names=["x"], output_names=["y"], opset_version=17, dynamo=False, dynamic_axes={"x": {2: "h", 3: "w"}, "y": {2: "h", 3: "w"}})
print("FIM", flush=True)
