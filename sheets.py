import auth
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Autenticação com Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_json = os.environ.get("GOOGLE_CREDS_ADM")
if not creds_json:
    raise ValueError("A variável de ambiente GOOGLE_CREDS_ADM não está definida.")
creds_dict = json.loads(creds_json)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

# Abrir planilha
planilha_id = os.environ.get("PLANILHA_ADM_ID")
if not planilha_id:
    raise ValueError("A variável PLANILHA_ADM_ID não está definida.")
spreadsheet = client.open_by_key(planilha_id)

# Acesso a abas
def get_aba(nome):
    return spreadsheet.worksheet(nome)

# Usuários
def listar_usuarios():
    return get_aba("usuarios").get_all_records()

def salvar_usuario(email, senha_hash, ativo=False, nome="", sobrenome="", cidade="", telefone=""):
    id, codigo = auth.gerar_identificador("usuario")
    get_aba("usuarios").append_row([
        id,
        codigo,
        email,
        senha_hash,
        ativo,
        nome,
        sobrenome,
        cidade,
        telefone
    ])
#produtos
def listar_produtos():
    aba = get_aba("produtos")  # Nome da guia no Sheets
    linhas = aba.get_all_records()
    return linhas

# Clientes
def salvar_cliente(nome, email, telefone, proprietario, datacad,
                   cpf=None, nascimento=None,
                   cep=None, estado=None, municipio=None, logradouro=None, numero=None):
    """
    Salva cliente na aba 'clientes'.
    Agora inclui CPF e data de nascimento além dos campos de endereço.

    Ordem das colunas gravadas (IMPORTANTE, corresponde ao cabeçalho esperado na planilha):
    id, codigo, nome, cpf, nascimento, email, telefone, proprietario, datacad, cep, estado, municipio, logradouro, numero
    """
    id, codigo = auth.gerar_identificador("cliente")

    # Prepara um mapa de valores (chaves normalizadas em minúsculas)
    valores_map = {
        "id": id,
        "codigo": codigo,
        "nome": nome or "",
        "cpf": (cpf or ""),
        "nascimento": (nascimento or ""),
        "email": (email or ""),
        "telefone": (telefone or ""),
        "proprietario": (proprietario or ""),
        "datacad": (datacad or ""),
        "cep": (cep or ""),
        "estado": (estado or ""),
        "municipio": (municipio or ""),
        "logradouro": (logradouro or ""),
        "numero": (numero or "")
    }

    aba = get_aba("clientes")
    # Lê cabeçalho atual da planilha para respeitar a ordem das colunas
    valores = aba.get_all_values()
    if valores and len(valores) >= 1:
        cabecalho = valores[0]
    else:
        # fallback para ordem esperada
        cabecalho = ["id", "codigo", "nome", "cpf", "nascimento", "email", "telefone", "proprietario", "datacad", "cep", "estado", "municipio", "logradouro", "numero"]

    # Monta a linha respeitando a ordem do cabeçalho (normalizando nomes)
    linha_para_salvar = []
    for h in cabecalho:
        key = (h or "").strip().lower()
        linha_para_salvar.append(valores_map.get(key, ""))

    aba.append_row(linha_para_salvar)

def listar_clientes_por_owner(owner_id):
    todos = get_aba("clientes").get_all_records()
    return [c for c in todos if str(c.get("proprietario")) == str(owner_id)]

def buscar_cliente_por_proprietario(proprietario_id):
    """
    Busca um cliente pelo ID do proprietário (owner ID).
    Retorna o primeiro cliente encontrado com esse proprietário.
    Inclui todos os dados do cliente: endereço, CPF, telefone, etc.
    """
    try:
        todos = get_aba("clientes").get_all_records()
        prop_busca = str(proprietario_id).strip()
        for cliente in todos:
            if str(cliente.get("proprietario", "")).strip() == prop_busca:
                return cliente
        return None
    except Exception as e:
        print(f"Erro ao buscar cliente por proprietario ({proprietario_id}): {e}")
        return None

