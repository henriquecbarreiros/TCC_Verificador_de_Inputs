import tkinter as tk #importa bliblioteca tkinter, responsavel pela parte grafica
from tkinter import filedialog, messagebox, scrolledtext #Importação dos componentes do Tkinter para interface gráfica
import requests #Permite fazer requisições HTTP para comunicação com com a DeepSeek.
import os #Fornece acesso a funções do sistema operacional
import hashlib # Utilizado para criar hashes (resumos únicos) de dados, útil para identificar arquivos ou entradas de forma segura.
import json # Permite ler, escrever e manipular dados no formato JSON
from dotenv import load_dotenv # Carrega variáveis de ambiente do arquivo .env, protegendo a chave de API.
from datetime import datetime, timedelta # Fornece ferramentas para manipular datas e horários.

# Carrega variáveis do .env
load_dotenv()
deepseek_api_key = os.getenv("DEEPSEEK_API_KEY") #Local onde a API key está localizada
LAST_DIR_FILE = "last_dir.json" #Local onde está localizado a ultima pasta aberta do programa

# Abre o arquivo que armazena o último diretório usado, lê os dados em formato JSON
# e verifica se a pasta ainda existe. Se sim, retorna esse diretório, caso não, retorna o diretório atual
def carregar_ultimo_dir(): 
    try:
        with open(LAST_DIR_FILE, "r") as f: 
            data = json.load(f)  
            if os.path.isdir(data.get("last_dir", "")):  
                return data["last_dir"] 
            return os.getcwd() 
    except Exception as e:
        print(f"Erro ao carregar último diretório: {e}") # Em caso de erro, exibe uma mensagem
        return os.getcwd() # E retorna o diretório atual

def salvar_ultimo_dir(caminho):
    """Salva o último diretório acessado."""
    with open(LAST_DIR_FILE, "w") as f: # Abre o arquivo para escrita
        json.dump({"last_dir": os.path.dirname(caminho)}, f) # Salva o caminho da pasta do arquivo selecionado em formato JSON

# Cache de resultados com expiração
class ResultCache:
    def __init__(self, max_size=100, ttl_hours=24): 
        self.cache = {} #Dicionário para armazenar os resultados em cache
        self.max_size = max_size  #Número máximo de itens permitidos no cache
        self.ttl = timedelta(hours=ttl_hours) #Tempo de vida (TTL) dos itens no cache
    
    def add(self, key, value):
        if len(self.cache) >= self.max_size:
            self.cleanup() #Remove o item mais antigo se o cache estiver cheio
        self.cache[key] = {
            'value': value, #Valor do resultado em cache
            'timestamp': datetime.now() #Momento em que o item foi adicionado (para expiração)
        }
    
    def get(self, key):
        item = self.cache.get(key) #Tenta recuperar o item pelo identificador
        # Verifica se o item existe e se ainda está dentro do tempo de validade (TTL)
        if item and (datetime.now() - item['timestamp']) < self.ttl:
            return item['value'] # Retorna o valor do cache se estiver válido
        return None  # Retorna None se não existir ou se já expirou
    
    def cleanup(self): # Remove o item mais antigo do cache para liberar espaço
        oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k]['timestamp'])
        del self.cache[oldest_key]

cache_resultados = ResultCache() # Instancia a classe ResultCache para uso no programa

# Gera um hash único baseado no input
def gerar_hash(input_str):
    return hashlib.sha256(input_str.encode()).hexdigest()

#A função garante que o arquivo de entrada tenha todas as informações essenciais antes de prosseguir com a análise. 
# Se faltar algum campo importante, ela interrompe o processo e avisa qual campo está faltando, evitando que a validação continue com dados incompletos.
def validar_estrutura_input(input_json): 
    campos_obrigatorios = [
        "Hardware", "Software", "Regiao_Execucao",
        "Versao_Android", "WiFi", "NFC", "Bluetooth", "SIM", "Rede"
    ]
    for campo in campos_obrigatorios:
        if campo not in input_json:
            raise ValueError(f"Campo obrigatório faltando: {campo}")

# A função verifica se o software informado pode ser usado em determinada região,
# de acordo com o banco de dados do hardware. Isso garante que testes e validações respeitem regras regionais de compatibilidade.
def validar_relacao_software_regiao(banco, hardware, software, regiao):
    hw_data = banco.get(hardware, {})
    regioes = hw_data.get("Regioes", {})
    
    if isinstance(regioes, dict):
        # Caso dicionário: verifica se o software está na lista da região
        if regiao in regioes:
            return software in regioes[regiao]
        return False
    elif isinstance(regioes, list):
        # Caso lista: verifica apenas se a região existe
        return regiao in regioes
    return False

