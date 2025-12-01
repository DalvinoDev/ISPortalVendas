import sheets  #centraliza Google Sheets
import uuid
import hashlib
import random
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

def cadastrar_usuario(email, senha, nome, sobrenome, cidade, telefone):
    senha_hash = generate_password_hash(senha)
    usuarios = sheets.listar_usuarios()

    # Verifica se o email já está cadastrado
    for u in usuarios:
        if u["email"] == email:
            return False

    # Salva todos os dados na planilha
    sheets.salvar_usuario(
        email=email,
        senha_hash=senha_hash,
        ativo=False,
        nome=nome,
        sobrenome=sobrenome,
        cidade=cidade,
        telefone=telefone
    )
    return True

# auth.py (substituir a função validar_login existente por esta)
def validar_login(email, senha):
    usuarios = sheets.listar_usuarios()
    for u in usuarios:
        # normaliza o email para comparar (evita espaços e maiúsculas)
        if str(u.get("email", "")).strip().lower() == str(email).strip().lower():
            # verifica ativo (tolerante a True/TRUE/"true")
            ativo = u.get("ativo", False)
            if not (str(ativo).lower() == "true" or ativo is True):
                return None  # usuário inativo

            # checa senha — trata chaves: 'senha' ou 'senha_hash'
            senha_armazenada = u.get("senha") or u.get("senha_hash") or ""
            try:
                if check_password_hash(senha_armazenada, senha):
                    # pega o campo de acesso com tolerância a maiúsculas/minúsculas
                    nivel = u.get("acesso") or u.get("Acesso") or u.get("nivel") or "Visitante"
                    nivel = str(nivel).strip()
                    return {"id": u.get("id"), "acesso": nivel}
            except Exception as e:
                # se houver qualquer problema com o hash, falha o login
                return None
    return None

def gerar_identificador(tipo_registro="geral"):

    # 1UUID técnico — garante unicidade global
    id_unico = str(uuid.uuid4())

    # Seed única derivada de UUID + timestamp
    seed_base = f"{id_unico}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    hash_seed = hashlib.sha1(seed_base.encode()).hexdigest().upper()

    # Código curto (3 letras de tipo + 4 dígitos + 3 chars aleatórios)
    prefixo = tipo_registro[:3].upper()
    numero_rand = random.randint(1, 9999)
    sufixo_hash = hash_seed[:3]
    codigo_amigavel = f"{prefixo}-{str(numero_rand).zfill(4)}-{sufixo_hash}"

    return id_unico, codigo_amigavel
