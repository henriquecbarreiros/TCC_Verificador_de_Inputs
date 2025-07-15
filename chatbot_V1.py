import tkinter as tk
from tkinter import scrolledtext, messagebox, simpledialog
import json
import requests
from datetime import datetime
import os
from dotenv import load_dotenv

# Configurações
load_dotenv()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
BANCO_DADOS = "software_db.json"

class DeepSeekChatbot:
    def __init__(self, master):
        self.master = master
        master.title("Chatbot Técnico com DeepSeek")
        master.geometry("900x700")
        
        # Carrega banco de dados
        self.banco = self.carregar_banco_dados()
        
        # Interface
        self.criar_interface()
        self.adicionar_mensagem("Chatbot", 
            "Olá! Sou um assistente técnico integrado com DeepSeek.\n"
            "Você pode perguntar sobre:\n"
            "- Compatibilidade entre hardwares/softwares\n"
            "- Especificações técnicas\n"
            "- Análise de configurações\n\n"
            "Exemplo: 'Analise a compatibilidade do Hardware_A com Android 14'",
            "bot"
        )
    
    def criar_interface(self):
        """Configura os elementos visuais"""
        # Área de conversa
        self.conversa = scrolledtext.ScrolledText(
            self.master,
            wrap=tk.WORD,
            width=100,
            height=25,
            font=("Consolas", 10),
            state='disabled'
        )
        self.conversa.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        
        # Tags para formatação
        self.conversa.tag_config('bot', foreground='#0066CC')
        self.conversa.tag_config('user', foreground='#009933')
        self.conversa.tag_config('error', foreground='red')
        
        # Frame de entrada
        frame_entrada = tk.Frame(self.master)
        frame_entrada.pack(fill=tk.X, padx=10, pady=5)
        
        self.entrada = tk.Entry(
            frame_entrada,
            font=("Arial", 12),
            width=80
        )
        self.entrada.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entrada.bind("<Return>", self.enviar_pergunta)
        
        tk.Button(
            frame_entrada,
            text="Enviar",
            command=self.enviar_pergunta,
            bg="#4CAF50",
            fg="white"
        ).pack(side=tk.LEFT, padx=5)
    
    def carregar_banco_dados(self):
        try:
            with open(BANCO_DADOS, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            self.adicionar_mensagem("Sistema", f"Erro ao carregar banco de dados: {str(e)}", "error")
            return {}

    def enviar_pergunta(self, event=None):
        pergunta = self.entrada.get().strip()
        if not pergunta:
            return
            
        self.adicionar_mensagem("Você", pergunta, "user")
        self.entrada.delete(0, tk.END)
        
        # Prepara contexto para a API
        contexto = {
            "banco_dados": self.banco,
            "pergunta_usuario": pergunta,
            "instrucoes": (
                "Você é um especialista técnico. Analise a pergunta com base nos dados fornecidos. "
                "Seja conciso e técnico. Formate respostas com marcadores quando necessário."
            )
        }
        
        resposta = self.consultar_deepseek(contexto)
        self.adicionar_mensagem("Assistente", resposta, "bot")

    def consultar_deepseek(self, contexto):
        """Consulta a API do DeepSeek com contexto estruturado"""
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {
                    "role": "system",
                    "content": contexto["instrucoes"]
                },
                {
                    "role": "user",
                    "content": (
                        f"Banco de Dados Técnicos (JSON):\n{json.dumps(contexto['banco_dados'], indent=2)}\n\n"
                        f"Pergunta do Usuário:\n{contexto['pergunta_usuario']}\n\n"
                        "Instruções:\n"
                        "1. Analise os dados técnicos\n"
                        "2. Responda com precisão\n"
                        "3. Destaque valores relevantes"
                    )
                }
            ],
            "temperature": 0.3,
            "max_tokens": 1000
        }
        
        try:
            response = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"⚠ Erro na consulta à API: {str(e)}"

    def adicionar_mensagem(self, remetente, mensagem, tag=None):
        self.conversa.config(state='normal')
        agora = datetime.now().strftime("%H:%M:%S")
        self.conversa.insert(tk.END, f"[{agora}] {remetente}:\n", tag)
        self.conversa.insert(tk.END, f"{mensagem}\n\n")
        self.conversa.config(state='disabled')
        self.conversa.see(tk.END)

# Inicia a aplicação
if __name__ == "__main__":
    root = tk.Tk()
    app = DeepSeekChatbot(root)
    root.mainloop()