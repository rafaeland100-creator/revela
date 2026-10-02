"""RevelaNet-Tom: a rede própria do Revela para luz e cor.

A rede olha a foto reduzida (128x128) junto com o histograma e devolve uma correção global:
matriz de cor 3x3, uma curva monotônica por canal (17 pontos) e saturação/vibração.
Por ser global, a correção não cria halo, fantasma nem borda falsa.

Ela aprende por "estragar e recuperar": pegamos fotos bem tratadas, estragamos do jeito que
foto de celular costuma sair (escura, lavada, amarelada, sem cor) e treinamos a rede para
devolver a original. O app aplica a mesma transformação em JavaScript (função tomApply).
"""
import math
import torch
import torch.nn as nn
import torch.nn.functional as F

K = 17                 # pontos de cada curva
NB = 32                # faixas do histograma por canal
NS = 16                # faixas do histograma de saturação
NH = NB * 4 + NS       # R, G, B, luz e saturação
NP = 9 + 3 * K + 2     # saída: matriz, curvas, saturação, vibração
C0 = math.log(math.e - 1)  # softplus(C0) = 1


def luma(x):
    return 0.2126 * x[:, 0:1] + 0.7152 * x[:, 1:2] + 0.0722 * x[:, 2:3]


def histograma(x):
    """x: (B,3,H,W) em 0..1 -> (B, NH); cada bloco soma 1."""
    B = x.shape[0]
    y = luma(x)
    mx, mn = x.amax(1, keepdim=True), x.amin(1, keepdim=True)
    s = (mx - mn) / (mx + 1e-4)

    def h(v, nb):
        idx = (v.clamp(0, 1) * nb).long().clamp(max=nb - 1).flatten(1)
        out = torch.zeros(B, nb, device=x.device)
        out.scatter_add_(1, idx, torch.ones_like(idx, dtype=torch.float32))
        return out / idx.shape[1]

    return torch.cat([h(x[:, 0], NB), h(x[:, 1], NB), h(x[:, 2], NB), h(y[:, 0], NB), h(s[:, 0], NS)], 1)


class Bloco(nn.Module):
    def __init__(self, i, o):
        super().__init__()
        self.c = nn.Conv2d(i, o, 3, 2, 1, bias=False)
        self.b = nn.BatchNorm2d(o)

    def forward(self, x):
        return F.relu(self.b(self.c(x)))


class RevelaTom(nn.Module):
    def __init__(self, larg=(16, 32, 64, 96, 128)):
        super().__init__()
        blocos, i = [], 3
        for o in larg:
            blocos.append(Bloco(i, o))
            i = o
        self.conv = nn.Sequential(*blocos)
        self.hist = nn.Sequential(nn.Linear(NH, 96), nn.ReLU())
        self.fc = nn.Sequential(nn.Linear(i * 2 + 96, 256), nn.ReLU(), nn.Linear(256, NP))
        nn.init.zeros_(self.fc[-1].weight)
        nn.init.zeros_(self.fc[-1].bias)

    def forward(self, img, hist):
        f = self.conv(img * 2 - 1)
        f = torch.cat([f.mean((2, 3)), f.amax((2, 3))], 1)
        return self.fc(torch.cat([f, self.hist(hist * NB)], 1))


def parametros(raw):
    """Saída crua da rede -> (matriz Bx3x3, curvas Bx3xK, saturação Bx1, vibração Bx1).
    Com a saída zerada dá a transformação identidade."""
    B = raw.shape[0]
    M = torch.eye(3, device=raw.device).unsqueeze(0) + 0.5 * raw[:, :9].reshape(B, 3, 3)
    a = raw[:, 9:9 + 3 * K].reshape(B, 3, K)
    y0 = 0.25 * a[:, :, :1]
    inc = F.softplus(a[:, :, 1:] + C0) / (K - 1)
    curvas = torch.cat([y0, y0 + torch.cumsum(inc, 2)], 2)
    sat = F.softplus(raw[:, 9 + 3 * K:10 + 3 * K] + C0)
    vib = torch.tanh(raw[:, 10 + 3 * K:11 + 3 * K])
    return M, curvas, sat, vib


