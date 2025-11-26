from flask import (Flask,render_template,request,redirect,url_for,session,flash,jsonify,)
import os
import json
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import typing
import requests
from bs4 import BeautifulSoup
from modules import db_manager, parser, ai_engine

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "mude-essa-chave-em-producao")

# Inicialzação do banco de dados
db_manager.init_db()


def get_logged_user():
    username = session.get("username")
    logged_in = session.get("logged_in", False)

    if not username or not logged_in:
        return None, False

    #Confere se o user existe no banco
    try:
        if not db_manager.user_exists(username):
            session.clear()
            return None, False
    except Exception as e:
        print(f"[auth] erro ao validar usuário '{username}' no banco: {e}")
        session.clear()
        return None, False

    return username, True

# Remove linhas contendo lixo
def clean_job_description_for_matching(text: str) -> str:
    if not text:
        return text

    lines = [l.strip() for l in text.splitlines()]
    noise_starts = (
        "Mostrar mais",
        "Show more",
        "Show less",
        "Ver mais",
        "Veja mais",
        "Saiba mais",
        "Candidatar-se",
        "Candidate-se",
        "Apply",
        "Apply now",
        "Turn on job alerts",
        "Ativar alerta de vagas",
        "Veja quem você conhece",
        "Descubra quem",
        "Número de candidatos",
        "há ",
        "Há ",
        "Nível de experiência",
        "Tipo de emprego",
        "Função",
        "Setor",
        "Localização da vaga",
        "Conheça a empresa",
        "Sobre a empresa",
        "Sobre nós",
        "Informações adicionais",
        "Informações da vaga",
    )

    cleaned_lines = []
    for line in lines:
        if not line:
            continue
        
        if any(line.startswith(p) for p in noise_starts):
            continue
        cleaned_lines.append(line)

    cleaned_text = "\n".join(cleaned_lines)
    #Tira múltiplas quebras de linha
    cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text).strip()

    try:
        cleaned_text_ai = ai_engine.clean_job_description_with_ai(cleaned_text)
        if cleaned_text_ai:
            return cleaned_text_ai.strip()
    except Exception as e:
        print(f"[WARN] Falha na limpeza com IA, usando heurística apenas: {e}")

    return cleaned_text


def try_autofill_from_job_link(job_link, job_title, company, job_description):
    if not job_link or not requests or not BeautifulSoup:
        return job_title, company, job_description

    if "linkedin.com" not in job_link:
        return job_title, company, job_description

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0 Safari/537.36"
            )
        }
        resp = requests.get(job_link, headers=headers, timeout=10)
        if resp.status_code != 200:
            print(f"[scraper] status diferente de 200 ao buscar vaga: {resp.status_code}")
            return job_title, company, job_description

        html = resp.text
        soup = BeautifulSoup(html, "html.parser")

        # Titulo da vaga
        h1 = soup.select_one("h1.top-card-layout__title")
        if h1 and not job_title:
            jt = " ".join(h1.get_text(separator=" ", strip=True).split())
            job_title = jt[:120]

        #Empresa
        org = soup.select_one("a.topcard__org-name-link, span.topcard__flavor")
        if org and not company:
            company = " ".join(org.get_text(separator=" ", strip=True).split())

        #Descrição da vaga
        section = soup.select_one("section.core-section-container.description")
        if section and not job_description:
            desc_div = section.select_one("div.description__text") or section
            raw = desc_div.get_text(separator="\n")
            lines = [line.strip() for line in raw.splitlines()]
            lines = [line for line in lines if line]
            job_description = "\n".join(lines)

        return job_title, company, job_description
    except Exception as e:
        print(f"[scraper] erro ao buscar descrição da vaga: {e}")
        return job_title, company, job_description


@app.route("/", methods=["GET"])
def index():
    username, logged_in = get_logged_user()
    return render_template(
        "index.html",
        logged_in=logged_in,
        username=username,
        analysis=None,
        rewritten=None,
        audit=None,
        job_title="",
        job_description="",
        company="",
        job_link="",
        job_mode="auto",
    )

