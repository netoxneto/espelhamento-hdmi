# Espelhamento HDMI (Windows 11)

Projeto inicial para selecionar uma janela do Windows e exibi-la em tela cheia em um monitor/TV HDMI configurado em **Estender**. Não usa OBS, rede, Chromecast ou captura de desktop recortada.

## Estado real da implementação

**Importante: esta entrega é um protótipo inicial, não uma versão integralmente concluída nem validada em hardware Windows.**
- Enumeração de monitores Win32: implementada.
- Listagem de janelas visíveis com título, HWND e PID: implementada.
- Saída sem bordas em tela cheia, proporção preservada: implementada no Qt.
- Captura de vídeo: integração com `windows-capture`/Windows Graphics Capture incluída, mas a API de frame-buffer pode variar entre versões e precisa ser validada no Windows de destino.
- Bloqueio do cursor com `ClipCursor` e atalho Ctrl+Alt+F12: implementação inicial; teste o desbloqueio antes de uso prolongado.
- Áudio por processo via WASAPI Process Loopback: **não implementado ainda**. O programa não finge capturar áudio nem transmite áudio global.
- Tratamento avançado de janela minimizada, reconexão HDMI e recuperação de captura: ainda precisa ser concluído.
- Os testes listados abaixo são um plano de testes; não afirmam que foram executados.

## Requisitos

- Windows 11 x64.
- Python 3.11, 3.12 ou 3.13 x64.
- TV conectada por HDMI.
- O modo de exibição do Windows deve estar em **Estender**.

## Instalação

1. Instale Python x64 a partir de https://www.python.org/downloads/windows/ e marque **Add python.exe to PATH**.
2. Extraia esta pasta em um local gravável.
3. Execute `install.bat`.
4. Se a instalação falhar, leia a mensagem completa no terminal; o instalador não suprime erros.

## Configurar a TV

1. Conecte o HDMI.
2. Pressione `Win + P`.
3. Selecione **Estender**.
4. Em Configurações > Sistema > Tela, identifique a TV e ajuste a posição relativa dos monitores se necessário.
5. Não altere a resolução para usar este protótipo; a janela de saída usa as dimensões detectadas do monitor.

## Executar

Execute `run.bat`, selecione o monitor da TV e depois a janela. Use `Ctrl+C` no terminal para solicitar encerramento.

## Atalhos

O bloqueio do mouse usa `ClipCursor` e um watchdog independente do terminal, reaplicando o retângulo do monitor principal a cada 50 ms. Minimizar o terminal ou mudar o foco não deve liberar o cursor.


- `Ctrl+Alt+F12`: alterna o confinamento do cursor ao monitor principal, se o registro do atalho global for aceito.
- `Ctrl+C` no terminal: solicita encerramento. Ao fechar normalmente, o código chama `ClipCursor(NULL)`.

**Cuidado:** se o processo for encerrado à força, o Windows normalmente libera o clip ao terminar o processo, mas não dependa disso como mecanismo de segurança. Teste primeiro e mantenha acesso ao teclado.

## Gerar executável

Execute `build.bat` depois da instalação. O resultado esperado fica em `dist\EspelhamementoHDMI.exe` (confira o nome real produzido). O executável e a captura precisam ser validados em uma máquina Windows 11 limpa.

## Plano de testes

Marque cada item somente depois de testar em Windows 11:
- [ ] Chrome
- [ ] Edge
- [ ] PowerPoint
- [ ] Bloco de Notas
- [ ] Windows Explorer
- [ ] Aplicativo Python
- [ ] Aplicativo Electron
- [ ] Redimensionamento e maximização
- [ ] Minimização e restauração
- [ ] Fechamento da janela
- [ ] Desconexão/reconexão da TV
- [ ] Áudio do processo selecionado (não suportado nesta versão)
- [ ] Bloqueio e desbloqueio do cursor
- [ ] Encerramento normal e forçado

## Limitações conhecidas

1. A API de `windows-capture` e a forma de expor os buffers podem variar por versão. Se `frame.frame_buffer` não estiver disponível, a captura falhará explicitamente; não existe fallback para captura da tela inteira.
2. O áudio por processo requer integração WASAPI Process Loopback e não está implementado nesta versão.
3. A captura de janelas minimizadas depende do comportamento do Windows Graphics Capture; a recuperação automática ainda precisa de trabalho.
4. A interface é um protótipo CLI + janela de saída. Não é um serviço e não deve ser executada com privilégios administrativos.
5. A instalação de pacotes pode falhar se não houver wheel compatível para a versão do Python. Use Python x64 3.11–3.13.

## Estrutura

- `app/windows`: enumeração de monitores e janelas.
- `app/video`: sessão de captura e renderização.
- `app/audio`: pontos de integração de áudio, com limitações explicitadas.
- `app/input`: confinamento do cursor.
- `app/config`: leitura de configuração.

## Próxima fase necessária para uma versão de produção

