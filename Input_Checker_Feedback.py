import tkinter as tk #
from tkinter import filedialog, messagebox, scrolledtext, ttk
import requests
import os
import hashlib
import json
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Carrega variáveis do .env
load_dotenv()
deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
FEEDBACK_FILE = "feedback_logs.json"

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
    return hashlib.md5(input_str.encode("utf-8")).hexdigest()

# Função para montar bloco reduzido do hardware
def montar_bloco_hardware(banco_json, nome_hardware):
    if nome_hardware in banco_json:
        hw = banco_json[nome_hardware]
        bloco = f"""
Hardware: {nome_hardware}
Softwares: {', '.join(hw['Softwares'])}
Regiões: {', '.join(hw['Regioes'] if isinstance(hw['Regioes'], list) else hw['Regioes'].keys())}
Androids disponíveis: {', '.join(hw['Androids_disponiveis'])}
Android mais recente: {hw['Android_mais_recente']}
Tecnologias suportadas: {json.dumps(hw['Tecnologias_suportadas'], indent=2)}
"""
        return bloco.strip()
    return "Hardware não encontrado."

def validar_estrutura_input(input_json):
    campos_obrigatorios = [
        "Hardware", "Software", "Regiao_Execucao",
        "Versao_Android", "WiFi", "NFC", "Bluetooth", "SIM", "Rede"
    ]
    for campo in campos_obrigatorios:
        if campo not in input_json:
            raise ValueError(f"Campo obrigatório faltando: {campo}")

def comparar_versoes(versao_input, versao_db):
    try:
        # Extrai números e pontos para comparação
        v_input = float(''.join(filter(lambda x: x.isdigit() or x == '.', versao_input)))
        v_db = float(''.join(filter(lambda x: x.isdigit() or x == '.', versao_db)))
        return v_input >= v_db
    except:
        return False

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
- HARDWARE: PASS/FAIL [valor]
- SOFTWARE: PASS/FAIL [valor]
- RELAÇÃO_SOFTWARE_REGIAO: PASS/FAIL [Software/Região] 
  → Se 'Regioes' for dicionário: FAIL se software não estiver na lista da região
  → Se 'Regioes' for lista: FAIL se região não existir
- VERSAO_ANDROID: PASS/FAIL [valor]
- WIFI: PASS/FAIL [valor]
- NFC: PASS/FAIL [valor]
- BLUETOOTH: PASS/FAIL [valor]
- SIM: PASS/FAIL [valor]
- REDE: PASS/FAIL [valor]

REGRAS RÍGIDAS:
1. Para RELAÇÃO_SOFTWARE_REGIAO:
   - Caso 1: Se 'Regioes' for um dicionário {região: [softwares]}, o software deve estar na lista da região especificada.
   - Caso 2: Se 'Regioes' for uma lista [regiões], a região do input deve existir na lista.
