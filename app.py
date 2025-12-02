import os
from datetime import datetime, timezone, timedelta
from functools import wraps  # Importado para o decorator

import permissoes
import auth
import sheets
from flask import (Flask, render_template, request, redirect, url_for, session, send_file)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# --- Configuração da Aplicação ---

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "nada ainda")

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[]  # sem limite global
)


# ---------------------------
# Template filters (formatação BR)
# ---------------------------
@app.template_filter('br_currency')
def br_currency(value):
    """Formata número como moeda brasileira: 28000.0 -> 28.000,00"""
    try:
        if value is None or value == "":
            return "0,00"
        v = float(value)
        s = format(v, ",.2f")  # e.g. '28,000.00'
        # swap thousand and decimal separators: ',' -> temporary, '.'->',', temporary->'.'
        s = s.replace(',', 'X').replace('.', ',').replace('X', '.')
        return s
    except Exception:
        return value


@app.template_filter('br_decimal')
def br_decimal(value):
    """Formata número com duas casas decimais e padrão brasileiro (sem R$)."""
    try:
        if value is None or value == "":
            return "0,00"
        v = float(value)
        s = format(v, ",.2f")
        s = s.replace(',', 'X').replace('.', ',').replace('X', '.')
        return s
    except Exception:
        return value


@app.template_filter('br_date')
def br_date(value):
    """Converte datas ISO (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS) ou US (MM/DD/YYYY) para DD/MM/YYYY."""
    if not value:
        return value
    from datetime import datetime
    formatos = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"]
    for fmt in formatos:
        try:
            dt = datetime.strptime(str(value), fmt)
            return dt.strftime("%d/%m/%Y")
        except Exception:
            continue
    return value


@app.template_filter('br_cep')
def br_cep(value):
    if value is None or value == "":
        return ""
    s = str(value).strip()
    # remove non-digit
    import re
    digits = re.sub(r"\D", "", s)
    digits = digits.zfill(8)
    return f"{digits[:5]}-{digits[5:]}"


@app.template_filter('br_cpf')
def br_cpf(value):
    if value is None or value == "":
        return ""
    s = str(value).strip()
    import re
    digits = re.sub(r"\D", "", s)
    digits = digits.zfill(11)
    return f"{digits[0:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:11]}"


@app.template_filter('br_phone')
def br_phone(value):
    if value is None or value == "":
        return ""
    s = str(value).strip()
    import re
    digits = re.sub(r"\D", "", s)
    # celular com 11 dígitos (DD+9) -> (XX) 9XXXX-XXXX
    if len(digits) == 11:
        return f"({digits[0:2]}) {digits[2:7]}-{digits[7:11]}"
    if len(digits) == 10:
        return f"({digits[0:2]}) {digits[2:6]}-{digits[6:10]}"
    return s

# -----------------------------------------------------------------
# Decorator de Autenticação
# -----------------------------------------------------------------

