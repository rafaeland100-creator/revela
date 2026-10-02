"""Confere em segundos se o treino da RevelaNet-Tom está inteiro: identidade, velocidade e exportação."""
import os, sys, time
import numpy as np
import torch
from revela_tom import RevelaTom, Exportavel, parametros, aplicar, histograma, estragar, NH

DADOS = sys.argv[1]
torch.set_num_threads(6)
d = torch.from_numpy(np.load(os.path.join(DADOS, "tom128.npy"), mmap_mode="r")[:192].copy())
x = d.permute(0, 3, 1, 2).float() / 255
g = torch.Generator().manual_seed(1)
rede = RevelaTom()
raw = rede(x[:8], histograma(x[:8]))
ident = aplicar(x[:8], *parametros(raw))
print("identidade no inicio: erro max", (ident - x[:8]).abs().max().item())
y = estragar(x, g)
print("estragada: erro medio", (y - x).abs().mean().item() * 255, "| intacta em", int(((y - x).abs().flatten(1).max(1)[0] < 0.003).sum()), "de", x.shape[0])
h = histograma(y)
print("histograma", tuple(h.shape), "soma por bloco", h[0, :32].sum().item(), h[0, 128:].sum().item())
opt = torch.optim.AdamW(rede.parameters(), lr=1e-3)
t0 = time.time()
for it in range(6):
    ent = estragar(x[:96], g)
    out = aplicar(ent, *parametros(rede(ent, histograma(ent))))
    L = (out - x[:96]).abs().mean()
    opt.zero_grad(); L.backward(); opt.step()
    print(f"  passo {it} perda {L.item():.4f} | {time.time() - t0:.2f} s")
rede.eval()
caminho = os.path.join(DADOS, "teste_tom.onnx")
torch.onnx.export(Exportavel(rede).eval(), (torch.rand(1, 3, 128, 128), torch.full((1, NH), 1 / 32)), caminho, input_names=["img", "hist"], output_names=["params"], opset_version=17, dynamo=False)
import onnxruntime as ort
s = ort.InferenceSession(caminho, providers=["CPUExecutionProvider"])
a = s.run(None, {"img": y[:1].numpy(), "hist": h[:1].numpy()})[0]
with torch.no_grad():
    b = Exportavel(rede)(y[:1], h[:1]).numpy()
print("onnx", a.shape, "| diferenca max torch x onnx", float(np.abs(a - b).max()), "| arquivo", os.path.getsize(caminho) // 1024, "KB")
print("operadores:", sorted({n.op_type for n in __import__("onnx").load(caminho).graph.node}))