- Fixar e testar uma versão exata de `windows-capture` e adaptar o callback ao formato real dos frames.
- Implementar WASAPI Process Loopback para o PID escolhido e roteamento ao endpoint HDMI selecionado.
- Implementar controle de ciclo de vida da janela capturada, janelas minimizadas, desconexões e recuperação.
- Criar testes de integração reais no Windows 11, inclusive monitor com DPI diferente.

## Trocar a janela durante a transmissão

A transmissão agora permanece aberta enquanto a janela capturada é trocada.

No terminal da aplicação:

```text
T
```

O programa lista novamente as janelas e você escolhe outra. A saída na TV continua sendo a mesma; somente a captura WGC é encerrada e uma nova captura da janela escolhida é iniciada.

Exemplo:

```text
Comandos: [T] trocar janela  [L] mouse bloqueado/liberado  [Q] encerrar
> T

Janelas disponíveis:
[1] Google Chrome  (PID 1234)
[2] PowerPoint  (PID 5678)
[3] Visual Studio Code  (PID 9012)

Digite o número da nova janela: 2

Transmitindo agora: PowerPoint (PID 5678)
```

Não é necessário fechar e abrir o programa.

## Bloqueio real do mouse

O bloqueio usa a API Win32 `ClipCursor`. Isso **não é apenas ocultação do cursor**.

Enquanto estiver bloqueado, o Windows restringe fisicamente a posição do cursor ao retângulo do monitor principal. Portanto, mesmo que a TV esteja ao lado do monitor no modo **Estender**, o ponteiro não consegue atravessar para ela.

`Ctrl+Alt+F12` alterna entre:

```text
BLOQUEADO → LIBERADO → BLOQUEADO
```

Ao encerrar a aplicação, `ClipCursor(NULL)` é chamado para restaurar o comportamento normal.

### Observação importante

O atalho de emergência existe justamente para evitar ficar sem acesso ao cursor. Recomenda-se testar `Ctrl+Alt+F12` antes de usar o programa em uma apresentação.

## Segurança da troca de janela

A sessão de captura usa uma máquina de estados (`STOPPED`, `STARTING`, `RUNNING`, `SWITCHING`, `STOPPING`, `FAILED`, `CLOSED`), um lock curto para o estado compartilhado e um lock separado para serializar `start`, `switch` e `stop`.

A nova `WindowsCapture` é registrada como captura atual **antes** de `start_free_threaded()`, porque o callback de frame pode ocorrer antes de essa chamada retornar. A geração da sessão invalida callbacks atrasados da captura anterior, e `control.wait()` é chamado fora do lock de estado antes de iniciar a captura seguinte.

Falhas no start limpam as referências e fazem rollback da janela anterior quando possível. A troca é centralizada em `switch_window()`, e `stop()` é idempotente.

Os testes de concorrência ficam em `tests/test_capture_session.py` e cobrem os cenários críticos de inicialização, troca, callbacks atrasados, rollback e shutdown.

## 🖥️ Interface gráfica

A partir da versão GUI, o controle principal pode ser feito pelo aplicativo PySide6, sem depender dos comandos do terminal.

A interface permite:

- selecionar o monitor/TV de saída;
- listar e selecionar a janela que será transmitida;
- iniciar a transmissão;
- trocar a janela durante a transmissão;
- parar a transmissão sem encerrar o aplicativo;
- atualizar a lista de monitores e janelas;
- bloquear ou liberar o mouse;
- visualizar o status atual da transmissão.

A captura continua sendo controlada pela mesma `CaptureSession` utilizada anteriormente. A GUI não cria uma segunda implementação de captura.

As operações de início, troca e parada são executadas fora da thread visual para evitar que a interface congele enquanto a captura nativa é encerrada ou iniciada.

### Fluxo da GUI

```text
Abrir aplicativo
      ↓
Selecionar monitor/TV
      ↓
Selecionar janela
      ↓
Transmitir
      ↓
┌───────────────────────────┐
│        TRANSMITINDO       │
│                           │
│ Janela: Google Chrome     │
│ Saída: TV HDMI            │
└───────────────────────────┘
      ↓
Selecionar outra janela
      ↓
Troca segura da captura
```

A saída fullscreen permanece separada da janela de controle. Quando a transmissão está parada, a saída permanece oculta para não cobrir a interface principal.

## ⌨️ Atalhos

O bloqueio do mouse continua podendo ser alternado pelo atalho global:

```text
Ctrl + Alt + F12
```

O ponteiro continua confinado ao monitor principal e, quando `cursor_capture` está habilitado, o cursor pode aparecer dentro da imagem capturada enviada para a TV.


## Correção v10
A inicialização do `WindowsCapture` é feita no thread principal do Qt, preservando o mesmo contexto usado pela versão funcional anterior. O `start_free_threaded()` da biblioteca continua sendo responsável pela thread nativa da captura.

## Cursor na saída

A captura usa `cursor_capture=False`. O cursor é desenhado pela saída fullscreen somente quando o ponteiro físico está dentro da janela selecionada. Assim, mover o mouse pelo desktop ou pela GUI não faz o ponteiro aparecer na TV.
