# Live Chat Peak Analyzer

Aplicação web local para baixar uma gravação de live, coletar o replay do chat e visualizar os momentos de maior atividade em uma timeline.

## Requisitos

- Python 3.10 ou superior
- `yt-dlp`
- FFmpeg
- Node.js (recomendado para downloads do YouTube)

O FFmpeg e o Node.js são opcionais para abrir a aplicação, mas são necessários para obter os melhores formatos de vídeo e criar recortes.

## Instalação

Abra o PowerShell na pasta do projeto:

```powershell
cd C:\Users\Romeo\Documents\aulas\baixar_live\Live-Chat-Peak-Analyzer
```

Instale as dependências do backend:

```powershell
python -m pip install -r backend\requirements.txt
```

Instale as dependências do frontend:

```powershell
cd frontend
npm install
cd ..
```

Confirme se as ferramentas estão disponíveis:

```powershell
python --version
yt-dlp --version
ffmpeg -version
node --version
```

## Executar

Inicie o backend em um terminal:

```powershell
python backend\app.py
```

Em outro terminal, inicie o frontend:

```powershell
cd frontend
npm run dev
```

Abra no navegador:

```text
http://127.0.0.1:5173
```

## Uso básico

1. Cole a URL da gravação da live.
2. Aguarde o download do vídeo e a coleta do chat.
3. Abra a live processada.
4. Use o player e a timeline para navegar.
5. Clique em um pico do chat para ir até aquele momento.
6. Arraste as alças de início e fim para selecionar um trecho.
7. Adicione marcações na posição atual usando o botão **Marcação**.
8. Clique em **Criar e baixar trecho** para gerar o recorte.

O replay do chat é separado do vídeo. Se nenhuma mensagem aparecer, use o botão **Tentar coletar chat** na página de análise.

Ao abrir uma live sem vídeo local, a aplicação tenta baixar a gravação completa novamente. Depois que o vídeo estiver salvo, a timeline libera reprodução, marcações e recortes com precisão.

## Dados gerados

Os downloads e relatórios ficam na pasta `.data`, criada automaticamente dentro do projeto. Essa pasta pode ser apagada quando quiser remover os dados locais.

Os logs do backend ficam em `.data\backend.log` e também aparecem no terminal
onde `python backend\app.py` está rodando. O arquivo registra as tentativas do
`yt-dlp`, saídas de erro, caminhos dos arquivos gerados e exceções sem gravar
o conteúdo dos cookies.

Para apagar tudo pela linha de comando:

```powershell
python backend\app.py --clear-data
```

O código da interface fica em `frontend\web`. O Vite executa o frontend
independentemente do backend e encaminha `/api`, `/media` e `/clips` para
`http://127.0.0.1:8000`. As APIs, o processamento e os downloads ficam em
`backend`.

Para gerar uma build de produção do frontend:

```powershell
cd frontend
npm run build
```

O diretório `frontend\dist` é apenas um artefato de build e não é necessário
para o modo de desenvolvimento separado.

Use essa opção com cuidado: ela remove os vídeos, chats, relatórios e metadados salvos localmente.

## Observações

- O download depende da disponibilidade pública da gravação e das regras da plataforma.
- Se o YouTube mostrar `Sign in to confirm you’re not a bot`, mantenha a conta do YouTube conectada no Edge, Chrome ou Firefox. A aplicação tentará usar automaticamente os cookies dos navegadores instalados.
- Se existir `C:\Users\Romeo\Downloads\www.youtube.com_cookies.txt` ou `C:\Users\Romeo\Downloads\cookies.txt`, a aplicação também tentará usar esse arquivo automaticamente.
- Feche completamente o navegador antes de tentar novamente se a leitura dos cookies falhar.
- Confirme que a gravação reproduz normalmente no navegador conectado. Se ela também estiver bloqueada no navegador, o trecho não poderá ser baixado pela aplicação.
- Algumas lives não possuem replay de chat.
- O servidor deve continuar aberto enquanto a aplicação estiver sendo usada.
- Para encerrar, volte ao PowerShell e pressione `Ctrl+C`.
- Apague o arquivo de cookies depois do uso, pois ele permite acesso à sua sessão do YouTube.
