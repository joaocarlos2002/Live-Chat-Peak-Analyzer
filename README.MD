# Projeto: Live Chat Peak Analyzer

## Objetivo

Desenvolva uma aplicação web local que permita informar a URL de uma live, baixar e armazenar os dados necessários em uma pasta `.data`, analisar as mensagens do chat ao longo do tempo e identificar os momentos de maior atividade.

A aplicação deve ser modular, eficiente, persistente e preparada para futuras expansões com inteligência artificial.

## 1. Funcionalidades principais

### 1.1. Cadastro e processamento de lives

- Criar uma interface web para adicionar uma live por meio de sua URL.
- Identificar automaticamente a plataforma e o canal de origem quando possível.
- Validar a URL antes de iniciar o processamento.
- Baixar a live ou obter o arquivo de vídeo quando houver suporte técnico e autorização para isso.
- Coletar as mensagens do chat, incluindo timestamps, conteúdo e identificação do canal.
- Exibir o progresso do processamento em tempo real.
- Permitir cancelar uma tarefa em andamento.
- Evitar o processamento duplicado de uma mesma live.
- Informar claramente quando o vídeo ou o replay do chat não estiver disponível.
- Não presumir que toda plataforma permite baixar vídeos ou recuperar o histórico completo do chat.

### 1.2. Armazenamento local

Todos os arquivos gerados devem ficar dentro de uma pasta `.data` na raiz do projeto.

Estruture o armazenamento de forma organizada, separando vídeos, dados brutos, dados processados, metadados e relatórios.

Exemplo de estrutura:

```text
.data/
├── videos/
│   └── <platform>/
│       └── <channel>/
│           └── <live_id>.mp4
├── raw/
│   └── chats/
│       └── <live_id>.jsonl
├── processed/
│   └── chats/
│       └── <live_id>.parquet
├── metadata/
│   └── <live_id>.json
└── reports/
    └── <live_id>/
        ├── peaks.json
        └── timeline.json
```

Requisitos de armazenamento:

- Criar diretórios automaticamente quando necessário.
- Utilizar identificadores estáveis para lives e canais.
- Preservar os dados brutos para permitir reprocessamento.
- Não baixar novamente arquivos já existentes e válidos.
- Validar integridade, tamanho e conclusão dos downloads.
- Suportar retomada de operações interrompidas quando tecnicamente possível.
- Não armazenar credenciais, cookies ou tokens em arquivos públicos.
- Implementar limites de armazenamento e tratamento de falta de espaço em disco.
- Garantir que arquivos temporários não sejam confundidos com downloads concluídos.

A pasta `.data` deve estar no `.gitignore`.

### 1.3. Análise de mensagens do chat

O sistema deve analisar a atividade do chat ao longo de toda a live.

Calcular, no mínimo:

- Total de mensagens.
- Total de usuários únicos, quando houver identificadores disponíveis.
- Mensagens por segundo e por minuto.
- Média e mediana de mensagens por intervalo.
- Maior pico de mensagens por intervalo.
- Horário e timestamp do maior pico.
- Top 10 ou mais períodos de maior atividade.
- Evolução da atividade durante a transmissão.
- Intervalos com atividade acima da média.
- Comparação entre diferentes lives do mesmo canal.

Implementar janelas de análise configuráveis, como 1, 5, 10, 30 e 60 segundos, além de 1 e 5 minutos.

A aplicação deve permitir alternar entre essas janelas sem precisar baixar novamente os dados.

### 1.4. Detecção de picos

Criar um algoritmo que identifique automaticamente os períodos de maior atividade.

Para cada pico, apresentar:

- Timestamp inicial e final.
- Minutagem correspondente no vídeo, quando houver sincronização confiável.
- Quantidade de mensagens.
- Mensagens por segundo ou minuto, conforme a janela.
- Número de usuários únicos, quando disponível.
- Intensidade relativa à atividade normal do chat.
- Posição no ranking de picos.
- Mensagens representativas do período, com links ou timestamps quando disponíveis.

Não confundir o maior volume absoluto com uma anomalia estatística. Implementar métricas distintas para picos absolutos e picos relativos à linha de base.

Agrupar picos muito próximos para evitar que um único evento gere dezenas de resultados redundantes.

### 1.5. Separação por canal

A aplicação deve separar os resultados por canal, sem misturar os dados de canais diferentes.

Cada canal deve ter uma página ou seção própria contendo:

- Nome e identificador do canal.
- Lives processadas.
- Quantidade total de mensagens analisadas.
- Histórico de picos.
- Ranking dos momentos mais movimentados.
- Gráficos de atividade.
- Comparação entre transmissões.
- Filtros por data, duração e plataforma.

Se uma live tiver mais de uma fonte de chat, identificar cada fonte separadamente e permitir visualizar tanto os dados individuais quanto os agregados, quando isso fizer sentido.

### 1.6. Sincronização com o vídeo

A minutagem precisa representar o instante correto da live, e não apenas o horário em que uma mensagem foi recebida.

- Preservar os timestamps originais das mensagens.
- Normalizar os timestamps para uma linha temporal consistente.
- Calcular o tempo relativo ao início da transmissão quando os dados permitirem.
- Tratar pausas, atrasos, transmissões reiniciadas e diferenças de fuso horário.
- Informar quando a sincronização for estimada ou incerta.
- Permitir clicar em um pico e abrir o vídeo no instante correspondente, caso o player ou o arquivo permita.
- Não inventar timestamps ausentes.

Exemplo de resultado:

```text
Canal: exemplo
Live: transmissão analisada
Pico #1: 01:24:35 – 01:24:45
Mensagens: 1.284
Taxa: 128,4 mensagens/s
```

Os números acima são ilustrativos. Os valores reais devem ser calculados a partir dos dados coletados.

## 2. Aplicação web

Crie uma interface moderna, responsiva e funcional, com tema escuro como opção padrão.

### Páginas

**Dashboard**
- Total de lives processadas.
- Total de mensagens analisadas.
- Canais cadastrados.
- Últimas tarefas executadas.
- Maiores picos encontrados.

**Adicionar live**
- Campo para URL.
- Seleção automática ou manual da plataforma.
- Configurações de coleta e análise.
- Botão para iniciar processamento.
- Barra de progresso e logs resumidos.

**Detalhes da live**
- Informações da transmissão.
- Player de vídeo, quando disponível.
- Gráfico de mensagens ao longo do tempo.
- Lista ordenada de picos.
- Tabela de mensagens por intervalo.
- Filtros de período.
- Exportação dos resultados.

**Canais**
- Lista de canais conhecidos.
- Histórico de transmissões.
- Estatísticas agregadas.
- Comparação de picos entre lives.

**Configurações**
- Diretório de armazenamento.
- Limites de downloads simultâneos.
- Tamanho das janelas de análise.
- Política de retenção de arquivos.
- Configurações de processamento.

### Interações

- Clicar em um ponto do gráfico deve exibir os dados daquele intervalo.
- Clicar em um pico deve abrir os detalhes correspondentes.
- Permitir ordenar tabelas por volume, horário e intensidade.
- Permitir pesquisar por canal ou transmissão.
- Exibir erros de forma compreensível.
- Atualizar o status de tarefas sem exigir recarregamento manual da página.

## 3. Arquitetura técnica

Antes de implementar, examine o ambiente e os arquivos existentes. Se já houver um projeto, preserve suas convenções e evite reescrever componentes sem necessidade.

Caso o projeto esteja vazio, proponha e documente uma arquitetura adequada para execução local.

Separar a aplicação em módulos independentes:

- Interface web.
- API backend.
- Adaptadores de plataformas.
- Gerenciador de downloads.
- Coletor de mensagens.
- Normalizador de timestamps.
- Motor de análise.
- Detector de picos.
- Camada de persistência.
- Gerenciador de tarefas.
- Exportador de relatórios.

O processamento de arquivos grandes deve ocorrer fora do ciclo de requisição HTTP. Utilizar tarefas assíncronas ou processos em segundo plano, com controle de concorrência, cancelamento e recuperação de falhas.

Não bloquear a interface durante downloads ou análises.

### Persistência

Manter os arquivos brutos e processados na pasta `.data`.

Utilizar inicialmente metadados e índices em arquivos locais, se isso for suficiente para a escala esperada. Se o projeto já possuir banco de dados, utilizar a infraestrutura existente. Não introduzir PostgreSQL ou Redis sem uma justificativa técnica concreta.

Evitar carregar vídeos inteiros ou históricos completos de chat na memória quando for possível processá-los em fluxo.

### Plataformas

Criar uma interface comum para adaptadores de plataformas, permitindo adicionar suporte a novas fontes sem modificar o motor de análise.

Cada adaptador deve declarar:

- Plataformas suportadas.
- Disponibilidade de download do vídeo.
- Disponibilidade de replay do chat.
- Limitações conhecidas.
- Necessidade de autenticação.
- Formato e precisão dos timestamps.
- Restrições de uso e limites de requisições.