def buscar_cliente_por_id(cliente_id):
    """
    Busca um cliente pelo seu ID.
    Retorna um dicionário com todos os dados do cliente.
    """
    try:
        todos = get_aba("clientes").get_all_records()
        id_busca = str(cliente_id).strip()
        for cliente in todos:
            if str(cliente.get("id", "")).strip() == id_busca:
                return cliente
        return None
    except Exception as e:
        print(f"Erro ao buscar cliente por ID ({cliente_id}): {e}")
        return None

def buscar_cliente_por_email_e_proprietario(email, proprietario_id):
    """
    Busca um cliente pelo email E proprietário (mais específico).
    Útil quando há múltiplos clientes do mesmo proprietário.
    """
    try:
        todos = get_aba("clientes").get_all_records()
        email_busca = str(email).strip().lower()
        prop_busca = str(proprietario_id).strip()
        for cliente in todos:
            if (str(cliente.get("email", "")).strip().lower() == email_busca and
                str(cliente.get("proprietario", "")).strip() == prop_busca):
                return cliente
        return None
    except Exception as e:
        print(f"Erro ao buscar cliente por email e proprietário: {e}")
        return None

# -----------------------------------------------------------------
# NOVA FUNÇÃO (Refatoração por ID)
# -----------------------------------------------------------------
def buscar_oportunidade_por_id(id_opp):
    """
    Busca uma única oportunidade pelo seu ID.
    Usado no fluxo 'Continuar Oportunidade'.
    """
    def _parse_brazil_number(val):
        """
        Normaliza strings numéricas no formato brasileiro (ex: "28\u00a0000,00" ou "1 835,56")
        para float (28000.0, 1835.56). Retorna o valor original se não for possível.
        """
        if val is None:
            return val
        # Se já for numérico, retorna como float/int óbvio
        if isinstance(val, (int, float)):
            return val
        try:
            s = str(val)
            # Remove símbolos de moeda e espaços em branco (inclui NBSP)
            s = s.replace('\u00a0', '').replace('\xa0', '')
            s = s.replace('R$', '').replace('r$', '')
            s = s.replace('\u20ac', '')
            # Remove espaços normais
            s = s.replace(' ', '')
            # Se já contém apenas dígitos e ponto, tentar converter direto
            # Troca vírgula decimal por ponto
            if ',' in s and s.count(',') >= 1:
                # Remove pontos de milhares (caso existam) e então trocar vírgula por ponto
                s = s.replace('.', '')
                s = s.replace(',', '.')
            # Poder haver outros caracteres como non-breaking space, já limpos
            return float(s)
        except Exception:
            return val

    try:
        aba = get_aba("oportunidades")
        todos = aba.get_all_records() # get_all_records retorna lista de dicionários
        id_busca = str(id_opp).strip()

        for registro in todos:
            if str(registro.get("id")).strip() == id_busca:
                # Converte campos monetários/numéricos que possam vir formatados como string
                for campo in ("preco", "valorParcela", "valorJuros", "valor"):
                    if campo in registro:
                        registro[campo] = _parse_brazil_number(registro.get(campo))
                return registro # Retorna o dicionário da oportunidade encontrada
        
        print(f"Oportunidade com ID {id_opp} não encontrada.")
        return None 
    except Exception as e:
        print(f"Erro ao buscar oportunidade por ID ({id_opp}): {e}")
        return None
# -----------------------------------------------------------------

def buscar_oportunidades_por_proprietario(proprietario):
    """
    Busca TODAS as oportunidades de um proprietário.
    (Nota: Não é mais usado no fluxo 'Continuar', mas pode ser útil em outros lugares).
    """
    try:
        aba = get_aba("oportunidades")
        todos = aba.get_all_records()

        owner_busca = str(proprietario).strip().lower()
        resultados = []

        for registro in todos:
            owner_registro = str(registro.get("proprietario", "")).strip().lower()
            if owner_registro == owner_busca:
                resultados.append(registro)

        return resultados  # retorna lista de oportunidades do proprietário

    except Exception as e:
        print(f"Erro ao buscar oportunidades do proprietário: {e}")
        return []

