import os
import json
from groq import Groq
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import nltk
from nltk.corpus import stopwords
import re

API_KEY = "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"
#API_KEY = "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"
#API_KEY = "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"
#API_KEY = "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"

client = Groq(api_key=API_KEY)

try:
    nltk.data.find("corpora/stopwords")
except LookupError:
    nltk.download("stopwords")


def clean_text(text):
    if not text:
        return ""
    text = str(text).lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def calculate_compatibility(resume_text, job_description):
    resume_clean = clean_text(resume_text)
    job_clean = clean_text(job_description)

    if not resume_clean or not job_clean:
        return 0.0

    pt_stopwords = stopwords.words("portuguese")
    vectorizer = TfidfVectorizer(stop_words=pt_stopwords, ngram_range=(1, 1))

    try:
        vectors = vectorizer.fit_transform([resume_clean, job_clean])
        similarity_matrix = cosine_similarity(vectors)
        match_score = similarity_matrix[0][1] * 100
        return round(match_score, 1)
    except Exception:
        return 0.0


def clean_job_description_with_ai(job_description: str) -> str:
    if not job_description:
        return job_description

    prompt = f"""
Você está ajudando a preparar o texto de uma vaga para ser comparado com um currículo.

TEXTO ORIGINAL DA VAGA (como veio da plataforma):

\"\"\"{job_description}\"\"\"

TAREFA:
- Reescreva a vaga mantendo APENAS:
  - responsabilidades do cargo;
  - requisitos obrigatórios e desejáveis;
  - habilidades técnicas e comportamentais importantes para seleção.

REMOVA:
- descrição institucional da empresa;
- marketing da vaga;
- informações de candidatura (botões, "candidate-se", "mostrar mais" etc.);
- benefícios e detalhes administrativos que não ajudam a avaliar o fit do currículo.

Responda APENAS com o texto limpo em português, sem comentários extras.
    """

    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.4,
        )
        return chat_completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"Erro ao limpar descrição da vaga com IA: {e}")
        return job_description


def extract_structured_requirements(job_description: str) -> dict:
    base = {
        "role_summary": "",
        "seniority": "",
        "area": [],
        "responsibilities": [],
        "requirements_must_have": [],
        "requirements_nice_to_have": [],
        "soft_skills": [],
        "tools_and_techs": [],
        "languages": [],
    }

    if not job_description:
        return base

    prompt = f"""
Você é um especialista em Recrutamento & Seleção que estrutura vagas para análise de currículo.

Abaixo está o TEXTO DA VAGA (como veio da plataforma, já parcialmente limpo):

\"\"\"{job_description}\"\"\"

TAREFA:
Transforme essa descrição em um RESUMO ESTRUTURADO, pensando em matching com currículos.

IDENTIFIQUE E DEVOLVA (em JSON):

- role_summary: (string) resumo curto da vaga (ex: "Estágio em Desenvolvimento RPA com foco em UiPath").
- seniority: (string) nível da vaga (ex: "estagio", "junior", "pleno", "senior", "trainee", "coordenador", etc.).
- area: (lista de strings) áreas ou temas principais (ex: ["RPA", "Automação de Processos", "Tecnologia"]).

- responsibilities: (lista de strings) principais responsabilidades do cargo, em frases curtas.

- requirements_must_have: (lista de strings) requisitos OBRIGATÓRIOS (formação, experiência, tecnologias, idiomas).
- requirements_nice_to_have: (lista de strings) requisitos DESEJÁVEIS / diferenciais.

- soft_skills: (lista de strings) competências comportamentais (trabalho em equipe, organização, comunicação, etc.).
- tools_and_techs: (lista de strings) ferramentas e tecnologias citadas (linguagens, frameworks, plataformas, etc.).

- languages: (lista de objetos) idiomas exigidos ou valorizados, no formato:
  [
    {{"language": "Inglês", "level": "intermediario"}},
    {{"language": "Espanhol", "level": "basico"}}
  ]
  Se não houver idiomas explícitos, use lista vazia.

INSTRUÇÕES:
- Use português do Brasil.
- Não invente requisitos que não existam na vaga.
- Se algo for inferido, seja conservador (só inclua se fizer muito sentido).
- Mantenha as frases das listas em formato que possa ser exibido direto para o usuário.

Responda APENAS com o JSON (sem comentários, sem texto antes ou depois).
    """

    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        content = chat_completion.choices[0].message.content
        content = content.replace("```json", "").replace("```", "").strip()
        data = json.loads(content)
    except Exception as e:
        print(f"Erro ao estruturar requisitos da vaga com IA: {e}")
        return base

    def _ensure_list(val):
        if val is None:
            return []
        if isinstance(val, list):
            return val
        return [str(val)]

    structured = {
        "role_summary": data.get("role_summary") or "",
        "seniority": data.get("seniority") or "",
        "area": _ensure_list(data.get("area")),
        "responsibilities": _ensure_list(data.get("responsibilities")),
        "requirements_must_have": _ensure_list(data.get("requirements_must_have")),
        "requirements_nice_to_have": _ensure_list(data.get("requirements_nice_to_have")),
        "soft_skills": _ensure_list(data.get("soft_skills")),
        "tools_and_techs": _ensure_list(data.get("tools_and_techs")),
        "languages": data.get("languages") or [],
    }

    # Correção do bug de normalização na lista de idiomas
    normalized_langs = []
    for item in structured["languages"]:
        if isinstance(item, dict):
            normalized_langs.append(
                {
                    "language": item.get("language") or item.get("idioma") or "",
                    "level": item.get("level") or item.get("nivel") or "",
                }
            )
        else:
            normalized_langs.append({"language": str(item), "level": ""})

    structured["languages"] = normalized_langs

    return structured


