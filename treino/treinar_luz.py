"""Treina a RevelaNet-Luz (luz por região) na CPU.

uso: python treinar_luz.py <pasta_dados> <pasta_saida> [passos] [lote]

Precisa de tom128.npy (preparar_dados.py) e estat.npy (estatisticas.py). Usa as mesmas fotos-alvo
escolhidas para a RevelaNet-Tom. Grava revela_luz.pt a cada medição e o histórico em treino_luz.json.
"""
import os, sys, time, json
import numpy as np
import torch
import torch.nn.functional as F
from revela_tom import curadoria
from revela_luz import RevelaLuz, aplicar, estragar_luz, luma

DADOS, SAIDA = sys.argv[1], sys.argv[2]
PASSOS = int(sys.argv[3]) if len(sys.argv) > 3 else 4000
LOTE = int(sys.argv[4]) if len(sys.argv) > 4 else 64
NVAL, MEDIR = 300, 200
os.makedirs(SAIDA, exist_ok=True)
torch.set_num_threads(6)
torch.manual_seed(7)

sel = np.nonzero(curadoria(np.load(os.path.join(DADOS, "estat.npy"))))[0]
dados = torch.from_numpy(np.load(os.path.join(DADOS, "tom128.npy"))[sel])  # (N,128,128,3) uint8
N = dados.shape[0]
treino, val = dados[:N - NVAL], dados[N - NVAL:]
print(f"fotos-alvo {N} | treino {treino.shape[0]} | validacao {val.shape[0]} | lote {LOTE} | passos {PASSOS}", flush=True)


def lote_f(t):
    return t.permute(0, 3, 1, 2).float() / 255


def recorte(x, g):
    if torch.rand(1, generator=g).item() < 0.5:
        x = x.flip(3)
    if torch.rand(1, generator=g).item() < 0.7:
        c = int(128 * (0.72 + 0.28 * torch.rand(1, generator=g).item()))
        ox = int(torch.randint(0, 129 - c, (1,), generator=g)); oy = int(torch.randint(0, 129 - c, (1,), generator=g))
        x = F.interpolate(x[:, :, oy:oy + c, ox:ox + c], size=128, mode="bilinear", align_corners=False, antialias=True).clamp(0, 1)
    return x


def perda(saida, alvo, ganho):
    d = saida - alvo
    rec = torch.sqrt(d * d + 1e-6).mean()
    baixa = (F.avg_pool2d(saida, 16) - F.avg_pool2d(alvo, 16)).abs().mean()
    # o mapa de ganho deve ser suave e, sem motivo, ficar em zero
    tv = (ganho[:, :, 1:] - ganho[:, :, :-1]).abs().mean() + (ganho[:, :, :, 1:] - ganho[:, :, :, :-1]).abs().mean()
    return rec + 0.7 * baixa + 0.02 * tv + 0.01 * ganho.abs().mean(), rec


def erro(a, b):
    return (a - b).abs().flatten(1).mean(1) * 255


def erro_luz(a, b):
    """Erro só da luz em blocos grandes (16 px): é o que a rede se propõe a consertar."""
    return (F.avg_pool2d(luma(a), 16) - F.avg_pool2d(luma(b), 16)).abs().flatten(1).mean(1) * 255


rede = RevelaLuz()
print("parametros da rede:", sum(p.numel() for p in rede.parameters()), flush=True)
opt = torch.optim.AdamW(rede.parameters(), lr=2e-3, weight_decay=1e-4)
sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=2e-3, total_steps=PASSOS, pct_start=0.06)

gv = torch.Generator().manual_seed(99)
val_alvo = lote_f(val)
val_ent, _ = estragar_luz(val_alvo, gv, identidade=0.0)
e0, l0 = erro(val_ent, val_alvo), erro_luz(val_ent, val_alvo)
print(f"validacao sem correcao: erro medio {e0.mean():.2f} | mediana {e0.median():.2f} | erro de luz por regiao {l0.mean():.2f}", flush=True)


def medir():
    rede.eval()
    with torch.no_grad():
        s, s0, gm = [], [], []
        for i in range(0, NVAL, 100):
            a, _ = aplicar(val_ent[i:i + 100], rede(val_ent[i:i + 100]))
            b, g0 = aplicar(val_alvo[i:i + 100], rede(val_alvo[i:i + 100]))
            s.append(a); s0.append(b); gm.append(g0.abs().flatten(1).mean(1))
        s, s0, gm = torch.cat(s), torch.cat(s0), torch.cat(gm)
    rede.train()
    e = erro(s, val_alvo)
    return {"erro": e.mean().item(), "mediana": e.median().item(), "luz": erro_luz(s, val_alvo).mean().item(),
            "melhorou": (e < e0).float().mean().item(), "boa_intacta": erro(s0, val_alvo).mean().item(), "ganho_na_boa": gm.mean().item()}


g = torch.Generator().manual_seed(5)
t0, soma, n, log = time.time(), 0.0, 0, []
rede.train()
for passo in range(1, PASSOS + 1):
    idx = torch.randint(0, treino.shape[0], (LOTE,), generator=g)
    alvo = recorte(lote_f(treino[idx]), g)
    ent, _ = estragar_luz(alvo, g)
    ganho = rede(ent)
    saida, _ = aplicar(ent, ganho)
    L, rec = perda(saida, alvo, ganho)
    opt.zero_grad(set_to_none=True)
    L.backward()
    torch.nn.utils.clip_grad_norm_(rede.parameters(), 2.0)
    opt.step(); sched.step()
    soma += rec.item(); n += 1
    if passo % MEDIR == 0 or passo == PASSOS:
        m = medir()
        m.update({"passo": passo, "treino": soma / n * 255, "min": (time.time() - t0) / 60})
        log.append(m); soma = n = 0
        torch.save(rede.state_dict(), os.path.join(SAIDA, "revela_luz.pt"))
        json.dump(log, open(os.path.join(SAIDA, "treino_luz.json"), "w"), indent=1)
        print(f"passo {passo:5d}/{PASSOS} | treino {m['treino']:.2f} | val erro {m['erro']:.2f} (sem correcao {e0.mean():.2f}) mediana {m['mediana']:.2f} | luz por regiao {m['luz']:.2f} (era {l0.mean():.2f}) | melhorou {m['melhorou'] * 100:.0f}% | foto boa mexida em {m['boa_intacta']:.2f} | {m['min']:.1f} min", flush=True)
print("FIM", flush=True)
