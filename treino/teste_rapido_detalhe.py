"""Confere em segundos o treino da RevelaNet-Detalhe: estrago, velocidade e exportação."""
import os, sys, time
import numpy as np
import torch
from PIL import Image
from revela_detalhe import RevelaDetalhe, estragar_detalhe

DADOS = sys.argv[1]
torch.set_num_threads(6)
d = torch.from_numpy(np.load(os.path.join(DADOS, "det96.npy"), mmap_mode="r")[:48].copy())
x = d.permute(0, 3, 1, 2).float() / 255
g = torch.Generator().manual_seed(1)
t0 = time.time(); y = estragar_detalhe(x, g); t1 = time.time() - t0
mse = ((y - x) ** 2).flatten(1).mean(1)
print(f"estrago de 48 recortes em {t1 * 1000:.0f} ms | PSNR medio {(10 * torch.log10(1 / mse.clamp(min=1e-8))).mean():.1f} dB | intactos {int((mse < 1e-7).sum())}")
rede = RevelaDetalhe()
print("identidade no inicio:", (rede(x[:4]) - x[:4]).abs().max().item(), "| parametros", sum(p.numel() for p in rede.parameters()))
opt = torch.optim.AdamW(rede.parameters(), lr=1e-3)
t0 = time.time()
for it in range(5):
    ent = estragar_detalhe(x[:24], g)
    L = (rede(ent[:, :, :64, :64]) - x[:24, :, :64, :64]).abs().mean()
    opt.zero_grad(); L.backward(); opt.step()
    print(f"  passo {it} perda {L.item() * 255:.2f} | {time.time() - t0:.2f} s")
# prancha: limpo em cima, estragado embaixo
a = torch.cat([torch.cat(list(x[:8]), 2), torch.cat(list(y[:8]), 2)], 1)
Image.fromarray((a.permute(1, 2, 0).numpy() * 255).round().astype(np.uint8)).resize((8 * 96 * 2, 96 * 4), Image.NEAREST).save(os.path.join(DADOS, "estrago_detalhe.png"))
rede.eval()
p = os.path.join(DADOS, "teste_detalhe.onnx")
torch.onnx.export(rede, (torch.rand(1, 3, 128, 128),), p, input_names=["x"], output_names=["y"], opset_version=17, dynamo=False, dynamic_axes={"x": {2: "h", 3: "w"}, "y": {2: "h", 3: "w"}})
import onnxruntime as ort
s = ort.InferenceSession(p, providers=["CPUExecutionProvider"])
e = np.random.rand(1, 3, 256, 320).astype(np.float32)
t0 = time.time(); o = s.run(None, {"x": e})[0]; t2 = time.time() - t0
with torch.no_grad():
    b = rede(torch.from_numpy(e)).numpy()
print("onnx", o.shape, "| diferenca max", float(np.abs(o - b).max()), "| arquivo", os.path.getsize(p) // 1024, "KB |", f"{t2 * 1000:.0f} ms para 256x320 ->", f"{t2 / (256 * 320) * 2e6:.2f} s por 2 megapixels")
