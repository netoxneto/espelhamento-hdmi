# Espelhamento HDMI

Aplicação para **Windows 11 x64** desenvolvida em Python para capturar uma janela de aplicativo e exibi-la em **tela cheia em um segundo monitor/TV conectado via HDMI**, mantendo o Windows no modo **Estender**.

O projeto utiliza **Windows Graphics Capture** para realizar a captura da janela e **PySide6** para renderizar o conteúdo capturado em uma janela fullscreen no monitor escolhido.

## ✨ Funcionalidades

* 🖥️ Seleção do monitor de saída.
* 🪟 Seleção da janela que será transmitida.
* 📺 Exibição em tela cheia no segundo monitor/TV.
* 🔄 Troca da janela transmitida sem fechar o programa.
* 🖱️ Bloqueio físico do mouse no monitor principal.
* ⌨️ Atalhos de teclado para controlar a transmissão.
* 🔒 Controle de concorrência durante a troca de captura.
* ♻️ Recuperação automática em caso de falha ao iniciar uma nova captura.
* 🧹 Encerramento seguro dos recursos de captura.
* 🧪 Testes automatizados para os cenários críticos de troca de janela.
* 🪟 Utilização do `HWND` da janela quando disponível.
* ⚡ Captura através da API Windows Graphics Capture.

---

## 🖼️ Funcionamento

O fluxo básico da aplicação é:

```text
┌──────────────────────┐
│   Aplicação Windows  │
│   (janela escolhida) │
└──────────┬───────────┘
           │
           │ Windows Graphics Capture
           ▼
┌──────────────────────┐
│   CaptureSession     │
│                      │
│ - Controle da captura│
│ - Troca de janela    │
│ - Controle de estado │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│   FullscreenOutput   │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Monitor / TV HDMI    │
│      Tela cheia      │
└──────────────────────┘
```

O Windows deve estar configurado no modo:

**Configurações → Sistema → Tela → Estender estas telas**

---

# 📋 Requisitos

## Sistema operacional

* Windows 11 x64
* Dois monitores ou uma TV conectada via HDMI
* Windows configurado em modo **Estender**

## Python

Recomendado:

```text
Python 3.11+
```

Verifique sua versão:

```bash
python --version
```

---

# 📦 Instalação

Clone o repositório:

```bash
git clone https://github.com/SEU-USUARIO/espelhamento-hdmi.git
```

Entre na pasta:

```bash
cd espelhamento-hdmi
```

Opcionalmente, crie um ambiente virtual:

```bash
python -m venv .venv
```

Ative o ambiente virtual:

### Windows CMD

```cmd
.venv\Scripts\activate
```

### PowerShell