# Função para análise via DeepSeek, onde são passadas as instruções necessárias para a IA verificar os inputs
def analisar_deepseek(banco_de_dados, input_de_teste):
    headers = {
        "Authorization": f"Bearer {deepseek_api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system", 
                "content": """Você é um validador técnico. Formato OBRIGATÓRIO:

RESULTADOS:
- HARDWARE: PASS/FAIL [valor no input]
- SOFTWARE: PASS/FAIL [valor no input]
- RELAÇÃO_SOFTWARE_REGIAO: PASS/FAIL [Software/Região] 
  → Se 'Regioes' for dicionário: FAIL se software não estiver na lista da região
  → Se 'Regioes' for lista: FAIL se região não existir
- VERSAO_ANDROID: PASS/FAIL [valor no input]
- WIFI: PASS/FAIL [valor no input]
- NFC: PASS/FAIL [valor no input]
- BLUETOOTH: PASS/FAIL [valor no input]
- SIM: PASS/FAIL [valor no input]
- REDE: PASS/FAIL [valor no input]

Exemplo de RESULTADOS:

RESULTADOS:
- HARDWARE: PASS [Hardware_A]
- SOFTWARE: PASS [TREVAN-VS7]
- RELAÇÃO_SOFTWARE_REGIAO: PASS [TREVAN-VS7 está na lista da região Germany]
- VERSAO_ANDROID: PASS [Android 15]
- WIFI: PASS [2.4GHz]
- NFC: PASS [true]
- BLUETOOTH: FAIL [4.0] → Valor esperado: "5.0+"
- SIM: FAIL [Single SIM] → Valor esperado: "Dual SIM"
- REDE: FAIL [8G] → Valores esperados: ["4G", "5G", "6G"]

REGRAS RÍGIDAS:
1. Para RELAÇÃO_SOFTWARE_REGIAO:
   - Caso 1: Se 'Regioes' for um dicionário {região: [softwares]}, o software deve estar na lista da região especificada.
   - Caso 2: Se 'Regioes' for uma lista [regiões], a região do input deve existir na lista.
2. Para tecnologias (WiFi, NFC, Bluetooth, SIM, Rede): comparação exata de valores entre aspas. 
Exemplo: se o valor do input for 2.4GHz e no banco tiver uma das opções como 2.4GHZ, considere como PASS.
3. Sempre mostre o valor esperado no banco em caso de FAIL.
4. Para Bluetooth:
   - Se o valor no banco terminar com '+' (ex: "5.0+"), considere PASS para versões iguais ou superiores.
   - Caso contrário, faça comparação exata.
   """
            },
            {
                "role": "user", 
                "content": f"""Dados para análise:

BANCO DE DADOS:
{json.dumps(banco_de_dados, indent=2)}

INPUT:
{json.dumps(input_de_teste, indent=2)}

INSTRUÇÕES:
1. Para cada campo no input, verifique no banco
2. Seja rigoroso nas comparações e consulte apenas o banco de dados.
3. Mostre valores reais do banco em caso de FAIL"""
            }
        ],
        "temperature": 0,
        "max_tokens": 800
    }

    try:
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"ERRO: {str(e)}"

def executar_analise():
    status_bar.config(text="Analisando...")
    caminho = input_path_var.get()
    if not caminho:
        messagebox.showwarning("Aviso", "Selecione um arquivo de input primeiro.")
        return

    try:
        with open(caminho, "r", encoding="utf-8") as f:
            input_json = json.load(f)
            validar_estrutura_input(input_json)
            input_teste = json.dumps(input_json, indent=4)
    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao ler arquivo JSON: {str(e)}")
        return

    try:
        with open("software_db.json", "r", encoding="utf-8") as f:
            banco = json.load(f)
    except Exception as e:
        messagebox.showerror("Erro", f"Erro ao ler banco de dados: {str(e)}")
        return
    
    relacao_valida = validar_relacao_software_regiao(
        banco, input_json["Hardware"], input_json["Software"], input_json["Regiao_Execucao"]
    )
    if not relacao_valida:
        messagebox.showwarning("Aviso", "Relação Hardware/Software/Região inválida!")
        return  # Interrompe a execução se a validação local falhar    

    nome_hw = input_json["Hardware"]
    if nome_hw not in banco:
        messagebox.showwarning("Aviso", f"Hardware '{nome_hw}' não encontrado no banco de dados.")
        return

    entrada_hash = f"{input_json['Hardware']}{input_json['Software']}{input_json['Regiao_Execucao']}"
    chave = gerar_hash(entrada_hash)

    resultado = cache_resultados.get(chave)
    if not resultado:
        resultado = analisar_deepseek(banco, input_teste)
        cache_resultados.add(chave, resultado)

    output_text.delete(1.0, tk.END)
    output_text.insert(tk.END, resultado)
    status_bar.config(text="Pronto")

def escolher_arquivo(): #Função para selecionar o arquivo .json
    # Carrega o último diretório usado
    ultimo_dir = carregar_ultimo_dir()
    
    caminho = filedialog.askopenfilename(
        title="Selecione o arquivo de input",
        filetypes=[("Arquivos JSON", "*.json")],
        initialdir=ultimo_dir  # Abre no último diretório acessado
    )
    
    if caminho:
        input_path_var.set(caminho)
        salvar_ultimo_dir(caminho)  # Salva o novo diretório

# Interface Tkinter
janela = tk.Tk()
janela.title("Validador de Testes Android com DeepSeek - VF")
janela.geometry("900x750")
janela.configure(bg="#f0f0f0")

