// Consolidated site script: form validation, menu, masks, CEP lookup
document.addEventListener("DOMContentLoaded", function () {
    // Adiciona loading spinner a todos os forms ao submeter
    var forms = document.querySelectorAll('form');
    forms.forEach(function(form) {
        form.addEventListener('submit', function() {
            mostrarLoading('Salvando...');
        });
    });

    // Form de cadastro: validação simples de senha (se campos existirem)
    var formCadastro = document.getElementById("formCadastro");
    if (formCadastro) {
        var senha = document.getElementById("senha");
        var confirmarSenha = document.getElementById("confirmarSenha");
        var mensagemErro = document.getElementById("mensagemErro");

        formCadastro.addEventListener("submit", function(event) {
            if (senha && confirmarSenha && mensagemErro) {
                senha.classList.remove("input-error");
                confirmarSenha.classList.remove("input-error");
                mensagemErro.classList.add("hidden");

                if (senha.value !== confirmarSenha.value) {
                    senha.classList.add("input-error");
                    confirmarSenha.classList.add("input-error");
                    mensagemErro.classList.remove("hidden");
                    event.preventDefault();
                }
            }
            // Before submit, remove masks from cpf/cep/telefone so server gets digits
            limparCpfCep();
            limparMascara();
        });
    }

    // Menu lateral
    var body = document.body;
    var menuToggle = document.getElementById('menuToggle');
    var sideMenu = document.getElementById('sideMenu');
    var mainContent = document.getElementById('mainContent');

    if (menuToggle) {
        menuToggle.addEventListener('click', function (event) {
            event.stopPropagation();
            body.classList.toggle('menu-open');
        });
    }

    if (mainContent) {
        mainContent.addEventListener('click', function () {
            body.classList.remove('menu-open');
        });
    }

    if (sideMenu) {
        sideMenu.addEventListener('click', function () {
            body.classList.remove('menu-open');
        });
    }

    // CEP: botão de busca (se existir) e limpeza de mensagens ao digitar
    var cepInput = document.getElementById('cep');
    var buscarCepBtn = document.getElementById('buscarCep');
    if (cepInput) {
        cepInput.addEventListener('input', function () {
            var cepError = document.getElementById('cepError');
            if (cepError) {
                cepError.textContent = '';
                cepError.classList.add('hidden');
            }
            cepInput.classList.remove('ring-2', 'ring-red-500');
            cepInput.removeAttribute('aria-invalid');
        });
    }

    if (buscarCepBtn && cepInput) {
        buscarCepBtn.addEventListener('click', function (e) {
            e.preventDefault();
            buscarCep(cepInput.value);
        });
    }
});

/**
 * Busca CEP na API ViaCEP e preenche campos de endereço.
 * Mostra mensagens inline em #cepError quando há erro.
 */
function buscarCep(cepRaw) {
    var cepInput = document.getElementById('cep');
    var cepError = document.getElementById('cepError');
    var estadoInput = document.getElementById('estado');
    var municipioInput = document.getElementById('municipio');
    var logradouroInput = document.getElementById('logradouro');

    if (!cepInput) return;
    var cep = (cepRaw || cepInput.value || '').replace(/\D/g, '');
    if (cep.length !== 8) {
        if (cepError) {
            cepError.textContent = 'Informe um CEP válido (8 dígitos).';
            cepError.classList.remove('hidden');
            cepInput.classList.add('ring-2', 'ring-red-500');
            cepInput.setAttribute('aria-invalid', 'true');
        } else {
            alert('Informe um CEP válido (8 dígitos).');
        }
        return;
    }

    var url = 'https://viacep.com.br/ws/' + cep + '/json/';
    fetch(url).then(function (resp) {
        if (!resp.ok) throw new Error('Network response was not ok');
        return resp.json();
    }).then(function (data) {
        if (data.erro) {
            if (cepError) {
                cepError.textContent = 'CEP não encontrado.';
                cepError.classList.remove('hidden');
                cepInput.classList.add('ring-2', 'ring-red-500');
                cepInput.setAttribute('aria-invalid', 'true');
            } else {
                alert('CEP não encontrado.');
            }
            // limpa possíveis campos preenchidos
            if (estadoInput) estadoInput.value = '';
            if (municipioInput) municipioInput.value = '';
            if (logradouroInput) logradouroInput.value = '';
            return;
        }

        // sucesso — limpa erro e preenche campos
        if (cepError) {
            cepError.textContent = '';
            cepError.classList.add('hidden');
        }
        cepInput.classList.remove('ring-2', 'ring-red-500');
        cepInput.removeAttribute('aria-invalid');

        if (estadoInput) estadoInput.value = data.uf || '';
        if (municipioInput) municipioInput.value = data.localidade || '';
        if (logradouroInput) logradouroInput.value = data.logradouro || '';
    }).catch(function (err) {
        if (cepError) {
            cepError.textContent = 'Erro ao consultar CEP. Tente novamente.';
            cepError.classList.remove('hidden');
            cepInput.classList.add('ring-2', 'ring-red-500');
            cepInput.setAttribute('aria-invalid', 'true');
        } else {
            alert('Erro ao consultar CEP. Tente novamente.');
        }
    });
}

/**
 * Mascara para telefone (aceita 10 ou 11 dígitos)
 */
function mascaraTelefone(input) {
    if (!input) return;
    var valor = input.value.replace(/\D/g, '');
    valor = valor.slice(0, 11);
    if (valor.length > 6) {
        if (valor.length === 11) {
            valor = valor.replace(/^(\d{2})(\d{5})(\d{4})$/, "($1) $2-$3");
        } else {
            valor = valor.replace(/^(\d{2})(\d{4})(\d{4})$/, "($1) $2-$3");
        }
    } else if (valor.length > 2) {
        valor = valor.replace(/^(\d{2})(\d{1,})$/, "($1) $2");
    } else if (valor.length > 0) {
        valor = "(" + valor;
    }
    input.value = valor;
}

function limparMascara() {
    var inputTelefone = document.getElementById('telefone');
    if (inputTelefone) inputTelefone.value = inputTelefone.value.replace(/\D/g, '');
}

// Limpa máscara de CPF e CEP antes do envio (se existirem)
function limparCpfCep() {
    var inputCep = document.getElementById('cep');
    if (inputCep) inputCep.value = inputCep.value.replace(/\D/g, '');
    var inputCpf = document.getElementById('cpf');
    if (inputCpf) inputCpf.value = inputCpf.value.replace(/\D/g, '');
}

/**
 * Mascara para data no formato DD/MM/YYYY enquanto o usuário digita.
 * Não valida data completa, apenas formata a entrada.
 */
function mascaraData(input) {
    if (!input) return;
    var raw = input.value.replace(/\D/g, '').slice(0, 8);
    var formatted = raw;
    if (raw.length >= 5) {
        formatted = raw.slice(0,2) + '/' + raw.slice(2,4) + '/' + raw.slice(4);
    } else if (raw.length >= 3) {
        formatted = raw.slice(0,2) + '/' + raw.slice(2);
    }
    input.value = formatted;
    try { input.setSelectionRange(input.value.length, input.value.length); } catch (e) {}
}

/**
 * Filtra o catálogo de produtos baseado na seleção do picklist (KWh)
 */
// Filtragem de catálogo removida — volta ao fluxo com apenas dropdowns

/**
 * Seleciona um produto do catálogo e popula o formulário
 */
// Seleção por clique removida — usar dropdown para escolha

/**
 * Limpa a seleção de produto
 */
// limparProduto removed — not applicable in dropdown-only flow