```powershell
.venv\Scripts\Activate.ps1
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

---

# ▶️ Executando

A forma mais simples é executar:

```bash
python app/main.py
```

Também é possível utilizar o script:

```cmd
run.bat
```

---

# 🎮 Controles

Depois que a aplicação estiver transmitindo:

| Tecla              | Função                             |
| ------------------ | ---------------------------------- |
| `T`                | Trocar a janela transmitida        |
| `L`                | Ativar/desativar bloqueio do mouse |
| `Ctrl + Alt + F12` | Ativar/desativar bloqueio do mouse |
| `Q`                | Encerrar a aplicação               |
| `0`                | Encerrar a aplicação               |

## 🔄 Trocando a janela

Durante a transmissão, pressione:

```text
T
```

A aplicação exibirá a lista de janelas disponíveis.

Digite o número correspondente à janela desejada.

A captura atual será encerrada antes que a nova captura seja iniciada.

A janela fullscreen do monitor de saída permanece aberta durante a troca.

---

# 🖱️ Bloqueio do mouse

Quando ativado, o cursor fica fisicamente limitado à área do monitor principal.

O bloqueio utiliza a API Win32:

```text
ClipCursor
```

Além disso, existe um watchdog que verifica periodicamente o estado do cursor e reaplica a restrição.

Isso evita que o mouse escape para o segundo monitor quando, por exemplo:

* o terminal é minimizado;
* outra janela recebe foco;
* o usuário muda de aplicativo;
* o terminal deixa de estar ativo.

O atalho global:

```text
Ctrl + Alt + F12
```

permite alternar o bloqueio sem depender do foco do terminal.

---

# 🏗️ Estrutura do projeto

```text
espelhamento-hdmi/
│
├── app/
│   ├── main.py
│   │
│   ├── windows/
│   │   ├── monitor_manager.py
│   │   └── window_manager.py
│   │
│   ├── video/
│   │   └── session.py
│   │
│   ├── input/
│   │   └── mouse_lock.py
│   │
│   ├── audio/
│   │   ├── process_capture.py
│   │   ├── audio_output.py
│   │   └── audio_devices.py
│   │
│   └── config/
│       └── settings.py
│
├── tests/
│   └── test_capture_session.py
│
├── config.json
├── requirements.txt
├── install.bat
├── run.bat
├── build.bat
├── README.md
└── LICENSE
```

---

# 🧩 Principais componentes

## `app/main.py`

É o ponto de entrada da aplicação.

Responsável por:

* selecionar o monitor;
* selecionar a janela;
* criar a sessão de captura;
* iniciar o controle do mouse;
* processar os comandos do terminal;
* executar o loop da aplicação.

---

## `app/video/session.py`

É o componente central da transmissão.

A classe `CaptureSession` funciona como a **fonte única de verdade** sobre a captura atualmente ativa.

Ela controla:

* início da captura;
* parada da captura;
* troca de janela;
* geração da captura;
* callbacks;
* estado atual;
* recuperação após falhas;
* encerramento seguro.

### Estados

A sessão utiliza uma máquina de estados:

```text
STOPPED
   │
   ▼
STARTING
   │
   ▼
RUNNING
   │
   ▼
SWITCHING
   │
   ▼
STOPPING
   │
   ▼
RUNNING
```

Em caso de erro:

```text
FAILED
```

E no encerramento:

```text
CLOSED
```

---

# 🔄 Segurança durante a troca de janela

A troca de janela é uma das partes mais sensíveis da aplicação.

O projeto evita manter duas capturas nativas simultaneamente.

O fluxo é aproximadamente:

```text
Captura A
   │
   ▼
invalidar geração A
   │
   ▼
parar A
   │
   ▼
wait() em A
   │
   ▼
criar captura B
   │
   ▼
registrar B como captura atual
   │
   ▼
start_free_threaded()
   │
   ▼
