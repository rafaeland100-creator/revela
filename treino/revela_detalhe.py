"""RevelaNet-Detalhe: a rede própria do Revela para limpar e dar nitidez, sem aumentar a foto.

Entra a foto como está (sRGB 0..1), sai a foto do mesmo tamanho com menos ruído, menos blocos de JPEG
e bordas mais firmes. A rede é pequena de propósito (cerca de 44 mil números) para rodar em celular:
ela trabalha na metade da resolução (PixelUnshuffle) e devolve só a diferença em relação à entrada.

Aprende por "estragar e recuperar": recortes nítidos são borrados, ganham ruído e compressão JPEG,
e a rede aprende a devolver o recorte original.
"""
import io
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image


class RevelaDetalhe(nn.Module):
    def __init__(self, c=32, n=4):
        super().__init__()
        # LeakyReLU e não ReLU: com ReLU as unidades "morriam" nos primeiros passos e a rede travava sem aprender nada
        camadas = [nn.Conv2d(12, c, 3, padding=1), nn.LeakyReLU(0.1)]
        for _ in range(n):
            camadas += [nn.Conv2d(c, c, 3, padding=1), nn.LeakyReLU(0.1)]
        camadas.append(nn.Conv2d(c, 12, 3, padding=1))
        self.corpo = nn.Sequential(*camadas)
        nn.init.zeros_(self.corpo[-1].weight)
        nn.init.zeros_(self.corpo[-1].bias)

    def forward(self, x):
        return x + F.pixel_shuffle(self.corpo(F.pixel_unshuffle(x, 2)), 2)


def _nucleo(sigma, raio=4):
    k = torch.arange(-raio, raio + 1, dtype=torch.float32)
    g = torch.exp(-k * k / (2 * sigma * sigma))
    return g / g.sum()


def borrar(x, sigma):
    """Desfoque gaussiano com um sigma por imagem. x: (B,3,H,W); sigma: (B,)."""
    B = x.shape[0]
    k = torch.stack([_nucleo(max(0.05, float(s))) for s in sigma])            # (B, 9)
    kh = k.view(B, 1, 1, -1).repeat_interleave(3, 0)
    kv = k.view(B, 1, -1, 1).repeat_interleave(3, 0)
    y = F.pad(x.reshape(1, B * 3, *x.shape[2:]), (4, 4, 4, 4), mode="reflect")
    y = F.conv2d(F.conv2d(y, kh, groups=B * 3), kv, groups=B * 3)
    return y.reshape(x.shape)


def jpeg(x, q):
    """Compressão JPEG de verdade (PIL), uma qualidade por imagem. x: (B,3,H,W) em 0..1."""
    out = torch.empty_like(x)
    a = (x.clamp(0, 1) * 255).round().byte().permute(0, 2, 3, 1).numpy()
    for i in range(a.shape[0]):
        buf = io.BytesIO()
        Image.fromarray(a[i]).save(buf, "JPEG", quality=int(q[i]), subsampling=2 if q[i] < 90 else 0)
        out[i] = torch.from_numpy(np.asarray(Image.open(buf).convert("RGB")).copy()).permute(2, 0, 1).float() / 255
    return out


def estragar_detalhe(x, g, borrao=True):
    """Recortes nítidos -> como saem de um celular: menos resolução, borrão, ruído e JPEG.
    borrao=False deixa só ruído e JPEG (tarefa mais fácil, para a rede pequena)."""
    B, _, H, W = x.shape

    def u(n=B):
        return torch.rand(n, generator=g)

    y = x
    if borrao and u(1).item() < 0.45:                                    # resolução real menor que a do arquivo
        s = 1.15 + 0.85 * u(1).item()
        h2, w2 = max(8, round(H / s)), max(8, round(W / s))
        y = F.interpolate(F.interpolate(y, size=(h2, w2), mode="bicubic", align_corners=False, antialias=True), size=(H, W), mode="bicubic", align_corners=False)
    sigma = torch.where(u() < (0.7 if borrao else 0.0), 0.25 + 1.0 * u(), torch.zeros(B))
    y = torch.where((sigma > 0).view(B, 1, 1, 1), borrar(y, sigma), y)
    forca = torch.where(u() < 0.65, 9.0 * u() ** 1.5, torch.zeros(B)).view(B, 1, 1, 1) / 255
    ruido = torch.randn(x.shape, generator=g)
    croma = torch.randn(B, 3, H, W, generator=g)
    croma = croma - croma.mean(1, keepdim=True)                # ruído de cor (sem mudar a luz)
    mole = (u() < 0.5).float().view(B, 1, 1, 1)                # metade das vezes o ruído vem "amassado", como depois do tratamento da câmera
    r = ruido * 0.8 + croma * 0.9
    r = mole * borrar(r, torch.full((B,), 0.7)) * 1.6 + (1 - mole) * r
    y = (y + r * forca).clamp(0, 1)
    q = torch.where(u() < 0.85, 38 + 57 * u(), torch.full((B,), 100.0))
    y = jpeg(y, q.tolist())
    limpa = (u() < 0.05).view(B, 1, 1, 1)                       # de vez em quando a entrada já é a foto boa
    return torch.where(limpa, x, y)
