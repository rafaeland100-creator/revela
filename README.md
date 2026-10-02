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
- **Meu gosto**: quando você salva uma foto, o app compara os seus ajustes com o que o automático tinha proposto. A partir da segunda foto salva, a média dessas diferenças (mais contraste, mais cor, mais quente...) passa a entrar sozinha nas próximas. Fica só no aparelho, e dá para desligar ou esquecer.
- 11 looks de cinema por cima da foto já corrigida, a um toque.
- **Borracha mágica**: você pinta por cima de um dedo, de alguém ao fundo ou de um objeto e ele some; a IA preenche com o que estaria atrás. Com dois dedos a foto aproxima, para marcar detalhe pequeno, e o botão "Ver antes" compara com a foto original.
- **Fundo**: deixa a cor só na pessoa (o cenário vira preto e branco), troca o cenário por um fundo de estúdio (escuro, claro ou colorido) ou por uma foto sua, com desfoque de lente de retrato. A separação da pessoa é feita pela IA; a borda é refinada no tamanho da foto e a parte do cenário antigo que estava misturada nos fios de cabelo é trocada pela do fundo novo.
- **Copiar o look de uma foto**: você escolhe uma foto de referência e o app leva a sua para a mesma luz, contraste e cor. O look fica guardado para as próximas fotos.
- Foto amarelada de ambiente interno: quando tem gente, a cor da pele serve de referência para tirar o amarelado.
- Rosto escuro contra a luz: quando até a parte mais clara do rosto está escura e o fundo é claro, o automático levanta a luz só nas pessoas. Pele escura bem iluminada, low-key e silhueta de pôr do sol ficam como estão.
- Pele, olhos, dentes, cabelo e barba tratados por região, bem dosados.
- Fundo de cinema: desfoque do fundo com profundidade medida por IA, quando você pede.
- Ajustar imagem, detalhes, curvas, balanço de branco, vinheta, preto e branco, desfoque de lente, granulação e 10 filtros.
- Cortar, girar e endireitar automático. Formatos prontos para Feed, Story e Reels.
- Seletivo e pincel, com escolha de região (pele, cabelo, roupa, céu, fundo).
- Zoom com pinça, toque duplo e arrastar. Na borracha e no pincel um dedo pinta e dois dedos aproximam.
- Melhor rosto entre várias fotos (em teste).

## A IA própria

O código de treino, os pesos e os números de avaliação estão em [`treino/`](treino/README.md). A rede tem 310 mil parâmetros, pesa 1,2 MB e a conta é feita em JavaScript puro dentro do `index.html`, sem biblioteca de IA.

## Testes

A pasta [`testes/`](testes/README.md) tem a suíte que abre o app num navegador automatizado e confere abertura de arquivos, looks, ferramentas, zoom por toque, salvamento, funcionamento sem internet e a IA Revela.

## Créditos

A separação de pessoas e a leitura de rostos usam o [MediaPipe](https://ai.google.dev/edge/mediapipe) do Google, sob licença Apache 2.0. Os arquivos ficam na pasta `vendor/`.

Outros modelos que rodam no aparelho: MI-GAN (borracha mágica; Picsart AI Research, MIT), Real-ESRGAN (BSD-3), RestoreFormer++ (Apache 2.0), Depth Anything V2 Small (Apache 2.0) e SegFormer B1 ADE20K (licença NVIDIA, só uso não comercial; trocar antes de uso comercial), via ONNX Runtime Web (MIT).

A IA Revela foi treinada com fotos do Unsplash Lite Dataset, cujos termos permitem treinar modelos. As fotos não fazem parte deste repositório.

Este é um protótipo em desenvolvimento.