def listar_opp_por_owner_paginado(proprietario, pagina=1, limite=10):
    """
    Lista oportunidades paginadas. 
    Importante: Esta função já retorna o 'id' no dicionário 'registro',
    pois 'cabecalho' contém 'id'. Nenhuma mudança necessária aqui.
    """
    aba = get_aba("oportunidades")
    valores = aba.get_all_values()

    # Verifica se há dados suficientes
    if not valores or len(valores) < 2:
        return []

    cabecalho = valores[0]
    dados = valores[1:]

    proprietario = proprietario.strip().lower()

    # Filtra as linhas do proprietário atual
    dados_filtrados = []
    for linha in dados:
        if len(linha) < len(cabecalho):
            continue

        registro = dict(zip(cabecalho, linha))
        dono = registro.get("proprietario", "").strip().lower()

        if dono == proprietario:
            dados_filtrados.append(registro)

    # Paginação
    inicio = (pagina - 1) * limite
    fim = inicio + limite
    return dados_filtrados[inicio:fim]

def ajustar_escala(valor,escala):
        """Converte valor em centavos (int) para valor em Reais (float)."""
        # Aceita números inteiros/float ou strings numéricas (ex: '12345')
        if valor is None or valor == "":
            return valor
        try:
            # tenta converter para float (aceita strings numéricas)
            numeric = float(valor)
            return numeric / escala
        except (ValueError, TypeError):
            # Se não for numérico, retorna o valor original
            return valor

def salvar_oportunidade(dados_opp):
    """
    Salva uma nova oportunidade a partir de um dicionário de dados.
    """
    kwpFormatado = ajustar_escala(dados_opp.get("kwp"),100)
    valorParcelaFormatado = ajustar_escala(dados_opp.get("valorParcela"),100)
    id, codigo = auth.gerar_identificador("oportunidade")
    # A ordem aqui é CRUCIAL, pois deve bater com a ordem das colunas na planilha.
    # Usamos .get() para evitar erros caso uma chave não exista,
    # definindo um valor padrão (como "").
    linha_para_salvar = [
    id,
    codigo,
    dados_opp.get("nome"),
    dados_opp.get("email"),
    dados_opp.get("descricao"),
    dados_opp.get("potencia"),
    dados_opp.get("valor"),
    dados_opp.get("proprietario"),
    dados_opp.get("datacad"),
    dados_opp.get("cliente_id", ""),
    dados_opp.get("link_arquivo", ""),
    dados_opp.get("link_conta_energia", ""),
    dados_opp.get("estado"),
    dados_opp.get("pacote"),
    kwpFormatado,
    dados_opp.get("kw"),
    dados_opp.get("inversor"),
    dados_opp.get("wpPainel"),
    dados_opp.get("unidadePainel"),
    dados_opp.get("espacoFisico"),
    dados_opp.get("preco"),
    dados_opp.get("juros"),
    valorParcelaFormatado,
    dados_opp.get("valorJuros")
]

    get_aba("oportunidades").append_row(linha_para_salvar)
# -----------------------------------------------------------------

# -----------------------------------------------------------------
# FUNÇÃO ANTIGA (Depreciada, substituída por 'atualizar_oportunidade_anexo_por_id')
# -----------------------------------------------------------------
def atualizar_oportunidade_anexo(email, proprietario, link_arquivo, datacad=None):
    """
    [DEPRECIADA para o fluxo 'Continuar']
    Atualiza a oportunidade usando email, proprietário  e data como chave.
    Substituída por 'atualizar_oportunidade_anexo_por_id'.
    """
    try:
        aba = get_aba("oportunidades")
        valores = aba.get_all_values()

        if not valores or len(valores) < 2:
            print("Nenhum registro encontrado para atualização.")
            return False

        cabecalho = [h.strip().lower() for h in valores[0]]
        linhas = valores[1:]

        # Localiza índices das colunas
        col_link = cabecalho.index("link") + 1
        col_estado = cabecalho.index("estado") + 1

        email_busca = str(email).strip().lower()
        owner_busca = str(proprietario).strip().lower()
        data_busca = str(datacad).strip() if datacad else None

        for i, linha in enumerate(linhas, start=2):
            registro = dict(zip(cabecalho, [x.strip() for x in linha]))
            email_registro = registro.get("email", "").lower()
            owner_registro = registro.get("proprietario", "").lower()
            data_registro = registro.get("datadecriacao", "").strip()

            if (
                email_registro == email_busca
                and owner_registro == owner_busca
                and (not data_busca or data_registro == data_busca)
            ):
                aba.update_cell(i, col_link, link_arquivo)
                aba.update_cell(i, col_estado, "Em análise")
                print(f"Oportunidade atualizada na linha {i}.")
                return True

        print("Nenhuma oportunidade correspondente encontrada para atualizar.")
        return False

    except Exception as e:
        print(f"Erro ao atualizar oportunidade: {e}")
        return False

