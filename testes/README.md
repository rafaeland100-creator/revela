# Testes do Revela

Scripts que abrem o app num Chromium automatizado (Playwright) e conferem o comportamento. Rodam contra um servidor local:

```bash
python -m http.server 8765
```

## O que cada um faz

- `suite.js <pasta_de_fotos> [endereço] [grupos]`: 99 testes em 10 grupos.
  - G1 abertura de arquivos (PNG com transparência, foto minúscula, 6000×4000, EXIF, arquivo corrompido)
  - G2 looks, automático, ajustes, formatos e salvamento
  - G3 as 26 ferramentas
  - G4 as IAs sob demanda (detalhe, rostos, cancelar)
  - G5 celular 360×760 com toque de verdade (pinça, toque duplo, arrastar, botão Voltar, pintar com a foto ampliada, toque num botão logo depois de um traço rápido, fundo de estúdio)
  - G6 service worker e uso sem internet
  - G7 a IA Revela (foto escura, estourada, amarelada com gente, já boa, força, motor clássico, arquivo salvo)
  - G8 copiar o look de uma foto (aproximação da referência, intensidade, guardar, apagar, proteção do rosto)
  - G9 borracha mágica (pintar, zoom com a roda do mouse, limpar, apagar um objeto sem mexer no resto, salvar, desfazer)
  - G10 fundo (estúdio escuro, claro e azul, luz do fundo, cor só na pessoa, foto do usuário como fundo e o desfoque dela, arquivo salvo, foto sem gente, troca de foto)
- `battery.js <pasta_de_fotos> <saída>`: roda o automático em todas as fotos e monta pranchas de antes e depois. É o teste que mostra se o automático melhora ou estraga.
- `resumo.js <report.json>`: resume tempos e quais retoques entraram em cada foto da bateria.
- `tomtest.js <index.html> <revela_tom.bin> <revela_tom_teste.json>`: confere que a conta da rede em JavaScript dá os mesmos números do PyTorch.
- `looktest.js <index.html>`: confere a conta do "copiar look" com fotos sintéticas (quantis de luz, quantidade de cor, tom por faixa, preto e branco).
- `sintaxe.js <index.html>`: confere a sintaxe do script embutido.

## Fotos de teste

A suíte espera uma pasta com `images/`, `pexels/` e `pexels2/` (fotos pessoais e fotos de banco de imagens). Elas não estão no repositório. Para usar outras fotos, troque os caminhos no começo de `suite.js` e a lista em `battery.js`. O caminho do Chromium (`EXE`) também é o da máquina onde os testes foram escritos.

O teste no Android de verdade fica em `scripts/test-apk.js` e roda no emulador do GitHub Actions.
