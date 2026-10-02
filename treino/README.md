# Treino das redes do Revela

Aqui fica o código que treina as redes neurais próprias do app. O treino roda num PC comum, sem placa de vídeo.

## RevelaNet-Tom (luz e cor) — já está no app

A rede olha a foto reduzida a 128×128 e o histograma e devolve uma correção para a foto inteira: uma matriz de cor 3×3, uma curva por canal (17 pontos, sempre crescente) e saturação/vibração. São 62 números. O app aplica esses números em qualquer tamanho de foto, então a correção nunca cria halo nem borda falsa.

Ela aprende por "estragar e recuperar": pegamos fotos bem tratadas, estragamos como foto de celular costuma sair (escura, lavada, amarelada, sem cor, com névoa) e treinamos a rede para devolver a original.

O ponto que fez diferença: nem toda foto serve de alvo. Das 11.994 fotos baixadas só 3.481 entram, as que têm preto firme, branco presente, contraste e cor saudáveis (função `curadoria` em `revela_tom.py`). Com todas as fotos como alvo a rede quase não aprendia, porque metade delas é fosca ou lavada de propósito. É essa escolha que define o "jeito" que a rede dá às fotos.

Resultado da versão 0 (4.500 passos, 47 minutos num Core i5-10400):

| medida em 300 fotos que a rede nunca viu | sem a rede | com a rede |
| --- | --- | --- |
| erro médio (escala de 0 a 255) | 15,0 | 8,8 |
| erro mediano | 13,1 | 7,7 |
| PSNR mediano | 24,3 dB | 28,8 dB |

A rede melhora 78% das fotos estragadas. Numa foto que já está boa ela mexe 1,8 de 255, ou seja, quase nada.

Limites conhecidos da versão 0:

- Dominante de cor: numa foto com tinta amarela ou azul ela desfaz menos de 30% da tinta, e em alguns casos até reforça (medido com `medir_cor.py`). Só com este treino a rede não distingue pôr do sol de luz errada.
- A correção é global. Rosto escuro contra fundo claro fica por conta de uma regra do app (ver a seção da RevelaNet-Luz, abaixo).

Arquivos: `modelos/revela_tom.pt` (pesos), `modelos/treino_tom.json` (curva de treino). O app usa `vendor/models/revela_tom.bin`, gerado por `exportar_tom.py`, e refaz a conta em JavaScript puro (função `tomForward` no `index.html`). O teste `testes/tomtest.js` confere que o JavaScript chega aos mesmos números do PyTorch.

## RevelaNet-Detalhe (limpeza e nitidez) — ainda fora do app

Rede pequena (44 mil números) que recebe a foto no tamanho real e devolve a mesma foto com menos ruído e menos blocos de JPEG. Na validação o ganho foi de 27,8 para 28,8 dB e ela melhora 85% dos recortes. Em foto de verdade a diferença só aparece com muito zoom, então ainda não vale o tempo de espera no celular. Fica aqui para a próxima rodada, que precisa de placa de vídeo e mais passos.

Duas lições que custaram tempo e estão anotadas no código: com ReLU a rede travava em "não mexer em nada" (trocado por LeakyReLU), e a média de PSNR por recorte enganava, porque os recortes que entram limpos valem 80 dB sem a rede.

## RevelaNet-Luz (luz por região) — experimento que não entrou no app

A ideia era uma segunda rede para o que a primeira não faz: tratar partes da foto de jeitos diferentes. Ela olha a foto 128×128 já corrigida e devolve um mapa de 16×16 ganhos de luz, que é ampliado acompanhando os contornos da foto (filtro guiado) e multiplica a imagem. São 45 mil números. O treino foi o mesmo "estragar e recuperar", agora com defeitos de luz por região: sombra funda, claro estourado, degradê, vinheta e manchas (`estragar_luz` em `revela_luz.py`).

Não funcionou, e o motivo vale o registro:

| medida em 300 fotos que a rede nunca viu | sem a rede | com a rede (passo 1.600) |
| --- | --- | --- |
| erro médio (0 a 255) | 8,4 | 6,1 |
| erro de luz em blocos de 16 px | 7,8 | 5,4 |

O treino estacionou aí desde o passo 800, e foi interrompido no 1.600. Pior: em foto de verdade a rede praticamente não mexe. Em seis fotos de teste, incluindo contraluz, o maior ganho pedido foi 0,04 (menos de 0,15 EV).

A razão é de fundo. "Estragar e recuperar" só ensina a rede a desfazer o que ela consegue reconhecer como defeito. Uma foto escura por inteiro é reconhecível. Uma sombra funda numa parte da foto não é: fotos bem tratadas também têm sombra funda, silhueta e céu claro, então para a rede uma contraluz é uma foto válida. Para aprender que "rosto escuro contra fundo claro" é defeito ela precisaria saber onde está o rosto, e isso o app já sabe por outro caminho.

O que entrou no app no lugar foi uma regra que usa a separação de pessoas que o app já faz: quando até a parte mais clara da pele do rosto está escura (menos de 58% de luz depois da correção global) e o fundo é claro e bem mais claro que a pessoa, a luz sobe só nas pessoas, na medida do que falta. O detalhe que importa é a referência ser a parte mais clara do rosto, e não a média: em pele escura bem iluminada os brilhos do rosto passam de 60% de luz, então a regra não clareia pele escura por engano. Medido em 20 fotos com gente: dispara só na contraluz.

O código fica aqui para quem quiser retomar: `revela_luz.py`, `treinar_luz.py`, `exportar_luz.py` e `avaliar_luz.py`, com os pesos do passo 1.600 em `modelos/revela_luz_v0_parcial.pt` e a curva em `modelos/treino_luz.json`. A conta da rede em JavaScript também foi escrita e conferida contra o PyTorch (diferença de 2e-7 no mapa), mas saiu do app junto com a rede.

## Como refazer

```bash
python -m venv venv
venv/Scripts/pip install torch --index-url https://download.pytorch.org/whl/cpu
venv/Scripts/pip install pillow numpy onnx onnxruntime
```

1. Baixe `photos.tsv` do [Unsplash Lite Dataset](https://github.com/unsplash/datasets) para uma pasta de dados.
2. `python baixar_fotos.py <dados> 12000 384` baixa as fotos reduzidas (uns 430 MB).
3. `python preparar_dados.py <dados>` monta os arquivos de treino.
4. `python estatisticas.py <dados>` mede luz, contraste e cor de cada foto.
5. `python treinar_tom.py <dados> <saida> 4500 96` treina.
6. `python exportar_tom.py <saida> ../vendor/models/revela_tom.bin` gera o arquivo do app.
7. `python avaliar_fotos.py <saida> <pranchas> <suas fotos>` monta pranchas de antes e depois.

## Licença dos dados

As fotos de treino vêm do Unsplash Lite Dataset. Os termos permitem treinar modelos, inclusive para uso comercial, e proíbem republicar as fotos. Por isso as fotos não estão neste repositório: só o código e os pesos da rede.