# -----------------------------------------------------------------
# NOVA FUNÇÃO (Refatoração por ID)
# -----------------------------------------------------------------
def atualizar_oportunidade_anexo_por_id(id_opp, link_arquivo):
    """
    Atualiza o link e o estado de uma oportunidade usando seu ID.
    Usado no fluxo 'Continuar Oportunidade'.
    """
    try:
        aba = get_aba("oportunidades")
        valores = aba.get_all_values()

        if not valores or len(valores) < 2:
            print("Nenhum registro encontrado para atualização.")
            return False

        cabecalho = [h.strip().lower() for h in valores[0]]
        linhas = valores[1:]

        # Localiza índices das colunas (0-indexado para listas)
        try:
            col_id_idx = cabecalho.index("id")
            col_documento_idx = cabecalho.index("documento")
            col_comprovante_idx = cabecalho.index("comprovante")
            col_estado_idx = cabecalho.index("estado")
        except ValueError as e:
            print(f"Erro: Coluna não encontrada no cabeçalho - {e}")
            return False

        id_busca = str(id_opp).strip()

        # Itera pelas linhas de dados (índice 'i' começa em 2 para gspread)
        for i, linha in enumerate(linhas, start=2): 
            if len(linha) <= col_id_idx: # Proteção contra linha mal formatada
                 continue
            
            id_registro = linha[col_id_idx].strip() # Pega o ID da linha

            if id_registro == id_busca:
                # Achou! Atualiza as colunas (colunas são 1-indexadas no update_cell)
                # Adiciona +1 aos índices 0-indexados
                aba.update_cell(i, col_documento_idx + 1, link_arquivo.get("link_documento"))
                aba.update_cell(i, col_comprovante_idx + 1, link_arquivo.get("link_conta_energia"))
                aba.update_cell(i, col_estado_idx + 1, "Em análise")
                print(f"Oportunidade (ID: {id_opp}) atualizada na linha {i}.")
                return True

        print(f"Nenhuma oportunidade com ID {id_opp} encontrada para atualizar.")
        return False

    except Exception as e:
        print(f"Erro ao atualizar oportunidade por ID ({id_opp}): {e}")
        return False
# -----------------------------------------------------------------

def enviar_arquivo_drive(caminho_local, nome_arquivo, pasta_id=None):
    service = build("drive", "v3", credentials=creds)

    metadata = {"name": nome_arquivo}
    if pasta_id:
        metadata["parents"] = [pasta_id]

    media = MediaFileUpload(caminho_local, resumable=True)
    file = service.files().create(
        body=metadata,
        media_body=media,
        fields="id"
    ).execute()

    file_id = file.get("id")

    # Deixa o arquivo visível via link
    service.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()

    return f"https://drive.google.com/file/d/{file_id}/view"

def listar_user_por_id(user_id):
    try:
        aba = get_aba("usuarios")
        todos = aba.get_all_records()

        for u in todos:
            if str(u.get("id")) == str(user_id):
                # Remove campo de senha antes de retornar
                u.pop("senha", None)
                return u
        return None
    except Exception as e:
        print("Erro ao listar usuário por ID:", e)
        return None