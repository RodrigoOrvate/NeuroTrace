<p align="center">
  <img src="memorylab.ico" alt="NeuroTrace Logo" width="120">
</p>

<h1 align="center">NeuroTrace</h1>

<p align="center">
  <strong>Organizador de dados Topscan para pesquisa comportamental</strong>
</p>

<p align="center">
  <a href="https://github.com/RodrigoOrvate/NeuroTrace/releases/latest">
    <img src="https://img.shields.io/github/v/release/RodrigoOrvate/NeuroTrace?style=for-the-badge&color=ab3d4c&label=Vers%C3%A3o" alt="Versão">
  </a>
  <a href="https://github.com/RodrigoOrvate/NeuroTrace/releases/latest">
    <img src="https://img.shields.io/github/downloads/RodrigoOrvate/NeuroTrace/total?style=for-the-badge&color=2d2d4a&label=Downloads" alt="Downloads">
  </a>
  <img src="https://img.shields.io/badge/Plataforma-Windows%20|%20macOS-blue?style=for-the-badge&color=1a1a2e" alt="Plataforma">
</p>

---

## 📖 Sobre

O **NeuroTrace** é uma ferramenta desktop desenvolvida para automatizar a organização e filtragem de dados gerados pelo software **Topscan**, amplamente utilizado em pesquisas de comportamento animal em laboratórios de neurociência.

> **Compatível com Windows e macOS** — usa PyQt5 (Windows) e PySide6 (macOS) através de camada de compatibilidade automática.

### O que o programa faz?

- **Procurar Objetos (OBJ):** Filtra e organiza os dados de reconhecimento de objetos a partir de planilhas do Topscan, separando por pares de objetos e gerando uma planilha formatada.
- **Organizar Distância/Velocidade (DIST/VEL):** Organiza automaticamente os dados de distância e velocidade, consolidando todas as informações em uma única planilha com abas separadas.

---

## 🚀 Instalação

### 🪟 Windows

#### Opção 1 — Instalador (Recomendado)

A forma mais simples de instalar o programa. O instalador configura tudo automaticamente.