def aplicar(x, M, curvas, sat, vib):
    """Aplica a correção global em x (B,3,H,W), valores sRGB em 0..1."""
    B, _, H, W = x.shape
    u = torch.einsum("bij,bjhw->bihw", M, x).clamp(0, 1)
    t = u * (K - 1)
    i = t.detach().floor().clamp(max=K - 2)
    f = (t - i).flatten(2)
    i = i.long().flatten(2)
    a = torch.gather(curvas, 2, i)
    b = torch.gather(curvas, 2, i + 1)
    v = (a + (b - a) * f).reshape(B, 3, H, W).clamp(0, 1)
    Y = luma(v)
    mx, mn = v.amax(1, keepdim=True), v.amin(1, keepdim=True)
    s = (mx - mn) / (mx + 1e-4)
    fac = sat.reshape(B, 1, 1, 1) + vib.reshape(B, 1, 1, 1) * (1 - s)
    return (Y + (v - Y) * fac).clamp(0, 1)


class Exportavel(nn.Module):
    """Versão para o app: devolve os 62 números já prontos para aplicar."""

    def __init__(self, rede):
        super().__init__()
        self.rede = rede

    def forward(self, img, hist):
        M, curvas, sat, vib = parametros(self.rede(img, hist))
        return torch.cat([M.flatten(1), curvas.flatten(1), sat, vib], 1)


def curadoria(estat):
    """Escolhe as fotos que servem de alvo: preto firme, branco presente, contraste e cor saudáveis.
    É essa escolha que define o "jeito" que a rede aprende a dar às fotos. Fotos foscas, lavadas
    ou sem cor ficam de fora; preto e branco de verdade entra, para a rede aprender a não pintá-las.
    estat: colunas p01, p50, p99, desvio da luz, saturação média, fração de pixels com cor."""
    p01, p50, p99, dv, sat, fc = estat.T
    pb = fc < 0.01
    return (p01 <= 0.11) & (p99 >= 0.82) & (dv >= 0.145) & (p50 >= 0.10) & (p50 <= 0.80) & (((sat >= 0.13) & (sat <= 0.69)) | pb)


def s2l(x):
    return torch.where(x <= 0.04045, x / 12.92, ((x.clamp(min=0.04045) + 0.055) / 1.055) ** 2.4)


def l2s(x):
    return torch.where(x <= 0.0031308, x * 12.92, 1.055 * x.clamp(min=0.0031308) ** (1 / 2.4) - 0.055)


def estragar(x, g, forca=1.0, identidade=0.12):
    """Transforma fotos boas em fotos com os defeitos comuns de celular.
    x: (B,3,H,W) em 0..1; g: torch.Generator. Devolve a versão estragada, já em 8 bits."""
    B = x.shape[0]

    def n(sig):
        return torch.randn(B, 1, 1, 1, generator=g) * sig

    def u():
        return torch.rand(B, 1, 1, 1, generator=g)

    def on(p):
        return (u() < p).float()

    sev = (u() ** 0.7) * (u() >= identidade).float() * forca
    ev = torch.where(u() < 0.62, -n(0.9).abs(), n(0.5).abs()) * on(0.7) * sev        # escura é mais comum
    temp = n(0.16) * on(0.65) * sev                                                   # amarelada/azulada
    tint = n(0.08) * on(0.5) * sev                                                    # esverdeada/magenta
    con = torch.exp((n(0.25) - 0.15) * on(0.7) * sev)                                 # lavada é mais comum
    gam = torch.exp(n(0.22) * on(0.5) * sev)
    lift = (n(0.08).abs() * on(0.45) * sev).clamp(max=0.25)                           # névoa, preto cinza
    sat = torch.exp((n(0.3) - 0.15) * on(0.7) * sev)                                  # cor apagada
    ruido = 0.02 * u() * on(0.4) * sev

    lin = s2l(x) * torch.pow(2.0, ev) * torch.cat([torch.exp(temp), torch.exp(tint), torch.exp(-temp)], 1)
    y = l2s(lin.clamp(0, 1))
    y = ((y - 0.5) * con + 0.5).clamp(0, 1)
    y = y.clamp(min=1e-5) ** gam
    nevoa = 1 + 0.25 * torch.randn(B, 3, 1, 1, generator=g)
    y = y * (1 - lift) + lift * nevoa.clamp(0.5, 1.5)
    Y = luma(y)
    y = Y + (y - Y) * sat
    y = y + torch.randn(x.shape, generator=g) * ruido
    return (y.clamp(0, 1) * 255).round() / 255