# Estilos
fonte_padrao = ("Arial", 10)
fonte_titulo = ("Arial", 12, "bold")
cor_botao = "#4CAF50"
cor_botao_sec = "#2196F3"

# Frame superior
frame_superior = tk.Frame(janela, bg="#f0f0f0", padx=10, pady=10)
frame_superior.pack(fill=tk.X)

tk.Label(
    frame_superior,
    text="Validador de Configurações Android",
    font=fonte_titulo,
    bg="#f0f0f0"
).pack(pady=5)

# Frame de seleção de arquivo
frame_arquivo = tk.Frame(janela, bg="#f0f0f0", padx=10, pady=5)
frame_arquivo.pack(fill=tk.X)

tk.Label(
    frame_arquivo,
    text="Arquivo de Input (.json):",
    font=fonte_padrao,
    bg="#f0f0f0"
).pack(side=tk.LEFT)

input_path_var = tk.StringVar()
entrada_arquivo = tk.Entry(
    frame_arquivo,
    textvariable=input_path_var,
    width=60,
    font=fonte_padrao
)
entrada_arquivo.pack(side=tk.LEFT, padx=5)

tk.Button(
    frame_arquivo,
    text="Procurar",
    command=escolher_arquivo,
    bg=cor_botao_sec,
    fg="white",
    font=fonte_padrao
).pack(side=tk.LEFT)

# Frame de botões
frame_botoes = tk.Frame(janela, bg="#f0f0f0", padx=10, pady=10)
frame_botoes.pack(fill=tk.X)

tk.Button(
    frame_botoes,
    text="Executar Análise",
    command=executar_analise,
    bg=cor_botao,
    fg="white",
    font=fonte_titulo,
    padx=20,
    pady=5
).pack()

# Área de resultados
frame_resultados = tk.Frame(janela, bg="#f0f0f0", padx=10, pady=10)
frame_resultados.pack(fill=tk.BOTH, expand=True)

tk.Label(
    frame_resultados,
    text="Resultado da Análise:",
    font=fonte_padrao,
    bg="#f0f0f0"
).pack(anchor=tk.W)

output_text = scrolledtext.ScrolledText(
    frame_resultados,
    wrap=tk.WORD,
    width=100,
    height=25,
    font=("Consolas", 10),
    bg="white",
    fg="#333333"
)
output_text.pack(fill=tk.BOTH, expand=True)

# Status bar
status_bar = tk.Label(
    janela,
    text="Pronto",
    bd=1,
    relief=tk.SUNKEN,
    anchor=tk.W,
    font=fonte_padrao,
    bg="#e0e0e0"
)
status_bar.pack(fill=tk.X, side=tk.BOTTOM)

janela.mainloop() # Programa entra no loop principal esperando interações do usuário.

# Fluxo de funcionamento do Validador de Testes Android com DeepSeek
"""
1. Abertura da interface gráfica
    - O programa inicializa a interface usando Tkinter.
    - Carrega o último diretório acessado (carregar_ultimo_dir), caso exista, para facilitar a seleção do arquivo de input.

2. Seleção do arquivo de input (.json)
    - Usuário clica no botão "Procurar".
    - Chama a função escolher_arquivo():
        - Abre a janela para selecionar arquivo (filedialog).
        - Usa carregar_ultimo_dir() para abrir na última pasta acessada.
        - Se o usuário escolher um arquivo:
            - Salva o caminho selecionado (input_path_var.set).
            - Atualiza o arquivo com o último diretório usando salvar_ultimo_dir().

3. Execução da análise
    - Usuário clica no botão "Executar Análise".
    - Chama a função executar_analise():
        - Obtém o caminho do arquivo de input selecionado.
        - Abre e lê o arquivo JSON de entrada.
        - Chama validar_estrutura_input(input_json):
            - Verifica se todos os campos obrigatórios estão presentes no arquivo de entrada.
            - Se faltar algum campo, interrompe o processo e exibe mensagem de erro.
        - Abre e lê o banco de dados técnico (software_db.json). Caso não abra, um popup aparece

4. Validação local da relação hardware/software/região
    - Chama validar_relacao_software_regiao(banco, hardware, software, regiao):
        - Verifica se o hardware, software e região informados são compatíveis no banco de dados.
        - Se não for válido, exibe aviso e interrompe a análise.

5. Checagem de cache
    - Gera um hash exclusivo para a combinação hardware, software e região (gerar_hash).
    - Verifica se já existe resultado em cache (cache_resultados.get(chave)):
        - Se existir, exibe o resultado armazenado na interface.
        - Se não existir:
            - Chama analisar_deepseek(banco, input_teste):
                - Monta o prompt com regras e dados do banco/input.
                - Envia para a API do DeepSeek usando requests.post().
                - Recebe o resultado da análise IA.
            - Salva o resultado no cache (cache_resultados.add).

6. Exibição do resultado
    - Exibe o resultado detalhado (PASS/FAIL por campo, valores esperados e recebidos) na área de resultados da interface.
    - Atualiza a barra de status para "Pronto".
"""
