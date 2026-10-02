# Revela

Editor de fotos que roda no navegador e no celular. Você abre uma foto e a rede neural do próprio app corrige luz e cor na hora. Depois dá para escolher um look de cinema ou refinar com ferramentas parecidas com as do Snapseed.

Tudo é processado no seu aparelho. Nenhuma foto sai dele.

## Como usar no celular

1. Abra o endereço do app no Chrome (Android) ou no Safari (iPhone).
2. Use o menu do navegador e escolha "Adicionar à tela inicial" (ou "Instalar app").
3. Na primeira abertura o app baixa os modelos. Depois disso funciona sem internet.

No Android também dá para instalar o APK da página de versões.

## O que tem

- **IA Revela**: rede neural treinada por nós que corrige luz, contraste e cor da foto inteira em menos de um décimo de segundo. É o motor padrão do Automático; o motor antigo, por regras, continua disponível como "Clássico".
- 11 looks de cinema por cima da foto já corrigida, a um toque.
- Pele, olhos, dentes, cabelo e barba tratados por região, bem dosados.
- Fundo de cinema: desfoque do fundo com profundidade medida por IA, quando você pede.
- Ajustar imagem, detalhes, curvas, balanço de branco, vinheta, preto e branco, desfoque de lente, granulação e 10 filtros.
- Cortar, girar e endireitar automático. Formatos prontos para Feed, Story e Reels.
- Seletivo e pincel, com escolha de região (pele, cabelo, roupa, céu, fundo).
- Zoom com pinça, toque duplo e arrastar.
- Melhor rosto entre várias fotos (em teste).

## A IA própria

O código de treino, os pesos e os números de avaliação estão em [`treino/`](treino/README.md). A rede tem 310 mil parâmetros, pesa 1,2 MB e a conta é feita em JavaScript puro dentro do `index.html`, sem biblioteca de IA.

## Testes

A pasta [`testes/`](testes/README.md) tem a suíte que abre o app num navegador automatizado e confere abertura de arquivos, looks, ferramentas, zoom por toque, salvamento, funcionamento sem internet e a IA Revela.

## Créditos

A separação de pessoas e a leitura de rostos usam o [MediaPipe](https://ai.google.dev/edge/mediapipe) do Google, sob licença Apache 2.0. Os arquivos ficam na pasta `vendor/`.

Outros modelos que rodam no aparelho: Real-ESRGAN (BSD-3), RestoreFormer++ (Apache 2.0), Depth Anything V2 Small (Apache 2.0) e SegFormer B1 ADE20K (licença NVIDIA, só uso não comercial; trocar antes de uso comercial), via ONNX Runtime Web (MIT).

A IA Revela foi treinada com fotos do Unsplash Lite Dataset, cujos termos permitem treinar modelos. As fotos não fazem parte deste repositório.

Este é um protótipo em desenvolvimento.
