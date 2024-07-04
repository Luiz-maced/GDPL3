# IMPORTANDO AS BIBLIOTECAS MAROTAS
from flask import (
    Flask,
    Response,
    send_file,
    jsonify,
    render_template,
    request,
    redirect,
    url_for,
    send_from_directory,
    flash,
    session,
)
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from openpyxl import Workbook
from functools import wraps
import json
import os
from flask_mail import Mail, Message
import uuid
import plotly.express as px
import pandas as pd
from reportlab.pdfgen import canvas
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from io import BytesIO
from reportlab.lib.pagesizes import letter
import secrets
from datetime import datetime, timedelta
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email
import xlsxwriter

# INICIO DA APLICAÇÃO FLASK
app = Flask(__name__)

# Inicializar o LoginManager
login_manager = LoginManager()
login_manager.init_app(app)
# Definir a view de login
login_manager.login_view = "login"


# Definir a função user_loader antes de inicializar o LoginManager
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def generate_session_token():
    return secrets.token_urlsafe(16)


# Definindo o caminho do banco de dados e colunas para ser no diretório atual da aplicação
basedir = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(basedir, "uruk.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = "suportegdpl@gmail.com"
app.config["MAIL_PASSWORD"] = "scc l tpam ljiw vuqo"
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["SECRET_KEY"] = "5550123"
app.config["MAIL_DEFAULT_SENDER"] = "suportegdpl@gmail.com"
mail = Mail(app)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    auth_key = db.Column(db.String(36), unique=True, nullable=False)
    session_token = db.Column(db.String(150), nullable=True)  # Token de sessão

    def __init__(self, email):
        self.email = email
        self.auth_key = str(uuid.uuid4())


class Aluno(db.Model):
    id_aluno = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    nome = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(50), nullable=False)
    idade = db.Column(db.Float, nullable=False)
    data_cadastro = db.Column(db.DateTime, default=datetime.now, nullable=False)
    peso_atu = db.Column(db.Float, nullable=False)
    peso_alvo = db.Column(db.Float, nullable=False)
    tp_pagto = db.Column(db.Integer, nullable=False)
    status_aluno = db.Column(db.Integer, default=0)

    user = db.relationship("User", backref="alunos")


class Treino(db.Model):
    id_treino = db.Column(db.Integer, primary_key=True)
    aluno_id = db.Column(db.Integer, db.ForeignKey("aluno.id_aluno"), nullable=False)
    treino_tipo = db.Column(db.String(50), nullable=False)
    dt_criacao = db.Column(db.String(50), nullable=False)
    detalhes = db.Column(db.String(50), nullable=False)
    aluno = db.relationship("Aluno", backref="treinos")


