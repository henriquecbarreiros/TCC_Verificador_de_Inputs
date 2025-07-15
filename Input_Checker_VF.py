import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import requests
import os
import hashlib
import json
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Carrega variáveis do .env
load_dotenv()
deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
LAST_DIR_FILE = "last_dir.json"

def carregar_ultimo_dir():
    try:
        with open(LAST_DIR_FILE, "r") as f:
            data = json.load(f)
            if os.path.isdir(data.get("last_dir", "")):  # Verifica se a pasta ainda existe
                return data["last_dir"]
            return os.getcwd()
    except Exception as e:
        print(f"Erro ao carregar último diretório: {e}")
        return os.getcwd()

def salvar_ultimo_dir(caminho):
    """Salva o último diretório acessado."""
    with open(LAST_DIR_FILE, "w") as f:
        json.dump({"last_dir": os.path.dirname(caminho)}, f)

# Cache de resultados com expiração
class ResultCache:
    def __init__(self, max_size=100, ttl_hours=24):
        self.cache = {}
        self.max_size = max_size
        self.ttl = timedelta(hours=ttl_hours)
    
    def add(self, key, value):
        if len(self.cache) >= self.max_size:
            self.cleanup()
        self.cache[key] = {
            'value': value,
            'timestamp': datetime.now()
        }
    
    def get(self, key):
        item = self.cache.get(key)
        if item and (datetime.now() - item['timestamp']) < self.ttl:
            return item['value']
        return None
    
    def cleanup(self):
        oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k]['timestamp'])
        del self.cache[oldest_key]

cache_resultados = ResultCache()

# Gera um hash único baseado no input
def gerar_hash(input_str):
    return hashlib.sha256(input_str.encode()).hexdigest()

def validar_estrutura_input(input_json):
    campos_obrigatorios = [
        "Hardware", "Software", "Regiao_Execucao",
        "Versao_Android", "WiFi", "NFC", "Bluetooth", "SIM", "Rede"
    ]
    for campo in campos_obrigatorios:
        if campo not in input_json:
            raise ValueError(f"Campo obrigatório faltando: {campo}")

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

# Função para análise via DeepSeek
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
2. Seja rigoroso nas comparações
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

def escolher_arquivo():
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

janela.mainloop()