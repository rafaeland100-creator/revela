"""Treina a RevelaNet-Tom na CPU.

uso: python treinar_tom.py <pasta_dados> <pasta_saida> [passos] [lote]

Precisa de tom128.npy (preparar_dados.py) e estat.npy (estatisticas.py).
Grava revela_tom.pt a cada medição e exporta revela_tom.onnx no fim.
"""
import os, sys, time, json
import numpy as np
import torch
import torch.nn.functional as F
from revela_tom import RevelaTom, Exportavel, parametros, aplicar, histograma, estragar, curadoria, luma, K, NH

DADOS, SAIDA = sys.argv[1], sys.argv[2]
PASSOS = int(sys.argv[3]) if len(sys.argv) > 3 else 4500
LOTE = int(sys.argv[4]) if len(sys.argv) > 4 else 96
NVAL, MEDIR = 300, 150
os.makedirs(SAIDA, exist_ok=True)
torch.set_num_threads(6)
torch.manual_seed(3)

sel = np.nonzero(curadoria(np.load(os.path.join(DADOS, "estat.npy"))))[0]
dados = torch.from_numpy(np.load(os.path.join(DADOS, "tom128.npy"))[sel])  # (N,128,128,3) uint8
N = dados.shape[0]
treino, val = dados[:N - NVAL], dados[N - NVAL:]
print(f"fotos-alvo {N} | treino {treino.shape[0]} | validacao {val.shape[0]} | lote {LOTE} | passos {PASSOS}", flush=True)


def lote_f(t):
    return t.permute(0, 3, 1, 2).float() / 255


def recorte(x, g):
    """Corte aleatório (mesmo para o lote) e espelho: dificulta decorar as fotos."""
    if torch.rand(1, generator=g).item() < 0.5:
        x = x.flip(3)
    if torch.rand(1, generator=g).item() < 0.7:
        c = int(128 * (0.72 + 0.28 * torch.rand(1, generator=g).item()))
        ox = int(torch.randint(0, 129 - c, (1,), generator=g)); oy = int(torch.randint(0, 129 - c, (1,), generator=g))
        x = F.interpolate(x[:, :, oy:oy + c, ox:ox + c], size=128, mode="bilinear", align_corners=False, antialias=True).clamp(0, 1)
    return x


def perda(saida, alvo, curvas, M):
    d = saida - alvo
    rec = torch.sqrt(d * d + 1e-6).mean()
    cs, ca = saida - luma(saida), alvo - luma(alvo)
    cor = (cs - ca).abs().mean()
    baixa = (F.avg_pool2d(saida, 16) - F.avg_pool2d(alvo, 16)).abs().mean()
    d2 = curvas[:, :, 2:] - 2 * curvas[:, :, 1:-1] + curvas[:, :, :-2]
    suave = (d2 * d2).mean() * (K - 1) ** 2
    mat = ((M - torch.eye(3)) ** 2).mean()
    return rec + 0.6 * cor + 0.5 * baixa + 0.05 * suave + 0.02 * mat, rec


def psnr(a, b):
    return 10 * torch.log10(1 / ((a - b) ** 2).flatten(1).mean(1).clamp(min=1e-8))


def erro(a, b):
    return (a - b).abs().flatten(1).mean(1) * 255


rede = RevelaTom()
print("parametros da rede:", sum(p.numel() for p in rede.parameters()), flush=True)
opt = torch.optim.AdamW(rede.parameters(), lr=2e-3, weight_decay=1e-4)
sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=2e-3, total_steps=PASSOS, pct_start=0.06)

# validação fixa: as mesmas fotos estragadas do mesmo jeito em todas as medições
gv = torch.Generator().manual_seed(99)
val_alvo = lote_f(val)
val_ent = estragar(val_alvo, gv, identidade=0.0)
val_hist = histograma(val_ent)
val_hist0 = histograma(val_alvo)
e0 = erro(val_ent, val_alvo)
print(f"validacao sem correcao: erro medio {e0.mean():.2f} | mediana {e0.median():.2f} | PSNR mediana {psnr(val_ent, val_alvo).median():.2f} dB", flush=True)


def medir():
    rede.eval()
    with torch.no_grad():
        s, s0 = [], []
        for i in range(0, NVAL, 100):
            s.append(aplicar(val_ent[i:i + 100], *parametros(rede(val_ent[i:i + 100], val_hist[i:i + 100]))))
            s0.append(aplicar(val_alvo[i:i + 100], *parametros(rede(val_alvo[i:i + 100], val_hist0[i:i + 100]))))
        s, s0 = torch.cat(s), torch.cat(s0)
    rede.train()
    e = erro(s, val_alvo)
    return {"erro": e.mean().item(), "mediana": e.median().item(), "psnr": psnr(s, val_alvo).median().item(),
            "melhorou": (e < e0).float().mean().item(), "boa_intacta": erro(s0, val_alvo).mean().item()}


def exportar(nome):
    rede.eval()
    exp = Exportavel(rede).eval()
    caminho = os.path.join(SAIDA, nome)
    torch.onnx.export(exp, (torch.rand(1, 3, 128, 128), torch.full((1, NH), 1 / 32)), caminho, input_names=["img", "hist"], output_names=["params"], opset_version=17, dynamo=False)
    rede.train()
    return caminho


g = torch.Generator().manual_seed(5)
t0, soma, n, log = time.time(), 0.0, 0, []
rede.train()
for passo in range(1, PASSOS + 1):
    idx = torch.randint(0, treino.shape[0], (LOTE,), generator=g)
    alvo = recorte(lote_f(treino[idx]), g)
    ent = estragar(alvo, g)
    M, curvas, sat, vib = parametros(rede(ent, histograma(ent)))
    saida = aplicar(ent, M, curvas, sat, vib)
    L, rec = perda(saida, alvo, curvas, M)
    opt.zero_grad(set_to_none=True)
    L.backward()
    torch.nn.utils.clip_grad_norm_(rede.parameters(), 2.0)
    opt.step(); sched.step()
    soma += rec.item(); n += 1
    if passo % MEDIR == 0 or passo == PASSOS:
        m = medir()
        m.update({"passo": passo, "treino": soma / n * 255, "min": (time.time() - t0) / 60})
        log.append(m); soma = n = 0
        torch.save(rede.state_dict(), os.path.join(SAIDA, "revela_tom.pt"))
        json.dump(log, open(os.path.join(SAIDA, "treino_tom.json"), "w"), indent=1)
        print(f"passo {passo:5d}/{PASSOS} | treino {m['treino']:.2f} | val erro {m['erro']:.2f} (sem correcao {e0.mean():.2f}) mediana {m['mediana']:.2f} | PSNR {m['psnr']:.2f} dB | melhorou {m['melhorou'] * 100:.0f}% | foto boa mexida em {m['boa_intacta']:.2f} | {m['min']:.1f} min", flush=True)
exportar("revela_tom.onnx")
print("FIM", flush=True)
