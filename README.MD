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

Instale a dependência Python:

```powershell
python -m pip install -r requirements.txt
```

Confirme se as ferramentas estão disponíveis:

```powershell
python --version
yt-dlp --version
ffmpeg -version
node --version
```

## Executar

Inicie o servidor:

```powershell
python app.py
```

Abra no navegador:

```text
http://127.0.0.1:8000
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

## Dados gerados

Os downloads e relatórios ficam na pasta `.data`, criada automaticamente dentro do projeto. Essa pasta pode ser apagada quando quiser remover os dados locais.

Para apagar tudo pela linha de comando:

```powershell
python app.py --clear-data
```

Use essa opção com cuidado: ela remove os vídeos, chats, relatórios e metadados salvos localmente.

## Observações

- O download depende da disponibilidade pública da gravação e das regras da plataforma.
- Algumas lives não possuem replay de chat.
- O servidor deve continuar aberto enquanto a aplicação estiver sendo usada.
- Para encerrar, volte ao PowerShell e pressione `Ctrl+C`.