def generate_smart_feedback(resume_text, job_description, job_title=None, company=None):
    job_context_lines = []
    if job_title:
        job_context_lines.append(f"TÍTULO DA VAGA: {job_title}")
    if company:
        job_context_lines.append(f"EMPRESA: {company}")
    job_context_str = "\n".join(job_context_lines) if job_context_lines else "Não informado."
    structured_requirements = {}
    try:
        if job_description:
            structured_requirements = extract_structured_requirements(job_description)
    except Exception as e:
        print(f"Erro extract_structured_requirements dentro de generate_smart_feedback: {e}")
        structured_requirements = {}

    prompt = f"""
    Aja como um Recrutador Brasileiro Sênior e pragmático. Nada de "corporate speak".
    Analise este CURRÍCULO para esta VAGA específica.

    CONTEXTO DA VAGA:
    {job_context_str}

    DESCRIÇÃO COMPLETA DA VAGA:
    {job_description}

    REQUISITOS INTERPRETADOS (JSON estruturado da vaga - must_have, nice_to_have, soft_skills, tecnologias, idiomas):
    {json.dumps(structured_requirements, ensure_ascii=False)}

    CURRÍCULO:
    {resume_text}

    --- DIRETRIZES DE TOM ---
    1. Fale português natural do Brasil.
    2. Evite palavras vazias como "sinergia", "holístico", "paradigma".
    3. Seja útil. Se o candidato não tem chance, diga o que falta de verdade.
    4. Considere que o candidato quer se preparar para ser TOP 1 na triagem.

    --- SCORES (DIVIDA EM 3 DIMENSÕES) ---
    Calcule 4 scores separados (0 a 100):
      - score_tech: aderência TÉCNICA (hard skills, ferramentas, sistemas, tecnologias).
      - score_experience: aderência de RESPONSABILIDADES / SENIORIDADE (tarefas que já fez vs o que a vaga pede).
      - score_context: FIT DE CONTEXTO (modelo de trabalho, setor, idioma, localização, disponibilidade, tipo de contrato).
      - score: visão GERAL considerando os três (não precisa ser média exata, mas coerente com eles).

    --- MODO RECRUTADOR (VISÃO RÁPIDA) ---
    Gere também uma visão de recrutador humano:
      - summary: o que você pensaria nos primeiros 10 segundos olhando esse currículo para essa vaga.
      - red_flags: lista de possíveis motivos reais de reprovação na triagem.
      - final_checklist: lista curta de itens para o candidato conferir antes de enviar.

    Responda APENAS o JSON (sem comentários, sem texto fora do JSON):
    {{
        "score": (inteiro 0-100, honesto),
        "score_tech": (inteiro 0-100),
        "score_experience": (inteiro 0-100),
        "score_context": (inteiro 0-100),
        "verdict_title": (Manchete curta, ex: "Bom perfil, mas falta gestão"),
        "verdict_text": (Resumo de 2 linhas, direto ao ponto, citando a vaga e a empresa se fizer sentido),
        "strengths": [(Lista de 3 pontos reais que conectam com a vaga)],
        "missing_skills": [(Lista de hard skills que realmente faltam)],
        "ats_keywords": [(Lista de 5 a 8 palavras exatas da vaga que faltam no CV)],
        "golden_tip": (Uma dica prática. Nada de "seja proativo". Diga algo como "Aprenda a ferramenta X" ou "Destaque o projeto Y"),
        "recruiter_view": {{
            "summary": (Frase ou parágrafo curto sobre a impressão inicial),
            "red_flags": [(Lista de possíveis motivos reais de reprovação)],
            "final_checklist": [(Lista de 3 a 6 itens para conferir antes de enviar)]
        }}
    }}
    """

    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        content = chat_completion.choices[0].message.content
        content = content.replace("```json", "").replace("```", "").strip()
        data = json.loads(content)
        score = int(data.get("score", 0) or 0)
        data["score"] = score
        data["score_tech"] = int(data.get("score_tech", score) or score)
        data["score_experience"] = int(data.get("score_experience", score) or score)
        data["score_context"] = int(data.get("score_context", score) or score)
        data["strengths"] = data.get("strengths") or []
        data["missing_skills"] = data.get("missing_skills") or []
        data["ats_keywords"] = data.get("ats_keywords") or []
        data["verdict_title"] = data.get("verdict_title") or "Resumo da análise"
        data["verdict_text"] = data.get("verdict_text") or ""
        data["golden_tip"] = data.get("golden_tip") or ""
        rv = data.get("recruiter_view") or {}
        data["recruiter_view"] = {
            "summary": rv.get("summary") or "",
            "red_flags": rv.get("red_flags") or [],
            "final_checklist": rv.get("final_checklist") or [],
        }

        return data
    except Exception as e:
        print(f"Erro Feedback: {e}")
        err_msg = str(e)

        lowered = err_msg.lower()
        is_rate_limit = (
            "rate limit" in lowered
            or "rate_limit_exceeded" in lowered
            or "429" in lowered
        )

        if is_rate_limit:
            error_type = "rate_limit"
            user_message = (
                "Limite diário de uso da IA para otimização de texto atingido. "
                "Tente novamente em alguns minutos."
            )
        else:
            error_type = "generic"
            user_message = (
                "Ocorreu um erro ao tentar gerar a análise com IA. "
                "Tente novamente mais tarde..."
            )

        return {
            "error": True,
            "error_type": error_type,
            "error_message": user_message,
            "raw_error": err_msg,
            "score": 0,
            "score_tech": 0,
            "score_experience": 0,
            "score_context": 0,
            "verdict_title": "Erro na Análise",
            "verdict_text": user_message,
            "strengths": [],
            "missing_skills": [],
            "ats_keywords": [],
            "golden_tip": "",
            "recruiter_view": {
                "summary": "",
                "red_flags": [],
                "final_checklist": [],
            },
        }


