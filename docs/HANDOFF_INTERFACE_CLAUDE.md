# Handoff para construção da interface no Claude

## Missão

Construir somente a camada visual do Resumo Rápido Jurídico sobre o servidor Python local existente. Não alterar o motor jurídico, não adicionar nuvem, login, telemetria, serviços externos, Ollama ou upload remoto.

## Direção sugerida

Usar a **Opção A — Assistente em três etapas**, descrita em `OPCOES_DE_INTERFACE.md`. A interface deve ser calma, acessível, responsiva e claramente jurídica sem imitar portais oficiais.

## Fluxo principal

1. **Escolher arquivo:** aceitar `.pdf`, `.md` e `.markdown`; mostrar nome, tamanho e opção de trocar antes de enviar.
2. **Escolher modo:**
   - Resumo Rápido: identificação, fatos essenciais, partes, pedidos, decisões e pendências.
   - Relatório Jurídico Completo: acrescenta linha do tempo, provas, controvérsias, recursos, valores, dispositivos legais e pontos para revisão; pode demorar mais.
3. **Processar:** mostrar etapa, percentual, tempo transcorrido e mensagens simples.
4. **Revisar:** renderizar o relatório, destacar o aviso de conferência humana e oferecer MD, DOCX e PDF.

## Rotas internas do servidor Python

### `GET /`

Entrega a interface.

### `GET /saude`

Uso: confirmar que o servidor está ativo. Na versão pública, retornar apenas `ok`, `motor` e `versao`; não expor caminho absoluto.

### `POST /trabalhos`

`multipart/form-data`:

- `arquivo`: PDF ou Markdown.
- `modo`: `rapido` ou `completo`.

Resposta inicial: objeto de trabalho com `id`, `estado`, `etapa`, `progresso`, `detalhe`, indicadores de conclusão e modo.

### `GET /trabalhos/{id}`

Consultar a cada 500–1000 ms enquanto `estado` for `processando`. Parar em `concluido` ou `erro`.

Quando concluído, a resposta pode conter `analise_html`, `download_md`, `download_docx`, `download_pdf`, `estatisticas`, `metodo` e `segundos`.

### `GET /downloads/{nome}`

Baixa um relatório gerado. Os links vêm prontos na resposta do trabalho.

### `GET /arquivos` e `POST /resumir-existente`

São recursos da versão pessoal. Na distribuição pública, deixar desativados por padrão ou mostrar apenas arquivos da própria instalação, sempre por identificador opaco — nunca por caminho absoluto.

## Estados obrigatórios

- Inicial, sem arquivo.
- Arquivo selecionado e ainda não enviado.
- Enviando.
- Extraindo texto rápido.
- Executando OCR, com aviso de maior demora.
- Gerando análise em Python.
- Criando formatos.
- Concluído, com prévia e downloads.
- Erro recuperável, com mensagem e botão “Tentar novamente”.
- Servidor indisponível, orientando abrir o inicializador local.
- Arquivo inválido ou maior que o limite.

## Textos essenciais

- Título: “Resumo Rápido Jurídico”.
- Privacidade: “Seu documento é processado neste computador e não é enviado para serviços externos.”
- Revisão: “Este relatório é auxiliar. Confira nomes, datas, valores e conclusões diretamente nos autos.”
- Botão inicial: “Escolher documento”.
- Botão de ação: “Converter e analisar”.
- Processamento: “Organizando as informações…”.
- Downloads: “Baixar Word”, “Baixar PDF” e “Baixar Markdown”.
- Evitar “IA” nos botões porque o motor atual é determinístico em Python.

## LGPD e termos

Criar telas ou diálogos locais para:

- Política de privacidade: processamento local, ausência de envio externo e responsabilidade do usuário pela guarda dos arquivos.
- Termos de uso: ferramenta auxiliar, sem aconselhamento jurídico, sem garantia de exatidão e necessidade de conferência humana.
- Retenção: explicar onde os arquivos são salvos e permitir que o usuário gerencie a pasta; não apagar automaticamente.
- Segurança: recomendar computador protegido e cautela com documentos sigilosos.

Não afirmar “conformidade total com a LGPD”. Usar linguagem factual sobre o funcionamento e submeter o texto jurídico final à revisão profissional.

## Erros e recuperação

- Traduzir erros técnicos para português simples.
- Nunca exibir stack trace, caminho absoluto, certificado, chave ou variável de ambiente.
- Preservar o arquivo original quando a análise falhar.
- Se OCR não estiver instalado, explicar a dependência e oferecer análise de Markdown já extraído.
- Se o servidor reiniciar e perder o trabalho em memória, pedir reenvio sem afirmar que o documento foi apagado.

## Acessibilidade e responsividade

- Contraste AA, foco visível e navegação completa por teclado.
- `aria-live` para progresso e erros.
- Não depender apenas de cor para sucesso ou falha.
- Área clicável mínima de 44 px.
- Layout funcional entre 360 px e telas largas.
- Respeitar `prefers-reduced-motion`.

## Critérios de aceite

- O fluxo rápido e o completo terminam e mostram a prévia.
- Os três downloads funcionam.
- OCR e erros exibem mensagens compreensíveis.
- Nenhum caminho pessoal aparece na tela ou no HTML.
- Nenhuma chamada de rede ocorre além de `localhost`.
- O build funciona com o servidor Python sem framework obrigatório; preferir HTML/CSS/JS simples para instalação leve.
