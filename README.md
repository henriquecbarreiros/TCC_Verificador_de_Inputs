# TCC_Verificador_de_Inputs
Validador automatizado de testes Android com IA DeepSeek

## Descrição

Este projeto implementa uma ferramenta automatizada para validação de arquivos de entrada (input) em testes de software Android, utilizando inteligência artificial (IA) através da API DeepSeek. O objetivo é reduzir o tempo gasto em verificações manuais e minimizar erros humanos, garantindo maior confiabilidade no processo de validação de configurações para dispositivos Android.

## Funcionalidades

- Validação automática de arquivos JSON contendo configurações de teste
- Detecção de incompatibilidades entre hardware, software, região e tecnologias suportadas
- Interface gráfica simples e intuitiva (Tkinter)
- Feedback detalhado sobre cada validação (PASS/FAIL)
- Registro e histórico de resultados
- Protótipo experimental de feedback técnico e chatbot integrado (apêndices do TCC)

## Como usar

1. **Clone o repositório:**

   ```bash
   git clone https://github.com/henriquecbarreiros/TCC_Verificador_de_Inputs.git
## Pré Requisitos
Unzip os arquivos vscode, myenv e Inputs
Caso tenha problemas com o myenv, crie um proprio no pc 

Instale as dependências (caso necessário):

- Python 3.x
- pip install requests
- pip install tkinter

Configure sua chave de API DeepSeek
crie um arquivo .env e insira sua chave api usando o exemplo enviado

Execute o sistema: atraves de python Input_Checker_VF.py