def login_required(f):
    """
    Decorator para garantir que o usuário esteja logado.
    Redireciona para a página de login se não estiver.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

def tem_permissao(acao):
    """
    Verifica a permissão do usuário logado com base na sessão.
    """
    nivel = session.get("acesso")
    return permissoes.verificar_permissao(nivel, acao)

@app.context_processor
def inject_permissions():
    return dict(tem_permissao=tem_permissao)

# -----------------------------------------------------------------
# Rotas de Autenticação e Usuário
# -----------------------------------------------------------------

@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    # Se já estiver logado, redireciona para a home
    if "usuario_id" in session:
        return redirect(url_for("home"))

    if request.method == "POST":
        nome = request.form.get("nome")
        sobrenome = request.form.get("sobrenome")
        cidade = request.form.get("cidade")
        telefone = request.form.get("telefone")
        email = request.form.get("email")
        senha = request.form.get("senha")
        confirmar_senha = request.form.get("confirmarSenha")

        if senha != confirmar_senha:
            return render_template(
                "cadastro.html",
                mensagem="As senhas não coincidem!",
                tipo="erro"
            )

        sucesso = auth.cadastrar_usuario(
            email=email,
            senha=senha,
            nome=nome,
            sobrenome=sobrenome,
            cidade=cidade,
            telefone=telefone
        )

        if sucesso:
            return render_template(
                "cadastro.html",
                mensagem="Cadastro realizado com sucesso!",
                tipo="sucesso"
            )
        else:
            return render_template(
                "cadastro.html",
                mensagem="Email já cadastrado!",
                tipo="erro"
            )

    return render_template("cadastro.html")

@app.route("/login", methods=["GET"])
def login():
    if "usuario_id" in session:
        return redirect(url_for("home"))
    return render_template("login.html")

# app.py - substitua a função login_submit existente por esta
@app.route("/login", methods=["POST"])
@limiter.limit("3 per 2 minutes")
def login_submit():
    email = request.form.get("email")
    senha = request.form.get("senha")

    usuario = auth.validar_login(email, senha)

    # Debug: log detalhado no servidor (ver saída do console/render)
    app.logger.debug("Login attempt for email=%s -> usuario=%r", email, usuario)

    if usuario:
        # Garante dicionário correto
        usuario_id = usuario.get("id") if isinstance(usuario, dict) else None
        acesso = usuario.get("acesso") if isinstance(usuario, dict) else None

        # Fallback seguro
        if not acesso:
            acesso = "Visitante"
            app.logger.debug("Acesso não definido no registro. Aplicando fallback: %s", acesso)

        if not usuario_id:
            # Caso inesperado: log e aviso
            app.logger.error("Login válido mas sem 'id' retornado para email=%s. usuario=%r", email, usuario)
            return render_template("login.html", mensagem="Erro interno: usuário sem id. Contate o administrador.", tipo="erro")

        # Limpa e grava sessão
        session.clear()
        session["usuario_id"] = usuario_id
        session["acesso"] = acesso

        # Debug: confirma valores salvos
        app.logger.debug("Sessão criada: usuario_id=%s, acesso=%s", session.get("usuario_id"), session.get("acesso"))

        return redirect(url_for("home"))

    else:
        # Loga motivo provável (não expõe dados sensíveis ao usuário)
        app.logger.debug("Falha no login para email=%s (credenciais inválidas ou usuário inativo).", email)
        return render_template("login.html", mensagem="ID ou senha inválidos!", tipo="erro")


@app.errorhandler(429)
def ratelimit_handler(e):
    return render_template("login.html", mensagem="Muitas tentativas! Tente novamente em alguns minutos.", tipo="erro"), 429

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/perfil")
@login_required
def perfil():
    user_id = session["usuario_id"]
    usuario = sheets.listar_user_por_id(user_id)

    if not usuario:
        return render_template("index.html", mensagem="Usuário não encontrado!", tipo="erro")

    return render_template("perfil.html", usuario=usuario, mostrar_sair=True, active_page='perfil')

# -----------------------------------------------------------------
# Rotas Principais (Core)
# -----------------------------------------------------------------

@app.route("/")
@login_required
def home():
    # O decorator @login_required já garante que "usuario_id" existe
    usuario_id = session.get("usuario_id") 
    return render_template("index.html", usuario_id=usuario_id , active_page='inicio')

# -----------------------------------------------------------------
# Rotas de Clientes
# -----------------------------------------------------------------

@app.route("/cadastro_cliente")
@login_required
def cadastro_cliente():
    return render_template("cadastrarCliente.html", active_page='cadastro_cliente')

@app.route("/cadastrar_cliente", methods=["POST"])
@login_required
def cadastrar_cliente():
    nome = request.form.get("nome")
    telefone = request.form.get("telefone")
    email = request.form.get("email")
    cpf = request.form.get("cpf")
    nascimento = request.form.get("nascimento")
    cep = request.form.get("cep")
    estado = request.form.get("estado")
    municipio = request.form.get("municipio")
    logradouro = request.form.get("logradouro")
    numero = request.form.get("numero")
    proprietario = session["usuario_id"]
    data_cadastro = (datetime.now(timezone.utc) - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")

    if nome and email:
        sheets.salvar_cliente(nome, email, telefone, proprietario, datacad=data_cadastro,
                      cpf=cpf, nascimento=nascimento,
                      cep=cep, estado=estado, municipio=municipio,
                      logradouro=logradouro, numero=numero)
        # Armazena mensagem temporária na sessão (para aparecer em /meus_clientes)
        session["mensagem"] = "Cliente cadastrado com sucesso!"
        session["tipo_mensagem"] = "sucesso"
        return redirect(url_for("meus_clientes"))
    else:
        return render_template("cadastrarCliente.html", mensagem="Erro ao cadastrar!", tipo="erro", active_page='cadastro_cliente')


@app.route("/meus_clientes")
@login_required
def meus_clientes():
    owner_id = session["usuario_id"]
    clientes = sheets.listar_clientes_por_owner(owner_id)

    # Recupera mensagem da sessão, se existir
    mensagem = session.pop("mensagem", None)
    tipo = session.pop("tipo_mensagem", None)

    return render_template("meusClientes.html", clientes=clientes, mensagem=mensagem, tipo=tipo , active_page='meus_clientes')


# -----------------------------------------------------------------
# Rotas de Oportunidades
# -----------------------------------------------------------------

@app.route("/minhas_opp")
@login_required
def minhas_opp():
    proprietario = session["usuario_id"]
    pagina = int(request.args.get("pagina", 1))
    limite = 10

    oportunidades = sheets.listar_opp_por_owner_paginado(proprietario, pagina=pagina, limite=limite)
    tem_proxima = len(oportunidades) == limite

    mensagem = request.args.get("mensagem")
    tipo = request.args.get("tipo")

    return render_template(
        "minhasOportunidades.html",
        oportunidades=oportunidades,
        pagina_atual=pagina,
        tem_proxima=tem_proxima,
        mensagem=mensagem,
        tipo=tipo,
        active_page='minhas_opp'
    )

@app.route("/iniciar_fluxo_oportunidade")
@login_required
def iniciar_fluxo_oportunidade():
    """
    Controlador de fluxo. Inicia o processo de "Continuar" (com ID) 
    ou "Novo" (com nome/email de um cliente).
    """
    # Limpa dados de um fluxo anterior para evitar conflitos
    session.pop("opp_id", None)
    session.pop("opp_continuar", None)
    session.pop("opp_nome", None)
    session.pop("opp_email", None)

    id_opp = request.args.get("id")
    continuar = request.args.get("continuar")

    if id_opp and continuar == "1":
        # Fluxo "Continuar" - vindo de /minhas_opp
        session["opp_id"] = id_opp
        session["opp_continuar"] = "1"
    else:
        # Fluxo "Novo" - vindo de /meus_clientes ou link direto
        # Preferimos receber um cliente_id explícito ao iniciar o fluxo.
        cliente_id = request.args.get("cliente_id")
        if cliente_id:
            # Armazena o vínculo do cliente para uso na criação da oportunidade
            session["opp_cliente_id"] = cliente_id
            # Tenta popular nome/email a partir do cliente cadastrado (mais confiável)
            try:
                cliente = sheets.buscar_cliente_por_id(cliente_id)
                if cliente:
                    session["opp_nome"] = cliente.get("nome")
                    session["opp_email"] = cliente.get("email")
            except Exception:
                # Não falhar o fluxo se a busca do cliente der problema
                app.logger.debug("Falha ao buscar cliente por id ao iniciar fluxo: %s", cliente_id)
        else:
            # Fallback antigo: nome/email passados na querystring
            session["opp_nome"] = request.args.get("nome")
            session["opp_email"] = request.args.get("email")
        # opp_id e opp_continuar permanecem None

    return redirect(url_for("nova_oportunidade"))

@app.route("/nova_oportunidade")
@login_required
def nova_oportunidade():
    id_opp = session.get("opp_id")
    veio_continuar = session.get("opp_continuar") == "1"

    produtos = sheets.listar_produtos()
    categorias = [
        {"potencia": p.get("potencia"), "preco": p.get("preco")}
        for p in produtos if p.get("potencia")
    ]
    # Remove duplicados
    categorias = [dict(t) for t in {tuple(d.items()) for d in categorias}]

    oportunidade_existente = None
    if veio_continuar and id_opp:
        oportunidade_existente = sheets.buscar_oportunidade_por_id(id_opp)
        
        # Validação de segurança
        if oportunidade_existente and oportunidade_existente.get("proprietario") != session["usuario_id"]:
            session.pop("opp_id", None)
            session.pop("opp_continuar", None)
            return redirect(url_for("minhas_opp", mensagem="Erro de acesso.", tipo="erro"))

    # Busca nome/email da oportunidade (se 'Continuar') ou da sessão (se 'Novo')
    nome = oportunidade_existente.get("nome") if oportunidade_existente else session.get("opp_nome")
    email = oportunidade_existente.get("email") if oportunidade_existente else session.get("opp_email")

    # Se houve seleção explícita de cliente no fluxo, buscar para exibir
    cliente_selecionado = None
    cliente_id_selecionado = session.get("opp_cliente_id")
    if cliente_id_selecionado:
        try:
            cliente_selecionado = sheets.buscar_cliente_por_id(cliente_id_selecionado)
            # Preferir os dados do cliente para preencher o formulário
            if cliente_selecionado:
                nome = cliente_selecionado.get("nome") or nome
                email = cliente_selecionado.get("email") or email
        except Exception:
            app.logger.debug("Erro buscando cliente selecionado em nova_oportunidade: %s", cliente_id_selecionado)

    return render_template(
        "novaOportunidade.html",
        nome=nome,
        email=email,
        categorias=categorias,
        veio_continuar=veio_continuar,
        oportunidade=oportunidade_existente,
        cliente_selecionado=cliente_selecionado,
        sheets=sheets,
        active_page='minhas_opp'
    )

@app.route("/cadastrar_oportunidade", methods=["POST"])
@login_required
def cadastrar_oportunidade():
    modo = request.form.get("modo", "novo")
    id_opp = session.get("opp_id")  # Pega o ID da sessão (se existir)

    # Fallback: usa form primeiro, session se form não tiver
    nome = request.form.get("nome") or session.get("opp_nome")
    email = request.form.get("email") or session.get("opp_email")

    if not nome or not email:
        return render_template(
            "novaOportunidade.html",
            mensagem="Erro: nome ou email faltando. Operação cancelada.",
            tipo="erro",
            nome=session.get("opp_nome"),
            email=session.get("opp_email"),
            categorias=sheets.listar_produtos(),
            veio_continuar=session.get("opp_continuar") == "1",
            oportunidade=None
        )

    # -------------------------------
    # Lógica de Upload
    # -------------------------------
    arquivo_principal = request.files.get("arquivo")
    arquivo_conta = request.files.get("conta_energia")

    link_principal = ""
    link_conta = ""

    # Upload do documento principal
    if arquivo_principal and arquivo_principal.filename:
        from werkzeug.utils import secure_filename
        filename = secure_filename(arquivo_principal.filename)
        caminho_local = os.path.join("uploads", filename)
        os.makedirs("uploads", exist_ok=True)
        arquivo_principal.save(caminho_local)

        pasta_id = os.environ.get("GOOGLE_DRIVE_PASTA_ID")
        link_principal = sheets.enviar_arquivo_drive(caminho_local, filename, pasta_id)
        os.remove(caminho_local)

    # Upload do comprovante de energia
    if arquivo_conta and arquivo_conta.filename:
        from werkzeug.utils import secure_filename
        filename_conta = secure_filename(arquivo_conta.filename)
        caminho_local_conta = os.path.join("uploads", filename_conta)
        os.makedirs("uploads", exist_ok=True)
        arquivo_conta.save(caminho_local_conta)

        pasta_id = os.environ.get("GOOGLE_DRIVE_PASTA_ID")
        link_conta = sheets.enviar_arquivo_drive(caminho_local_conta, filename_conta, pasta_id)
        os.remove(caminho_local_conta)

    # -------------------------------
    # Processamento
    # -------------------------------
    if modo == "continuar":
        if not id_opp:
            msg = "Erro: ID da oportunidade faltando."
            tipo = "erro"
        else:
            # Validação: ambos obrigatórios
            if not link_principal or not link_conta:
                return render_template(
                    "novaOportunidade.html",
                    mensagem="É obrigatório anexar os dois documentos: principal e comprovante de energia.",
                    tipo="erro",
                    veio_continuar=True,
                    oportunidade=sheets.buscar_oportunidade_por_id(id_opp)
                )

            # Atualiza a planilha com os dois links
            dados = {
                "link_documento": link_principal,
                "link_conta_energia": link_conta
            }
            atualizado = sheets.atualizar_oportunidade_anexo_por_id(id_opp, dados)

            if atualizado:
                msg = "Oportunidade enviada para aprovação!"
                tipo = "sucesso"
            else:
                msg = "Erro: não foi possível atualizar a oportunidade."
                tipo = "erro"

    else:
        # -------------------------------
        # Modo "novo"
        # -------------------------------
        potencia = request.form.get("potenciaReal")

        # Busca o produto correspondente à potência
        produto = None
        for p in sheets.listar_produtos():
            if str(p.get("potencia")) == str(potencia):
                produto = p
                break

        dados_nova_oportunidade = {
            "nome": nome,
            "email": email,
            "descricao": request.form.get("descricao"),
            "potencia": potencia,
            "valor": request.form.get("valorReal"),
            "proprietario": session["usuario_id"],
            "datacad": (datetime.now(timezone.utc) - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S"),
            "estado": "Criado",
            "link_documento": link_principal,
            "link_conta_energia": link_conta
        }

        # Prioriza cliente selecionado explicitamente no fluxo (armazenado na sessão)
        cliente_id_selecionado = session.get("opp_cliente_id")
        if cliente_id_selecionado:
            dados_nova_oportunidade["cliente_id"] = cliente_id_selecionado
        else:
            # Fallback: busca o cliente pelo email + proprietário (compatibilidade retroativa)
            cliente_info = sheets.buscar_cliente_por_email_e_proprietario(email, session["usuario_id"])
            if cliente_info:
                dados_nova_oportunidade["cliente_id"] = cliente_info.get("id", "")

        # Se o produto for encontrado, anexa dados técnicos
        if produto:
            dados_nova_oportunidade.update({
                "pacote": produto.get("pacote"),
                "kwp": produto.get("kwp"),
                "kw": produto.get("kw"),
                "inversor": produto.get("inversor"),
                "wpPainel": produto.get("wpPainel"),
                "unidadePainel": produto.get("unidadePainel"),
                "espacoFisico": produto.get("espacoFisico"),
                "preco": produto.get("preco"),
                "juros": produto.get("juros"),
                "valorParcela": produto.get("valorParcela"),
                "valorJuros": produto.get("valorJuros"),
            })

        sheets.salvar_oportunidade(dados_nova_oportunidade)
        msg = "Cadastro realizado com sucesso!"
        tipo = "sucesso"

    # -------------------------------
    # Limpeza da sessão
    # -------------------------------
    session.pop("opp_nome", None)
    session.pop("opp_email", None)
    session.pop("opp_data", None)
    session.pop("opp_continuar", None)
    session.pop("opp_id", None)
    # Remove seleção de cliente do fluxo para evitar contaminação
    session.pop("opp_cliente_id", None)

    return redirect(url_for("minhas_opp", mensagem=msg, tipo=tipo))

    # --- Preview da proposota ---

@app.route('/proposta/preview/<string:oportunidade_id>')
@login_required
def preview_proposta(oportunidade_id):
    oportunidade = sheets.buscar_oportunidade_por_id(oportunidade_id)

    imprimir_agora = request.args.get('imprimir') == '1'

    if not oportunidade:
        return "Oportunidade não encontrada.", 404

    cliente = None
    cliente_id = oportunidade.get("cliente_id")
    if cliente_id:
        cliente = sheets.buscar_cliente_por_id(cliente_id)

    return render_template('propostaPreview.html', 
                           oportunidade=oportunidade,
                           cliente=cliente,
                           imprimir_agora=imprimir_agora,
                           #debug = False
                           )

@app.route('/proposta/pdf/<string:oportunidade_id>')
def gerar_pdf_proposta(oportunidade_id):

    oportunidade = sheets.buscar_oportunidade_por_id(oportunidade_id)
    if not oportunidade:
        return "Oportunidade não encontrada.", 404

    html = render_template('propostaPreview.html', oportunidade=oportunidade)

    # PDF generation via wkhtmltopdf/pdfkit is not required for the MVP preview.
    # Redirect to the HTML preview and trigger client-side print instead.
    return redirect(url_for('preview_proposta', oportunidade_id=oportunidade_id, imprimir=1))
# -----------------------------------------------------------------
# Inicialização
# -----------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)