@app.route("/preview_job", methods=["POST"])
def preview_job():
    username, logged_in = get_logged_user()
    if not logged_in:
        return jsonify(
            {
                "success": False,
                "message": "Você precisa estar logado para analisar uma vaga.",
            }
        ), 401

    data = request.get_json(silent=True) or {}
    job_link = (data.get("job_link") or "").strip()

    if not job_link:
        return jsonify({"success": False, "message": "Nenhum link de vaga foi informado."}), 400
    job_title = ""
    company = ""
    job_description = ""
    job_title, company, job_description = try_autofill_from_job_link(job_link, job_title, company, job_description)

    if job_description:
        job_description = clean_job_description_for_matching(job_description)

    if not (job_title or company or job_description):
        return jsonify(
            {
                "success": False,
                "message": (
                    "Não consegui extrair os dados desta vaga automaticamente. "
                    "Verifique se o link é de uma vaga pública do LinkedIn "
                    "ou preencha as informações no modo manual."
                ),
            }
        )

    return jsonify(
        {
            "success": True,
            "job_title": job_title,
            "company": company,
            "job_description": job_description,
        }
    )

@app.route("/analyze", methods=["POST"])
def analyze():
    username, logged_in = get_logged_user()
    if not logged_in:
        flash(
            "Para analisar a compatibilidade, entre ou crie uma conta primeiro.",
            "warning",
        )
        return redirect(url_for("index"))

    uploaded_file = request.files.get("cv_file")
    job_description = request.form.get("job_description", "").strip()
    job_title = request.form.get("job_title", "").strip()
    company = request.form.get("company", "").strip()
    job_link = (request.form.get("job_link") or "").strip()
    job_mode = request.form.get("job_mode", "auto")
    if not uploaded_file:
        flash("Envie o arquivo de currículo (PDF ou DOCX) para continuar.", "warning")
        return redirect(url_for("index"))

    if job_mode == "auto":
        # Modo automático
        if not job_link:
            flash(
                "Informe o link da vaga para extrair os dados automaticamente ou troque para o modo de preenchimento manual.",
                "warning",
            )
            return redirect(url_for("index"))

        # Se o link for preenchido, ignora a descrição
        job_description = ""
        job_title, company, job_description = try_autofill_from_job_link(job_link, job_title, company, job_description)
        if job_description:
            job_description = clean_job_description_for_matching(job_description)

        print("\nWeb scrapping (descrição):")
        print(job_description or "")
        print("----------------------------------\n")

        if not job_description:
            flash(
                "Não consegui extrair a descrição desta vaga automaticamente. Cole a descrição manualmente ou verifique se o link é de uma vaga pública do LinkedIn.",
                "warning",
            )
            return redirect(url_for("index"))

    else:
        # Modo manual
        if not job_description:
            flash(
                "Cole a descrição da vaga no campo apropriado ou troque para o modo de extração automática pelo link.",
                "warning",
            )
            return redirect(url_for("index"))

        job_description = clean_job_description_for_matching(job_description)
    if not job_title and job_description:
        first_line = job_description.splitlines()[0].strip()
        job_title = first_line[:120] if first_line else "Vaga sem título"

    #Extrair texto do pdf
    resume_text = parser.extract_text_from_file(uploaded_file)

    #Calculo de compatibilidade
    tfidf = ai_engine.calculate_compatibility(resume_text, job_description)
    audit_data = ai_engine.audit_resume_quality(resume_text, job_description)

    #Feedback
    ai_data = ai_engine.generate_smart_feedback(
        resume_text,
        job_description,
        job_title=job_title,
        company=company,
    )

    #Correção bug em falha da IA
    if ai_data.get("error"):
        flash(
            ai_data.get("error_message")
            or "Não foi possível gerar a análise com IA no momento. Tente novamente em alguns minutos.",
            "danger",
        )
        return redirect(url_for("index"))

    ai_data["tfidf"] = int(tfidf) if tfidf is not None else 0
    score = ai_data.get("score") or 0
    ai_data.setdefault("missing_skills", [])
    ai_data.setdefault("verdict_title", "Resumo da análise")
    ai_data.setdefault("verdict_text", "")
    ai_data.setdefault("score_tech", score)
    ai_data.setdefault("score_experience", score)
    ai_data.setdefault("score_context", score)
    ai_data.setdefault(
        "recruiter_view",
        {"summary": "", "red_flags": [], "final_checklist": []},
    )
    rewritten_data = ai_engine.generate_optimized_experience(
        resume_text, job_description, job_title=job_title, company=company
    )

    # Verificar se ocorreu erro antes de abrir o modal de resultados
    if not rewritten_data or rewritten_data.get("error"):
        user_message = None
        if isinstance(rewritten_data, dict):
            user_message = rewritten_data.get("error_message")

        if not user_message:
            user_message = (
                "Não foi possível gerar as versões otimizadas do currículo com IA "
                "no momento. Tente novamente em alguns minutos."
            )
        flash(user_message, "danger")
        return redirect(url_for("index"))

    #Salvar no hístorico (dashboard)
    if logged_in:
        db_manager.save_analysis(
            username,
            job_title,
            ai_data.get("score", 0),
            ai_data.get("missing_skills", []),
            job_link,
        )

    return render_template(
        "index.html",
        logged_in=logged_in,
        username=username,
        analysis=ai_data,
        rewritten=rewritten_data,
        audit=audit_data,
        job_title=job_title,
        job_description=job_description,
        company=company,
        job_link=job_link,
        job_mode=job_mode,
    )