Captura B
```

Isso é importante porque callbacks do `windows-capture` podem ocorrer em momentos inesperados durante o início e encerramento da captura.

## Generation Token

Cada captura recebe uma geração.

Por exemplo:

```text
Captura A → geração 1
Captura B → geração 2
Captura C → geração 3
```

Se um callback antigo da captura A chegar depois que a captura B já estiver ativa, ele será ignorado.

Isso impede que uma captura antiga:

* altere o estado atual;
* substitua o frame atual;
* encerre a nova captura;
* limpe referências da captura atual.

---

# 🔒 Controle de concorrência

A aplicação utiliza dois mecanismos de sincronização:

### State Lock

Protege alterações rápidas no estado interno.

```text
_state_lock
```

Esse lock não é mantido durante operações nativas potencialmente bloqueantes.

### Operation Lock

Serializa operações como:

```text
start()
switch()
stop()
```

Isso evita situações como:

```text
T
T
T
```

gerando várias trocas simultâneas.

As operações são processadas de forma serializada.

---

# 🧪 Testes

Os testes ficam em:

```text
tests/test_capture_session.py
```

Para executar:

```bash
python -m unittest discover -s tests -v
```

Os testes cobrem, entre outros:

* início da captura;
* callback imediato após o início;
* callback antigo depois de uma troca;
* `on_closed` de uma captura antiga;
* falha ao iniciar uma captura;
* rollback para a janela anterior;
* parada idempotente;
* troca aguardando o encerramento da captura anterior;
* duas trocas concorrentes;
* garantia de que duas capturas nativas não ficam ativas simultaneamente.

---

# 🛠️ Validação do projeto

Antes de executar no Windows, é possível verificar a compilação sintática:

```bash
python -m compileall -q app tests
```

O projeto também evita o uso de:

```python
time.sleep()
```

como mecanismo de sincronização da captura.

A sincronização da troca é feita através dos controles e estados da própria sessão.

---

# 📺 Configuração de múltiplos monitores

O projeto foi pensado para o seguinte cenário:

```text
┌──────────────────────┐      HDMI      ┌──────────────────────┐
│                      │                │                      │
│   Monitor principal  │───────────────▶│      TV / Monitor    │
│                      │                │       secundário     │
│   Windows / controle │                │     fullscreen       │
│                      │                │                      │
└──────────────────────┘                └──────────────────────┘
```

O Windows deve estar em:

```text
Estender estas telas
```

e não em:

```text
Duplicar estas telas
```

---

# ⚠️ Limitações atuais

## Áudio

A estrutura do projeto possui módulos relacionados a áudio, porém a captura de áudio **por processo utilizando WASAPI Process Loopback** ainda não está implementada como parte funcional da transmissão.

Atualmente o foco principal é:

```text
Captura de vídeo
+
Exibição fullscreen
+
Troca dinâmica de janela
+
Controle do mouse
```

---

## Windows

O projeto depende de APIs específicas do Windows, principalmente:

* Windows Graphics Capture
* Win32 API
* `ClipCursor`
* HWND
* WASAPI

Portanto, o projeto não foi desenvolvido para Linux ou macOS.

---

# 📦 Gerando um executável

O projeto possui um script:

```cmd
build.bat
```

que pode ser utilizado para gerar uma versão distribuível utilizando PyInstaller.

Também é possível executar o PyInstaller manualmente conforme a configuração do projeto.

O resultado normalmente será colocado na pasta:

```text
dist/
```

---

# ⚙️ Configuração

Algumas configurações podem ser armazenadas em:

```text
config.json
```

Exemplo:

```json
{
    "fullscreen": true
}
```

As configurações disponíveis podem variar conforme a versão do projeto.

---

# 🧰 Tecnologias utilizadas

| Tecnologia      | Utilização                    |
| --------------- | ----------------------------- |
| Python          | Linguagem principal           |
| PySide6         | Interface e janela fullscreen |
| NumPy           | Manipulação dos frames        |
| OpenCV          | Processamento de imagem       |
| windows-capture | Windows Graphics Capture      |
| pywin32         | Integração com Win32          |
| sounddevice     | Recursos de áudio             |
| PyInstaller     | Geração do executável         |
| ctypes          | Acesso à API Win32            |

---

# 📌 Dependências principais

As dependências estão definidas em:

```text
requirements.txt
```

Entre elas estão:

```text
PySide6
numpy
opencv-python
windows-capture
pywin32
sounddevice
```

---

# 🚀 Roadmap

Possíveis melhorias futuras:

* [ ] Captura de áudio por processo via WASAPI Process Loopback
* [ ] Interface gráfica para seleção da janela
* [ ] Interface gráfica para seleção do monitor
* [ ] Troca de janela sem depender do terminal
* [ ] Atalhos configuráveis
* [ ] Configuração de FPS
* [ ] Configuração de resolução
* [ ] Indicador visual durante a troca
* [ ] Tela de configurações
* [ ] Empacotamento completo em `.exe`
* [ ] Inicialização automática
* [ ] Logs em arquivo
* [ ] Seleção automática da TV/monitor HDMI

---

# 🐛 Problemas e contribuições

Encontrou um problema?

Abra uma **Issue** descrevendo:

1. Versão do Windows
2. Versão do Python
3. GPU utilizada
4. Quantidade de monitores
5. Aplicação que estava sendo capturada
6. Passos para reproduzir o problema
7. Mensagens apresentadas no terminal

Pull Requests também são bem-vindos.

---

# 📄 Licença

Este projeto está disponível sob a licença definida no arquivo:

```text
MIT
```

---

# 👨‍💻 Autor
Miguel Neto

Desenvolvido para realizar captura e transmissão de janelas do Windows para uma segunda tela/TV através de HDMI.

---

## ⭐ Se este projeto foi útil

Se o projeto foi útil para você, considere deixar uma ⭐ no GitHub.

Isso ajuda a demonstrar interesse no projeto e incentiva futuras melhorias.