class Exercicio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    treino_id = db.Column(db.Integer, db.ForeignKey("treino.id_treino"), nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    series = db.Column(db.String(100), nullable=False)
    repeticoes = db.Column(db.String(100), nullable=False)
    descanso = db.Column(db.String(100), nullable=False)


# Crie todas as tabelas
with app.app_context():
    db.create_all()


def session_protected(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        user = current_user
        session_token = session.get("session_token")

        if not user.is_authenticated or user.session_token != session_token:
            logout_user()
            session.pop("session_token", None)
            flash("Sessão inválida ou expirada. Faça login novamente.", "danger")
            return redirect(url_for("login"))

        return func(*args, **kwargs)

    return decorated_function


class RegistrationForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    submit = SubmitField("Register")


@app.route("/protected", methods=["GET"])
@login_required
@session_protected
def protected():
    return jsonify({"message": "Acesso permitido."})


# Chave de segurança para download do banco
SECURITY_KEY = "masterkey"


# Rota para baixar o banco de dados
@app.route("/download_db", methods=["GET", "POST"])
def download_db():
    security_key = request.form.get("security_key")
    if security_key == SECURITY_KEY:
        return send_from_directory(
            directory=basedir, path="uruk.db", as_attachment=True
        )
    else:
        flash("Chave de segurança incorreta. Tente novamente.")
        return redirect(url_for("configuracoes"))


@app.route("/", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        user = User.query.filter_by(email=email).first()
        if user:
            flash("Email já registrado.", "danger")
        else:
            new_user = User(email=email)  # Cria o objeto User com o e-mail
            db.session.add(new_user)
            db.session.commit()
            msg = Message(
                "Essa é sua chave de login!",
                sender="suportegdpl@gmail.com",
                recipients=[email],
            )
            msg.body = f"Sua chave de autenticação é: {new_user.auth_key}. Guarde-a em um lugar seguro, ela funciona como sua senha do app."
            mail.send(msg)
            flash(
                "Registro bem-sucedido! Verifique seu email para a chave de autenticação.",
                "success",
            )
            return redirect(url_for("login"))
    return render_template("auth/register.html")


active_sessions = set()  # Definindo a variável global


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        auth_key = request.form.get("auth_key")
        user = User.query.filter_by(email=email, auth_key=auth_key).first()

        if user:
            if user.session_token not in active_sessions:
                # Invalidate previous session
                active_sessions.discard(user.session_token)
                user.session_token = generate_session_token()
                active_sessions.add(user.session_token)
                db.session.commit()

            login_user(user)
            # Store the token in the Flask session
            session["session_token"] = user.session_token
            return redirect(url_for("menu"))
        else:
            flash("Login falhou. Verifique suas credenciais.", "danger")

    return render_template("auth/login.html")


@app.route("/logout", methods=["POST"])
@login_required
@session_protected
def logout():
    user = current_user
    if user.is_authenticated:
        # Clear the session token
        user.session_token = None
        active_sessions.discard(user.session_token)
        db.session.commit()

        # Remove the token from the Flask session
        session.pop("session_token", None)
        logout_user()
        return redirect(url_for("login"))

    return jsonify({"error": "Nenhum usuário logado."}), 401


@app.route("/termos", methods=["GET", "POST"])
@login_required
def termos():
    return render_template("auth/termos.html")


@app.route("/privacidade", methods=["GET", "POST"])
@login_required
def privacidade():
    return render_template("auth/privacidade.html")


@app.route("/menu", methods=["GET"])
@login_required
@session_protected
def menu():
    # Dados para o gráfico de novos cadastros de alunos por mês
    hoje = datetime.now()
    meses_anteriores = [hoje - timedelta(days=i * 30) for i in range(5)]
    meses_anteriores.reverse()  # Inverter para começar do mês mais antigo
    labels = [mes.strftime("%B") for mes in meses_anteriores]

    valores_ativos = []
    valores_inativos = []

    for mes in meses_anteriores:
        mes_atual = mes.replace(day=1)  # Primeiro dia do mês atual
        mes_proximo = (
            mes_atual.replace(month=mes_atual.month + 1)
            if mes_atual.month < 12
            else mes_atual.replace(year=mes_atual.year + 1, month=1)
        )  # Primeiro dia do próximo mês

        count_alunos_ativos = Aluno.query.filter(
            Aluno.data_cadastro >= mes_atual,
            Aluno.data_cadastro < mes_proximo,
            Aluno.status_aluno == 0,
            Aluno.user_id == current_user.id,
        ).count()
        valores_ativos.append(count_alunos_ativos)

        count_alunos_inativos = Aluno.query.filter(
            Aluno.data_cadastro >= mes_atual,
            Aluno.data_cadastro < mes_proximo,
            Aluno.status_aluno == 1,
            Aluno.user_id == current_user.id,
        ).count()
        valores_inativos.append(count_alunos_inativos)

    total_cadastros_ativos = sum(valores_ativos)
    total_cadastros_inativos = sum(valores_inativos)

    # Consulta para obter os nomes dos alunos
    return render_template(
        "aplication/menu.html",
        user_id=current_user.email,
        labels=labels,
        valores_ativos=valores_ativos,
        valores_inativos=valores_inativos,
        total_cadastros_ativos=total_cadastros_ativos,
        total_cadastros_inativos=total_cadastros_inativos,
    )


# Adiciona um novo aluno
@app.route("/adicionar_aluno", methods=["GET", "POST"])
@login_required
def adicionar_aluno():
    if request.method == "POST":
        nome = request.form.get("nome")
        email = request.form.get("email")
        idade = request.form.get("idade")
        peso_atu = request.form.get("peso_atu")
        peso_alvo = request.form.get("peso_alvo")
        tp_pagto = request.form.get("tp_pagto")
        user_id = current_user.id

        # Validação dos dados
        if not nome or not email:
            flash("Nome e email são obrigatórios", "error")
            return redirect(url_for("adicionar_aluno"))

        try:
            # Criação de um novo aluno
            novo_aluno = Aluno(
                user_id=user_id,
                nome=nome,
                email=email,
                idade=int(idade) if idade else None,
                peso_atu=float(peso_atu) if peso_atu else None,
                peso_alvo=float(peso_alvo) if peso_alvo else None,
                tp_pagto=tp_pagto if tp_pagto else None,
            )

            db.session.add(novo_aluno)
            db.session.commit()

            # Verificação do ID do Aluno
            if not novo_aluno.id_aluno:
                raise ValueError("ID do aluno não gerado")

        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao adicionar aluno: {e}", "error")
            return redirect(url_for("adicionar_aluno"))

        # Redireciona para a página de treino com os detalhes do aluno
        flash("Aluno adicionado com sucesso!", "success")
        return redirect(url_for("adicionar_treino", aluno_id=novo_aluno.id_aluno))

    return render_template("aplication/cadastro_aluno.html")


@app.route("/adicionar_treino", methods=["GET", "POST"])
@login_required
@session_protected
def adicionar_treino():
    if request.method == "POST":
        aluno_nome = request.form.get("aluno_nome")
        treino_tipo = request.form.get("treino_tipo")
        dt_criacao = request.form.get("dt_criacao")
        detalhes_treino = request.form.get("detalhes")

        # Validação básica dos dados do formulário
        if not aluno_nome or not treino_tipo or not dt_criacao:
            flash(
                "Nome do aluno, tipo de treino e data de criação são obrigatórios.",
                "error",
            )
            return redirect(url_for("adicionar_treino"))

        try:
            aluno = Aluno.query.filter_by(
                nome=aluno_nome, user_id=current_user.id
            ).first()
            if not aluno:
                flash("Aluno não localizado.", "error")
                return redirect(url_for("adicionar_treino"))

            novo_treino = Treino(
                aluno_id=aluno.id_aluno,
                treino_tipo=treino_tipo,
                dt_criacao=dt_criacao,
                detalhes=detalhes_treino,
            )
            db.session.add(novo_treino)
            db.session.commit()

            # Processar os dados da tabela de exercícios
            exercicios = request.form.getlist("exercicio[]")
            series_repeticoes = request.form.getlist("series_repeticoes[]")
            descansos = request.form.getlist("descanso[]")

            # Validação dos dados de exercícios
            if not (exercicios and series_repeticoes and descansos):
                flash("Todos os campos de exercícios são obrigatórios.", "error")
                return redirect(url_for("adicionar_treino"))

            for i in range(len(exercicios)):
                series, repeticoes = series_repeticoes[i].split("x")
                novo_exercicio = Exercicio(
                    treino_id=novo_treino.id_treino,
                    nome=exercicios[i],
                    series=int(series) if series else None,
                    repeticoes=int(repeticoes) if repeticoes else None,
                    descanso=descansos[i] if descansos[i] else None,
                )
                db.session.add(novo_exercicio)

            db.session.commit()

            flash("Treino adicionado com sucesso!", "success")
            return redirect(url_for("adicionar_treino"))

        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao adicionar treino: {e}", "error")
            return redirect(url_for("adicionar_treino"))

    alunos = Aluno.query.filter_by(user_id=current_user.id).all()
    return render_template("aplication/adicionar_treino.html", alunos=alunos)


@app.route("/procurar_aluno", methods=["GET", "POST"])
@login_required
def procurar_aluno():
    return render_template("aplication/buscar_aluno.html")


@app.route("/buscar_aluno", methods=["GET", "POST"])
@login_required
def buscar_aluno():
    alunos = []
    if request.method == "POST":
        nome = request.form.get("nome")
        if nome:
            # Filtrando os alunos pelo nome e pelo usuário atual
            alunos = Aluno.query.filter(
                Aluno.user_id == current_user.id,
                Aluno.nome.ilike(
                    f"%{nome}%"
                ),  # Usando ILIKE para busca case-insensitive
            ).all()

    return render_template("aplication/resultadoaluno.html", alunos=alunos)


# Rota para exportar todos os alunos para Excel
@app.route("/exportar_alunos_excel", methods=["POST"])
@login_required
@session_protected
def exportar_alunos_excel():
    alunos = Aluno.query.filter_by(user_id=current_user.id).all()

    # Verifica se há alunos para exportar
    if not alunos:
        return "Erro: Nenhum aluno encontrado para exportação."

    # Transforma os alunos em uma lista de dicionários
    alunos_dict = [{"nome": aluno.nome} for aluno in alunos]

    # Configurações iniciais para o arquivo Excel
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet("Alunos")

    # Escrevendo cabeçalho
    headers = ["Nome"]
    for col, header in enumerate(headers):
        worksheet.write(0, col, header)

    # Escrevendo dados dos alunos
    for row, aluno in enumerate(alunos_dict, start=1):
        worksheet.write(row, 0, aluno["nome"])

    workbook.close()

    # Configurando a resposta para o navegador
    output.seek(0)
    return Response(
        output.read(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment;filename=alunos.xlsx"},
    )


@app.route("/buscar_e_gerar_pdf", methods=["GET", "POST"])
@login_required
@session_protected
def buscar_e_gerar_pdf():
    alunos = []
    treinos_selecionados = []
    if request.method == "POST":
        nome = request.form.get("nome")
        if nome:
            # Filtrando os alunos pelo nome e pelo usuário atual
            alunos = Aluno.query.filter(
                Aluno.user_id == current_user.id, Aluno.nome.ilike(f"%{nome}%")
            ).all()

        if "gerar_pdf" in request.form:
            # Processar os treinos selecionados
            treinos_selecionados = request.form.getlist("treino")

            # Gerar PDF com os resultados da busca
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            styles = getSampleStyleSheet()
            elements = []

            for aluno in alunos:
                elements.append(Paragraph(f"Aluno: {aluno.nome}", styles["Title"]))
                elements.append(Paragraph(f"Idade: {aluno.idade}", styles["Normal"]))
                elements.append(
                    Paragraph(f"Peso Atual: {aluno.peso_atu}", styles["Normal"])
                )
                elements.append(
                    Paragraph(f"Peso Alvo: {aluno.peso_alvo}", styles["Normal"])
                )
                elements.append(Spacer(1, 12))

                elements.append(Paragraph("Treinos:", styles["Heading2"]))
                treinos = Treino.query.filter_by(aluno_id=aluno.id_aluno).all()

                for treino in treinos:
                    if str(treino.id_treino) in treinos_selecionados:
                        elements.append(
                            Paragraph(
                                f"Tipo de Treino: {treino.treino_tipo}",
                                styles["Heading3"],
                            )
                        )
                        elements.append(
                            Paragraph(
                                f"Detalhes do Treino: {treino.detalhes}",
                                styles["Normal"],
                            )
                        )
                        elements.append(
                            Paragraph(
                                f"Treino cadastrado em: {treino.dt_criacao}",
                                styles["Normal"],
                            )
                        )

                        elements.append(Paragraph("Exercícios:", styles["Heading3"]))
                        exercicios = Exercicio.query.filter_by(
                            treino_id=treino.id_treino
                        ).all()
                        exercicio_data = [
                            ["Exercício", "Séries", "Repetições", "Descanso"]
                        ]

                        for exercicio in exercicios:
                            exercicio_data.append(
                                [
                                    exercicio.nome,
                                    exercicio.series,
                                    exercicio.repeticoes,
                                    exercicio.descanso,
                                ]
                            )

                        exercicio_table = Table(exercicio_data)
                        exercicio_table.setStyle(
                            TableStyle(
                                [
                                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                                    ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                                ]
                            )
                        )

                        elements.append(exercicio_table)
                        elements.append(Spacer(1, 12))

            doc.build(elements)
            buffer.seek(0)

            # Enviar e-mail com o PDF em anexo para o e-mail do aluno
            for aluno in alunos:
                msg = Message("Ficha de Treino", recipients=[aluno.email])
                msg.body = "Segue em anexo a ficha de treino solicitada."
                msg.attach("FichaDeTreino.pdf", "application/pdf", buffer.getvalue())
                mail.send(msg)

            # Redirecionar para evitar reenvio do formulário
            return redirect(url_for("buscar_e_gerar_pdf"))

    return render_template("aplication/buscar_e_gerar_pdf.html", alunos=alunos)


@app.route("/configuracoes", methods=["GET", "POST"])
@login_required
@session_protected
def configuracoes():
    return render_template("aplication/configuracoes.html")


@app.route("/ficha", methods=["GET", "POST"])
@login_required
def ficha():
    aluno = None
    messages = []

    if request.method == "POST":
        form_type = request.form.get("form_type")
        if form_type == "buscar_aluno":
            nome = request.form.get("nome_busca")
            if nome:
                aluno = Aluno.query.filter_by(
                    nome=nome, user_id=current_user.id
                ).first()
                if not aluno:
                    flash(f"Aluno '{nome}' não localizado.", "error")
                else:
                    flash("Aluno encontrado.", "success")
            return render_template(
                "aplication/ficha.html", aluno=aluno, messages=messages
            )

        elif form_type == "atualizar_aluno":
            id_aluno = request.form.get("id_aluno")
            aluno = Aluno.query.filter_by(
                id_aluno=id_aluno, user_id=current_user.id
            ).first()
            if aluno:
                if request.form.get("nome"):
                    aluno.nome = request.form.get("nome")
                if request.form.get("email"):
                    aluno.email = request.form.get("email")
                if request.form.get("idade"):
                    aluno.idade = request.form.get("idade")
                if request.form.get("peso_atu"):
                    aluno.peso_atu = request.form.get("peso_atu")
                if request.form.get("peso_alvo"):
                    aluno.peso_alvo = request.form.get("peso_alvo")
                if request.form.get("tp_pagto"):
                    aluno.tp_pagto = request.form.get("tp_pagto")

                status_aluno = request.form.get("status_aluno")
                if status_aluno is not None:
                    aluno.status_aluno = int(status_aluno)

                try:
                    db.session.commit()
                    flash("Informações do aluno atualizadas com sucesso!", "success")
                except Exception as e:
                    db.session.rollback()
                    flash(f"Erro ao atualizar informações do aluno: {e}", "error")

            return redirect(url_for("ficha"))

    elif request.method == "GET":
        aluno = Aluno.query.filter_by(user_id=current_user.id).first()
        if not aluno:
            flash("Aluno não localizado.", "error")
            return redirect(url_for("menu"))

    return render_template("aplication/ficha.html", aluno=aluno, messages=messages)


if __name__ == "__main__":
    app.run(debug=True)
