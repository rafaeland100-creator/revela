# Revela

Editor de fotos que roda no navegador e no celular. Você abre uma foto e ele escolhe sozinho a luz, a cor, o estilo e os ajustes de rosto. Depois dá para refinar com ferramentas parecidas com as do Snapseed.

Tudo é processado no seu aparelho. Nenhuma foto sai dele.

## Como usar no celular

1. Abra o endereço do app no Chrome (Android) ou no Safari (iPhone).
2. Use o menu do navegador e escolha "Adicionar à tela inicial" (ou "Instalar app").
3. Na primeira abertura o app baixa uns 29 MB de modelos. Depois disso funciona sem internet.

## O que tem

- Edição automática por tipo de cena, com quatro estilos (Natural, Adams, Leibovitz, McCurry).
- Pele, olhos, dentes, cabelo e barba tratados por região.
- Ajustar imagem, detalhes, curvas, balanço de branco, vinheta, preto e branco, desfoque de lente, granulação e 10 filtros.
- Cortar, girar e endireitar automático.
- Seletivo e pincel, com escolha de região (pele, cabelo, roupa, céu, fundo).
- Melhor rosto entre várias fotos (em teste).

## Créditos

A separação de pessoas e a leitura de rostos usam o [MediaPipe](https://ai.google.dev/edge/mediapipe) do Google, sob licença Apache 2.0. Os arquivos ficam na pasta `vendor/`.

Modelos de IA que rodam no aparelho: Real-ESRGAN (BSD-3), RestoreFormer++ (Apache 2.0) e Depth Anything V2 Small (Apache 2.0), SegFormer B1 ADE20K (licença NVIDIA, só uso não comercial; trocar antes de uso comercial), via ONNX Runtime Web (MIT).

Este é um protótipo em desenvolvimento.
