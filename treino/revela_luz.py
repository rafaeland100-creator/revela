"""RevelaNet-Luz: a segunda rede própria do Revela, para a luz por região.

A RevelaNet-Tom corrige a foto inteira de uma vez (matriz de cor e curvas). O que ela não consegue é
tratar partes da foto de jeitos diferentes: levantar o rosto que ficou escuro contra a janela, segurar
o céu que estourou, desfazer a sombra que pegou metade da cena. Esta rede faz isso.

Ela olha a foto reduzida (128x128, já com a correção global) e devolve um mapa de ganho de luz de
16x16 pontos. O mapa é ampliado respeitando os contornos da foto (filtro guiado pela luminância), para
não criar halo, e multiplica a imagem. Ganho zero em todo lugar deixa a foto como está.

Aprende por "estragar e recuperar": fotos bem iluminadas recebem defeitos de luz por região (sombra
funda, claro estourado, degradê, vinheta, manchas) e a rede é treinada para devolver a original.
"""
import math
import torch
import torch.nn as nn
import torch.nn.functional as F

G = 16          # lado do mapa de ganho
GMAX = 1.1      # ganho máximo, em logaritmo natural do fator aplicado ao valor sRGB (1,1 ~ 3,5 EV de luz)
RAIO = 6        # raio do filtro guiado em 128 px (no app: o mesmo em proporção do tamanho)
EPS = 0.004


def luma(x):
    return 0.2126 * x[:, 0:1] + 0.7152 * x[:, 1:2] + 0.0722 * x[:, 2:3]


def s2l(x):
    return torch.where(x <= 0.04045, x / 12.92, ((x.clamp(min=0.04045) + 0.055) / 1.055) ** 2.4)


def l2s(x):
    return torch.where(x <= 0.0031308, x * 12.92, 1.055 * x.clamp(min=0.0031308) ** (1 / 2.4) - 0.055)


class Bloco(nn.Module):
    def __init__(self, i, o, passo=2, dil=1):
        super().__init__()
        self.c = nn.Conv2d(i, o, 3, passo, dil, dilation=dil, bias=False)
        self.b = nn.BatchNorm2d(o)

    def forward(self, x):
        return F.relu(self.b(self.c(x)))


class RevelaLuz(nn.Module):
    def __init__(self, larg=(16, 32, 48)):
        super().__init__()
        a, b, c = larg
        self.conv = nn.Sequential(Bloco(3, a), Bloco(a, b), Bloco(b, c), Bloco(c, c, 1, 2))   # 128 -> 16
        self.ctx = nn.Sequential(nn.Linear(c, c), nn.ReLU())                                  # o que a foto inteira diz
        self.mix = nn.Conv2d(2 * c, 32, 1)
        self.out = nn.Conv2d(32, 1, 3, 1, 1)
        nn.init.zeros_(self.out.weight)
        nn.init.zeros_(self.out.bias)

    def forward(self, img):
        f = self.conv(img * 2 - 1)
        g = self.ctx(f.mean((2, 3)))
        f = F.relu(self.mix(torch.cat([f, g[:, :, None, None].expand_as(f)], 1)))
        return GMAX * torch.tanh(self.out(f))          # (B,1,16,16), ganho em log


def caixa(x, r):
    return F.avg_pool2d(x, 2 * r + 1, 1, r, count_include_pad=False)


def ampliar(ganho, guia, r=RAIO, eps=EPS):
    """Mapa 16x16 -> tamanho da imagem, acompanhando os contornos da luminância (filtro guiado)."""
    P = F.interpolate(ganho, size=guia.shape[-2:], mode="bilinear", align_corners=False)
    mI, mP = caixa(guia, r), caixa(P, r)
    a = (caixa(guia * P, r) - mI * mP) / (caixa(guia * guia, r) - mI * mI + eps)
    b = mP - a * mI
    return caixa(a, r) * guia + caixa(b, r)


def aplicar(x, ganho):
    """x: (B,3,H,W) sRGB em 0..1; ganho: (B,1,16,16). Devolve a imagem com a luz corrigida e o mapa ampliado."""
    Gm = ampliar(ganho, luma(x)).clamp(-GMAX, GMAX)
    return (x * torch.exp(Gm)).clamp(0, 1), Gm


def borrar(x, sigma):
    k = int(sigma * 3) * 2 + 1
    t = torch.arange(k, dtype=torch.float32) - k // 2
    w = torch.exp(-t * t / (2 * sigma * sigma))
    w = (w / w.sum()).to(x.device)
    x = F.conv2d(F.pad(x, (k // 2, k // 2, 0, 0), mode="reflect"), w.view(1, 1, 1, k))
    return F.conv2d(F.pad(x, (0, 0, k // 2, k // 2), mode="reflect"), w.view(1, 1, k, 1))


def degrau(e0, e1, v):
    t = ((v - e0) / (e1 - e0)).clamp(0, 1)
    return t * t * (3 - 2 * t)


def estragar_luz(x, g, forca=1.0, identidade=0.15):
    """Defeitos de luz por região, do jeito que aparecem em foto de celular.
    x: (B,3,H,W) em 0..1; g: torch.Generator. Devolve a foto estragada (8 bits) e o campo aplicado, em EV."""
    B, _, H, W = x.shape

    def u():
        return torch.rand(B, 1, 1, 1, generator=g)

    def n(sig):
        return torch.randn(B, 1, 1, 1, generator=g) * sig

    def on(p):
        return (u() < p).float()

    sev = (u() ** 0.7) * (u() >= identidade).float() * forca
    Y = borrar(luma(x), 2.5)
    yy, xx = torch.meshgrid(torch.linspace(-1, 1, H), torch.linspace(-1, 1, W), indexing="ij")
    yy, xx = yy[None, None], xx[None, None]
    campo = torch.zeros(B, 1, H, W)
    # sombra funda: o que já era escuro (rosto contra a luz, canto do cômodo) fica mais escuro
    campo = campo - (0.4 + 1.6 * u()) * on(0.6) * (1 - degrau(0.12 + 0.2 * u(), 0.5 + 0.2 * u(), Y))
    # claro estourado: céu e janela passam do ponto
    campo = campo + (0.3 + 0.9 * u()) * on(0.4) * degrau(0.45 + 0.15 * u(), 0.8 + 0.15 * u(), Y)
    # manchas largas de luz e sombra
    ruido = torch.randn(B, 1, 4, 4, generator=g)
    campo = campo + F.interpolate(ruido, size=(H, W), mode="bicubic", align_corners=False) * 0.55 * u() * on(0.55)
    # degradê (janela de um lado, flash que não alcança o fundo)
    ang = u() * 2 * math.pi
    campo = campo + (xx * torch.cos(ang) + yy * torch.sin(ang)) * n(0.6) * on(0.45)
    # vinheta
    campo = campo - (xx * xx + yy * yy) * (0.2 + 0.7 * u()) * on(0.3)
    campo = campo * sev
    campo = campo - campo.mean((2, 3), keepdim=True)          # a luz geral é assunto da outra rede
    y = l2s((s2l(x) * torch.pow(2.0, campo)).clamp(0, 1))
    y = y + torch.randn(x.shape, generator=g) * 0.006 * u()
    return (y.clamp(0, 1) * 255).round() / 255, campo
