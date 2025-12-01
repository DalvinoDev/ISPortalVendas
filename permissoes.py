# permissoes.py
"""
Módulo central de controle de permissões da aplicação.
Define os papéis (acessos) e suas ações permitidas.
"""

# -----------------------------------------------------------------
# MATRIZ DE PERMISSÕES (Role Matrix)
# -----------------------------------------------------------------
PERMISSOES = {
    "Visitante": {
        "cadastrar_cliente": False,
        "ver_clientes": False,
        "ver_oportunidades": False,
        "gerar_pdf": False,
        "gerenciar_usuarios": False,
        "aprovar_proposta": False,
    },
    "Vendedor": {
        "cadastrar_cliente": True,
        "ver_clientes": True,
        "ver_oportunidades": True,
        "gerar_pdf": False,
        "gerenciar_usuarios": False,
        "aprovar_proposta": False,
    },
    "Projetista": {
        "cadastrar_cliente": True,
        "ver_clientes": True,
        "ver_oportunidades": True,
        "gerar_pdf": True,
        "gerenciar_usuarios": False,
        "aprovar_proposta": True,
    },
    "Estagiário": {
        "cadastrar_cliente": True,
        "ver_clientes": True,
        "ver_oportunidades": False,
        "gerar_pdf": False,
        "gerenciar_usuarios": False,
        "aprovar_proposta": False,
    },
    "Administrador": {
        "cadastrar_cliente": True,
        "ver_clientes": True,
        "ver_oportunidades": True,
        "gerar_pdf": True,
        "gerenciar_usuarios": True,
        "aprovar_proposta": True,
    },
}


# -----------------------------------------------------------------
# Funções utilitárias
# -----------------------------------------------------------------

def verificar_permissao(nivel, acao):
    """
    Retorna True se o 'nivel' tiver permissão para executar 'acao'.
    """
    if not nivel:
        return False
    permissoes = PERMISSOES.get(nivel, {})
    return permissoes.get(acao, False)