def audit_resume_quality(resume_text, job_description):
    word_count = len(resume_text.split())
    # Regex email e telefone
    has_email = bool(re.search(r"[\w\.-]+@[\w\.-]+", resume_text))
    has_phone = bool(
        re.search(r"\(?\d{2}\)?\s?\d{4,5}-?\d{4}", resume_text)
        or re.search(r"\d{8,11}", resume_text)
    )

    python_metrics = f"""
    - Contagem de palavras: {word_count} (Ideal: entre 250 e 700 para ser sucinto).
    - Email detectado via regex: {has_email}
    - Telefone detectado via regex: {has_phone}
    """

    prompt = f"""
    Aja como um Auditor de Qualidade de Currículos rigoroso.
    Analise o CURRÍCULO com base nas 7 REGRAS DE OURO do mercado de trabalho.
    
    DADOS TÉCNICOS (Já calculados, use-os):
    {python_metrics}
    
    VAGA: {job_description}
    CURRÍCULO: {resume_text}
    
    Avalie cada item abaixo e retorne "status" (boolean: true=aprovado, false=atenção) e "feedback" (explicação curta e direta do que corrigir).
    
    ITENS A AVALIAR:
    1. **Sucinto:** O texto é objetivo? (Baseado na contagem de palavras). Se tiver mais de 900 palavras, reprove.
    2. **Adaptação:** O currículo parece genérico ou usa termos da VAGA?
    3. **Conquistas:** Ele lista apenas tarefas ("Fiz X") ou resultados/conquistas ("Aumentei X")?
    4. **Certificados:** Existem certificados, cursos extras ou workshops citados?
    5. **Contato:** (Use o dado técnico). Estão fáceis de achar?
    6. **Idiomas:** Menciona idiomas (mesmo que seja nativo ou inglês básico)?
    7. **Especificidade:** As datas, nomes de empresas e descrições de cursos estão claros ou vagos?
    
    SAÍDA OBRIGATÓRIA (JSON Puro):
    {{
        "brevity": {{ "status": true/false, "feedback": "..." }},
        "customization": {{ "status": true/false, "feedback": "..." }},
        "achievements": {{ "status": true/false, "feedback": "..." }},
        "certificates": {{ "status": true/false, "feedback": "..." }},
        "contact": {{ "status": true/false, "feedback": "..." }},
        "languages": {{ "status": true/false, "feedback": "..." }},
        "specificity": {{ "status": true/false, "feedback": "..." }}
    }}
    """

    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        content = (
            chat_completion.choices[0]
            .message.content.replace("```json", "")
            .replace("```", "")
            .strip()
        )
        return json.loads(content)
    except Exception as e:
        print(f"Erro Auditoria: {e}")
        return None