Implementar primeiro uma plataforma que ofereça acesso viável aos dados necessários. Não simular suporte a funcionalidades indisponíveis.

## 4. API

Projetar endpoints REST para:

- Cadastrar uma live.
- Listar lives.
- Consultar detalhes de uma live.
- Iniciar e cancelar processamento.
- Consultar o status de uma tarefa.
- Listar canais.
- Consultar estatísticas por canal.
- Consultar picos de uma live.
- Consultar séries temporais.
- Exportar relatórios.

Documentar os contratos, códigos de erro e formatos de resposta.

Para atualizações de progresso, utilizar SSE ou WebSocket se houver benefício real para a experiência da interface.

## 5. Desempenho e confiabilidade

- Suportar transmissões longas e históricos grandes.
- Utilizar processamento incremental sempre que possível.
- Evitar recalcular métricas quando os dados e parâmetros não mudaram.
- Implementar logs estruturados.
- Tratar timeouts, falhas de rede, limites de requisições e arquivos corrompidos.
- Separar erros recuperáveis de erros fatais.
- Implementar testes para os casos críticos.
- Não considerar uma tarefa concluída até que os arquivos e os metadados necessários tenham sido validados.
- Evitar concorrência que provoque corrupção dos arquivos.
- Não expor caminhos arbitrários do sistema de arquivos pela API.



## 8. Entregáveis

Ao concluir, fornecer:

1. Aplicação web funcional.
2. Backend com módulos separados.
3. Frontend integrado à API.
4. Estrutura automática de armazenamento em `.data`.
5. Analisador de chat e detector de picos.
6. Separação por canal.
7. Testes automatizados.
8. Arquivo `.env.example`, se necessário, sem segredos.
9. `.gitignore` configurado.
10. Documentação de instalação e execução.
11. Documentação das plataformas suportadas e suas limitações.

## 9. Critérios de aceitação

O projeto será considerado funcional quando:

- Eu puder inserir uma URL válida pela interface web.
- A aplicação identificar os recursos disponíveis para aquela transmissão.
- O vídeo e os dados do chat forem coletados quando a plataforma permitir.
- Os arquivos forem organizados automaticamente em `.data`.
- O sistema calcular os intervalos com maior volume de mensagens.
- Os resultados mostrarem a minutagem correta quando houver dados suficientes para sincronização.
- Os canais permanecerem separados.
- Eu puder consultar os picos no dashboard e nos detalhes da live.
- Os resultados puderem ser exportados.
- O sistema tratar falhas sem corromper os dados existentes.

## Como executar esta implementação

Requisitos: Python 3.10 ou superior. O `yt-dlp` é usado para obter metadados e
baixar gravações. Para o YouTube, o Node.js é usado como runtime JavaScript
durante a extração. O FFmpeg é recomendado para juntar vídeo e áudio e gerar
arquivos MP4.

Na raiz do projeto, execute:

```powershell
python -m pip install -r requirements.txt
python app.py
```

Verifique se os comandos abaixo estão disponíveis no Windows:

```powershell
node --version
ffmpeg -version
```

Sem FFmpeg, o aplicativo ainda tenta baixar um formato único compatível, mas pode
salvar o vídeo como WebM em vez de MP4.

Para apagar todos os vídeos, chats, metadados e relatórios gerados anteriormente
antes de iniciar o servidor, use a flag:

```powershell
python app.py --clear-data
```

Também é possível usar o botão **Apagar tudo** na interface. A ação exige
confirmação e remove somente o conteúdo gerado dentro de `.data`.

Abra `http://127.0.0.1:8000` no navegador. A aplicação cria automaticamente a
estrutura `.data` e mantém os metadados fora do controle de versão. Nesta primeira
versão, a detecção de Twitch, YouTube e Kick está disponível. Para baixar uma
gravação, instale o executável `yt-dlp` e deixe-o disponível no `PATH` do Windows.
O aplicativo tenta salvar o vídeo em `.data/videos/<plataforma>/<canal>/`.
O vídeo não contém o histórico do chat. Para analisar mensagens, um arquivo
`*.jsonl` precisa ser disponibilizado em `.data/raw/chats/<live_id>.jsonl`.

Instalação opcional do downloader:

```powershell
pip install yt-dlp
```

A API calcula os picos com a janela solicitada:

```text
GET /api/lives/<live_id>?window=10
GET /api/lives/<live_id>/export
GET /api/channels
```
