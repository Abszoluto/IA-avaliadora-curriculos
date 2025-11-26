# Analisador de Currículos com IA (ResumeIA)
Aplicação web em Flask para avaliar a compatibilidade entre um currículo e uma vaga específica.  
O foco é bem prático: ajudar a pessoa candidata a entender se faz sentido aplicar para a vaga, o que está faltando no currículo e como melhorar o texto.

---
## O que o sistema faz
- Cadastro e login de usuários (cada pessoa tem seu próprio histórico).
- Upload de currículo em PDF/DOCX.
- Dois modos de entrada da vaga:
  - **Automático**: o usuário informa apenas o link da vaga no LinkedIn.
    - O sistema faz scraping da página.
    - Mostra um modal de confirmação com: título da vaga, empresa e descrição extraída.
    - Só depois da confirmação o processamento começa de fato.
  - **Manual**: o usuário cola ou digita o texto da vaga.
- Análise de compatibilidade usando:
  - Similaridade TF-IDF entre currículo e vaga.
  - Modelo de linguagem (Groq) para:
    - interpretar a vaga de forma estruturada (must-have, nice-to-have, soft skills, tecnologias, idiomas);
    - gerar um parecer “modo recrutador”;
    - montar um plano de ação;
    - sugerir melhorias de texto para o currículo.
  - Auditoria de qualidade do currículo (tamanho, contatos, idiomas, conquistas, especificidade, etc.).
- Modal de resultados com abas:
  - **Auditoria e correções**
  - **Palavras-chave**
  - **Plano de ação**
  - **Modo recrutador**
  - **Entrevista**
- Dashboard com histórico das análises:
  - título da vaga,
  - score de compatibilidade,
  - status,
  - link original da vaga.


---
# Como executar o projeto
- Instalação de dependências:
pip install -r requirements.txt

- Execução do projeto:
python app.py

- Acesso ao sistema através do link:
http://127.0.0.1:5000/

## Principais tecnologias
Back-end:
- Python 3
- Flask
- SQLite (`sqlite3`)
- Requests + BeautifulSoup para scraping de vagas do LinkedIn
- Groq API para geração de texto (modelo `llama-3.3-70b-versatile`)
- scikit-learn (TF-IDF, cosine similarity)
- NLTK (stopwords em português)
- Pandas (ajustes pontuais de dados)

Front-end:
- HTML
- CSS
- JavaScript vanilla para comportamento do formulário, modais, abas e loading
---

## Estrutura de pastas (resumo)
```text
.
├── app.py              # Aplicação Flask, rotas e integração geral
├── ai_engine.py        # Funções de IA (Groq + TF-IDF + auditoria)
├── db_manager.py       # Acesso ao SQLite (users + history)
├── templates/
│   ├── base.html       # Layout base, header, loading, flashes
│   ├── index.html      # Tela principal (upload + análise)
│   └── dashboard.html  # Histórico de análises
├── static/
│   └── styles.css      # Estilos da interface
└── users.db            # Banco SQLite (gerado em tempo de execução)
```