2. Para tecnologias (WiFi, NFC, etc.): comparação exata de valores entre aspas. Exemplo: se o valor do input for 2.4GHz e no banco tiver uma das opções como 2.4GHZ, considere como PASS.
3. Sempre mostre o valor esperado no banco em caso de FAIL."""
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


def enviar_feedback(resultado_original, feedback_usuario, tipo_feedback):
    headers = {
        "Authorization": f"Bearer {deepseek_api_key}",
        "Content-Type": "application/json"
    }
    
    # Mapeia o tipo de feedback para uma mensagem mais específica
    tipo_mensagem = {
        "correcao": "Correção de resultado incorreto",
        "melhoria": "Sugestão de melhoria na análise",
        "duvida": "Dúvida sobre o resultado",
        "outro": "Feedback geral"
    }.get(tipo_feedback, "Feedback geral")
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system",
                "content": f"Você está recebendo feedback sobre uma validação técnica ({tipo_mensagem}). Analise cuidadosamente e responda de forma concisa."
            },
            {
                "role": "user",
                "content": f"TIPO DE FEEDBACK: {tipo_mensagem}\n\nRESULTADO ORIGINAL:\n{resultado_original}\n\nFEEDBACK DO USUÁRIO:\n{feedback_usuario}\n\nPor favor, responda de forma concisa e útil."
            }
        ],
        "temperature": 0.3,
        "max_tokens": 300
    }

    try:
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        resposta = response.json()['choices'][0]['message']['content']
        return f"Feedback ({tipo_mensagem}) enviado com sucesso!\nResposta: {resposta}"
    except Exception as e:
        return f"Erro ao enviar feedback: {str(e)}"



def salvar_feedback(tipo, feedback, resultado_original, resposta_api):
    "Armazena feedback em um arquivo JSON"
    novo_registro = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tipo": tipo,
        "feedback": feedback,
        "resultado_original": resultado_original,
        "resposta_api": resposta_api
    }

    try:
        # Tenta carregar feedbacks existentes
        with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
            dados = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        dados = {"feedbacks": []}

    dados["feedbacks"].append(novo_registro)

    with open(FEEDBACK_FILE, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)






def executar_analise():
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
        messagebox.showwarning("Aviso", "Relação Software/Região inválida localmente!")
        return  # Interrompe a execução se a validação local falhar    

    nome_hw = input_json["Hardware"]
    if nome_hw not in banco:
        messagebox.showwarning("Aviso", f"Hardware '{nome_hw}' não encontrado no banco de dados.")
        return

    bloco_hw = montar_bloco_hardware(banco, nome_hw)
    entrada_hash = nome_hw + input_teste
    chave = gerar_hash(entrada_hash)

    resultado = cache_resultados.get(chave)
    if not resultado:
        resultado = analisar_deepseek(bloco_hw, input_teste)
        cache_resultados.add(chave, resultado)

    output_text.delete(1.0, tk.END)
    output_text.insert(tk.END, resultado)
    executar_analise.ultimo_resultado = resultado

def escolher_arquivo():
    caminho = filedialog.askopenfilename(
        title="Selecione o arquivo de input",
        filetypes=[("Arquivos JSON", "*.json")],
        initialdir=os.getcwd()
    )
    if caminho:
        input_path_var.set(caminho)


# Interface Tkinter
janela = tk.Tk()
janela.title("Validador de Testes Android com DeepSeek - v2.1")
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

# Frame de feedback
frame_feedback = tk.Frame(janela, bg="#f0f0f0", padx=10, pady=5)
frame_feedback.pack(fill=tk.X)

# Tipo de feedback
tk.Label(
    frame_feedback,
    text="Tipo:",
    font=fonte_padrao,
    bg="#f0f0f0"
).pack(side=tk.LEFT)

feedback_type_var = tk.StringVar(value="correcao")
feedback_types = ttk.Combobox(
    frame_feedback,
    textvariable=feedback_type_var,
    values=["correcao", "melhoria", "duvida", "outro"],
    state="readonly",
    width=12,
    font=fonte_padrao
)
feedback_types.pack(side=tk.LEFT, padx=5)

# Campo de feedback
tk.Label(
    frame_feedback,
    text="Feedback:",
    font=fonte_padrao,
    bg="#f0f0f0"
).pack(side=tk.LEFT)

feedback_entry = tk.Entry(frame_feedback, width=50, font=fonte_padrao)
feedback_entry.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

def enviar_feedback_handler():
    feedback = feedback_entry.get()
    tipo_feedback = feedback_type_var.get()
    
    if not feedback:
        messagebox.showwarning("Aviso", "Por favor, insira seu feedback.")
        return
        
    if not hasattr(executar_analise, 'ultimo_resultado'):
        messagebox.showwarning("Aviso", "Execute uma análise primeiro antes de enviar feedback.")
        return
        
    # Envia para a API e armazena localmente
    resposta_api = enviar_feedback(executar_analise.ultimo_resultado, feedback, tipo_feedback)
    salvar_feedback(
        tipo=tipo_feedback,
        feedback=feedback,
        resultado_original=executar_analise.ultimo_resultado,
        resposta_api=resposta_api
    )
    
    messagebox.showinfo("Feedback", resposta_api)
    feedback_entry.delete(0, tk.END)

tk.Button(
    frame_feedback,
    text="Enviar",
    command=enviar_feedback_handler,
    bg="#FF9800",
    fg="white",
    font=fonte_padrao,
    width=8
).pack(side=tk.LEFT, padx=5)

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