1. Acesse a **[página de Releases](https://github.com/RodrigoOrvate/NeuroTrace/releases/latest)**
2. Baixe o arquivo **`NeuroTrace_Setup_v2.0.0.exe`**
3. Execute o instalador e siga as instruções
4. O programa será instalado em `C:\Program Files (x86)\NeuroTrace` e um atalho será criado na **Área de Trabalho**

> **Nota:** O Windows pode exibir um alerta do SmartScreen na primeira execução. Clique em **"Mais informações"** → **"Executar assim mesmo"**.

#### Opção 2 — Executável Portátil

Se preferir não instalar, pode usar o executável diretamente.

1. Acesse a **[página de Releases](https://github.com/RodrigoOrvate/NeuroTrace/releases/latest)**
2. Baixe o arquivo **`NeuroTrace.exe`**
3. Salve em qualquer pasta e execute diretamente

---

### 🍎 macOS

#### Opção 1 — Instalador .dmg (Recomendado)

1. Acesse a **[página de Releases](https://github.com/RodrigoOrvate/NeuroTrace/releases/latest)**
2. Baixe o arquivo **`NeuroTrace_macOS_v2.0.0.dmg`**
3. Abra o `.dmg` e arraste o **NeuroTrace** para a pasta **Applications**
4. Na primeira vez, clique com o botão direito → **"Abrir"** para autorizar a execução

> **Nota:** Como o app não é assinado com certificado Apple Developer, o macOS pode bloquear a execução. Se aparecer a mensagem _"não pode ser aberto porque o desenvolvedor não pode ser verificado"_, vá em **Ajustes do Sistema → Privacidade e Segurança** e clique em **"Abrir Mesmo Assim"**.

#### Opção 2 — Executar a partir do código-fonte

Se o `.dmg` não estiver disponível, você pode rodar diretamente com Python:

```bash
# Instalar dependências (PySide6 funciona em ambas as plataformas)
pip3 install PySide6 pandas openpyxl

# Executar
python3 main.py
```

---

## 🖥️ Como Usar

### 1. Procurar Objetos (OBJ)

1. Clique em **"Pesquisar Arquivo (OBJ)"** e selecione a planilha `.xlsx` do Topscan
2. Clique em **"Ver Objetos"** para visualizar os pares de objetos e OBJs detectados
3. Defina a **quantidade de planilhas** (conjuntos) que deseja processar
4. Clique em **"Criar Conjuntos"** e preencha os campos de cada planilha
5. Clique em **"Procurar Objetos"** para gerar o arquivo `dados_filtrados_obj.xlsx`

### 2. Organizar Distância/Velocidade (DIST/VEL)

1. Clique em **"Pesquisar Arquivo (DIST/VEL)"** e selecione a planilha do Topscan
2. Clique em **"Organizar Dist/Vel"** para gerar o arquivo `dados_filtrados_distvel.xlsx`

> 💡 **Dica:** Os arquivos gerados são salvos na mesma pasta do executável e abrem automaticamente após o processamento.

---

## 🔄 Atualizações Automáticas

O programa verifica automaticamente se há novas versões ao iniciar. Quando uma atualização estiver disponível, um diálogo aparecerá com as opções de download. O sistema suporta todos os cenários de transição:

| De → Para | Comportamento |
|---|---|
| Portátil → Portátil | Substitui o `.exe` no lugar e reinicia |
| Portátil → Instalador | Executa o Setup e remove o `.exe` portátil antigo |
| Instalador → Instalador | Executa o novo Setup (`/SILENT /CLOSEAPPLICATIONS`) |
| Instalador → Portátil | Move o `.exe` para a Área de Trabalho e desinstala a versão anterior |

Você também pode verificar manualmente clicando no botão **"Atualizar 🔄"** na interface.

---

## 🛠️ Desenvolvimento

### Pré-requisitos

- Python 3.10+
- Dependências:

```bash
pip install PyQt5 pandas openpyxl pyinstaller  # Windows
# ou
pip install PySide6 pandas openpyxl pyinstaller  # macOS / multiplataforma
```

### Executar em modo desenvolvimento

```bash
python main.py
```

### Build para Windows

```bash
# Apenas o .exe
packaging\build_exe.bat

# .exe + Instalador (requer Inno Setup 6)
packaging\build_installer.bat
```

O `.exe` será gerado em `dist/NeuroTrace.exe` e o instalador em `installer_output/`.

### Build para macOS

```bash
chmod +x packaging/build_macos.sh
./packaging/build_macos.sh
```

O `.app` será gerado em `dist/NeuroTrace.app` e o `.dmg` em `installer_output/`.

---

## 📁 Estrutura do Projeto

```
NeuroTrace/
├── .github/workflows/      # CI/CD para build macOS
│   ├── build_macos.yml     # GitHub Actions — gera o .dmg
│   └── build_windows.yml   # GitHub Actions — gera .exe e setup
│
├── main.py                 # Interface principal (Qt)
├── qt_compat.py            # Compatibilidade PyQt5/PySide6
├── procurar_objeto.py      # Lógica de filtragem de objetos
├── procurar_distvel.py     # Lógica de organização dist/vel
├── updater.py              # Auto-atualização via GitHub Releases
├── memorylab.ico           # Ícone do aplicativo
├── requirements.txt        # Dependências por plataforma
│
├── packaging/              # Scripts de build e empacotamento
│   ├── main.spec           # PyInstaller spec — Windows
│   ├── main_macos.spec     # PyInstaller spec — macOS
│   └── installer.iss       # Inno Setup — instalador Windows
│
├── dist/                   # Executáveis compilados (gitignored)
└── installer_output/       # Instaladores gerados (gitignored)
```

---

## 📋 Changelog

### v2.0.0

- 🔄 **Rebranding** do programa de AUTOMATIZADO para **NeuroTrace**
- ✨ Interface completamente redesenhada com **PyQt5** (migração do tkinter)
- 🎨 Design moderno com **tema escuro** e paleta laboratorial
- 🔄 Sistema de **auto-atualização** via GitHub Releases
- 📦 **Instalador Windows** com atalho na área de trabalho
- 🍎 **Suporte a macOS** com `.app` bundle e `.dmg` installer
- 🧹 Refatoração completa do código com boas práticas

### v1.0.0

- Versão inicial com interface tkinter
- Funcionalidades básicas de filtragem de objetos e dist/vel

---

## 📄 Licença

Este projeto está licenciado sob a [Licença MIT](LICENSE) — veja o arquivo para detalhes.

---

<p align="center">
  Desenvolvido por <strong>Rodrigo Orvate</strong>
</p>