@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()

    if not username or not password:
        flash("Preencha usuário e senha.", "warning")
        return redirect(url_for("index"))

    if db_manager.login_user(username, password):
        session["logged_in"] = True
        session["username"] = username
        flash("Login realizado com sucesso!", "success")
    else:
        flash("Usuário ou senha incorretos.", "danger")

    return redirect(url_for("index"))


@app.route("/signup", methods=["POST"])
def signup():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()

    if not username or not password:
        flash("Preencha usuário e senha.", "warning")
        return redirect(url_for("index"))

    if db_manager.create_user(username, password):
        session["logged_in"] = True
        session["username"] = username
        flash("Conta criada com sucesso!", "success")
        return redirect(url_for("index"))
    else:
        flash("Esse usuário já existe.", "danger")
        return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.clear()
    flash("Você saiu da sua conta.", "info")
    return redirect(url_for("index"))


@app.route("/dashboard")
def dashboard():
    username, logged_in = get_logged_user()
    if not logged_in:
        flash("Você precisa estar logado para acessar o painel.", "warning")
        return redirect(url_for("index"))

    history = db_manager.get_user_history(username)
    if not history:
        return render_template(
            "dashboard.html",
            logged_in=True,
            username=username,
            has_history=False,)
    num_cols = len(history[0])
    if num_cols == 7:
        cols = [
            "id",
            "job_title",
            "score",
            "missing_skills",
            "analysis_date",
            "status",
            "job_link",
        ]
    elif num_cols == 6:
        cols = ["id", "job_title", "score", "missing_skills", "analysis_date", "status"]
    else:
        cols = [f"col_{i}" for i in range(num_cols)]

    df = pd.DataFrame(history, columns=cols)
    if "analysis_date" in df.columns:
        df["analysis_date"] = pd.to_datetime(df["analysis_date"])
    else:
        df["analysis_date"] = pd.to_datetime("now")

    total_analises = int(len(df))
    media_score = int(df["score"].mean())
    melhor_score = int(df["score"].max())
    df_sorted = df.sort_values("analysis_date")
    score_labels = [
        d.strftime("%d/%m/%Y %H:%M") for d in df_sorted["analysis_date"].tolist()
    ]
    score_values = df_sorted["score"].tolist()

    #Top 5 skills faltantes
    from collections import Counter

    all_skills = []
    for s in df["missing_skills"]:
        try:
            all_skills.extend(json.loads(s))
        except Exception:
            pass

    skills_labels = []
    skills_values = []

    if all_skills:
        counter = Counter(all_skills)
        top5 = counter.most_common(5)
        skills_labels = [k for k, _ in top5]
        skills_values = [v for _, v in top5]

    # Tabela
    table_rows = []
    df_table = df.sort_values("analysis_date", ascending=False)
    has_job_link = "job_link" in df_table.columns

    for _, row in df_table.iterrows():
        link_value = None
        if has_job_link and isinstance(row["job_link"], str) and row["job_link"].strip():
            link_value = row["job_link"].strip()

        table_rows.append(
            {
                "data": row["analysis_date"].strftime("%d/%m/%Y %H:%M"),
                "vaga": row["job_title"],
                "score": int(row["score"]),
                "status": row["status"] if "status" in df_table.columns else "Analisado",
                "link": link_value,
            }
        )

    return render_template(
        "dashboard.html",
        logged_in=True,
        username=username,
        has_history=True,
        total_analises=total_analises,
        media_score=media_score,
        melhor_score=melhor_score,
        score_labels=score_labels,
        score_values=score_values,
        skills_labels=skills_labels,
        skills_values=skills_values,
        table_rows=table_rows,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