def generate_optimized_experience(resume_text, job_description, job_title=None, company=None):
    job_context_lines = []
    if job_title:
        job_context_lines.append(f"TÍTULO DA VAGA: {job_title}")
    if company:
        job_context_lines.append(f"EMPRESA: {company}")
    job_context_str = "\n".join(job_context_lines) if job_context_lines else "Não informado."

    prompt = f"""
    Aja como um Consultor de Carreira que escreve currículos para PESSOAS REAIS, não para robôs.
    
    CONTEXTO:
    O candidato tem o currículo abaixo e quer a VAGA ALVO.
    
    VAGA ALVO (DADOS ESTRUTURADOS):
    {job_context_str}
    
    DESCRIÇÃO COMPLETA DA VAGA:
    {job_description}
    
    CURRÍCULO ATUAL:
    {resume_text}
    
    --- MISSÃO: EVITAR O "SOM DE IA" ---
    1. **Proibido Inventar Porcentagens:** Não use "[X]%" ou "R$ [Y]" a menos que seja óbvio (vendas).
       - Em vez de "Aumentei a eficiência em 30%", escreva "Eliminei processos manuais e reduzi erros de digitação".
       - Em vez de "Otimizei o fluxo", escreva "Organizei a rotina da equipe para evitar atrasos".
    
    2. **Proibido Vocabulário Rebuscado (Lista Negra):**
       - NÃO USE: "Meticuloso", "Alavancar", "Impulsionar", "Sinergia", "Mitigar", "Crucial", "Vasto conhecimento", "Exímio".
       - USE: "Resolvi", "Criei", "Organizei", "Liderei", "Melhorei", "Garanti".
    
    3. **Inteligência de Transição (O Pulo do Gato):**
       - Se a vaga for de área diferente do currículo (Ex: Dev aplicando para RH), **ESQUEÇA O TÉCNICO.**
       - Traduza a experiência: "Codificar em Java" vira "Resolver problemas complexos com lógica". "Gerenciar tickets no Jira" vira "Organizar demandas e prazos da equipe".
       - Foque no comportamento: Organização, Comunicação, Pontualidade e Resolução de Problemas.

    --- GERE 3 VERSÕES ---    
    VERSÃO 1: STAR (Natural e Narrativa)
    - Conte uma mini-história: "Havia um problema X, eu fiz Y, e o resultado foi que paramos de ter reclamações/atrasos."
    
    VERSÃO 2: ATS (Palavras-Chave da Vaga)
    - Use os termos exatos da VAGA, mas em frases que um humano falaria.
    
    VERSÃO 3: EXECUTIVA (Ação e Resultado)
    - Frases curtas começando com verbos.
    - Foco no benefício real (tempo ganho, dinheiro economizado, cliente feliz).
    
    SAÍDA OBRIGATÓRIA (JSON Puro):
    {{
        "original_summary": "Resumo de 1 linha da experiência original identificada.",
        "star_version": "Texto formato STAR natural.",
        "ats_version": "Texto com palavras-chave, mas fluido.",
        "executive_version": "Lista de bullet points diretos (pode ser string ou array de strings)."
    }}
    """

    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.6,
            response_format={"type": "json_object"},
        )
        content = chat_completion.choices[0].message.content
        content = content.replace("```json", "").replace("```", "").strip()
        return json.loads(content)
    except Exception as e:
        print(f"Erro Otimização: {e}")
        err_msg = str(e)
        lowered = err_msg.lower()

        is_rate_limit = (
            "rate limit" in lowered
            or "rate_limit_exceeded" in lowered
            or "429" in lowered
        )

        if is_rate_limit:
            error_type = "rate_limit"
            user_message = (
                "Limite diário de uso da IA para otimização de texto atingido. "
                "A análise principal foi gerada normalmente, mas não foi possível criar as versões reescritas agora."
            )
        else:
            error_type = "generic"
            user_message = (
                "Não foi possível gerar as versões reescritas do currículo com a IA no momento. "
                "A análise principal foi gerada normalmente."
            )
        return {
            "error": True,
            "error_type": error_type,
            "error_message": user_message,
            "raw_error": err_msg,
            "original_summary": "",
            "star_version": "",
            "ats_version": "",
            "executive_version": [],
        }