# Nexar

Nexar e um sistema Django para consultar um veiculo pela placa e exibir pecas compativeis cadastradas no catalogo.

## O que esta pronto

- Projeto Django com SQLite.
- Pagina publica de busca por placa.
- Cadastro de modelos/aplicacoes de veiculos, sem depender de placa.
- Cadastro de categorias de pecas pelo painel.
- Cadastro de pecas.
- Vinculo de compatibilidade entre pecas e veiculos.
- Painel protegido por senha especial.
- Integracao preparada para uma API externa de placas.
- Fallback com dados mockados enquanto a API real nao estiver configurada.

## Rodando o projeto

Instale as dependencias:

```bash
python -m pip install -r requirements.txt
```

Crie/atualize o banco:

```bash
python manage.py migrate
```

Opcionalmente, carregue dados demo do Voyage:

```bash
python manage.py seed_demo
```

Inicie o servidor:

```bash
python manage.py runserver
```

Acesse:

```text
http://127.0.0.1:8000/
```

## Painel protegido

O painel fica em:

```text
http://127.0.0.1:8000/painel/
```

Senha inicial:

```text
34260120
```

Essa senha pode ser alterada por variavel de ambiente:

```bash
NEXAR_STAFF_PASSWORD=outra-senha
```

## Como cadastrar pecas e compatibilidades

1. Acesse `/painel/`.
2. Entre com a senha especial.
3. Cadastre um modelo em "Novo modelo", por exemplo Volkswagen Voyage 1.6 MSI Comfortline.
4. Cadastre categorias em "Nova categoria", como Oleo, Filtro de ar ou Bieleta.
5. Cadastre uma peca em "Nova peca".
6. No cadastro da peca, marque os modelos compativeis.

Quando uma placa retornar um modelo cadastrado, a pagina publica exibira as pecas corretas para aquele modelo. A placa em si nao precisa estar cadastrada.

## Consulta de placa

O arquivo principal da integracao e:

```text
catalog/services.py
```

Por padrao, o Nexar usa dados de teste. Para usar uma API real, configure:

```bash
NEXAR_PLATE_API_URL=https://sua-api.com/consulta
NEXAR_PLATE_API_TOKEN=seu-token
```

O Nexar envia a placa como query string:

```text
https://sua-api.com/consulta?placa=ABC1D23
```

Se a API escolhida usar outro formato, ajuste `lookup_plate_from_configured_api`.

## Sobre BrasilAPI, Sinesp e FIPE

- BrasilAPI nao possui hoje um endpoint publico estavel de consulta de placa. Existe uma issue antiga pedindo isso: https://github.com/BrasilAPI/BrasilAPI/issues/137
- Sinesp Cidadao existe como solucao/app do governo, mas nao encontrei documentacao publica oficial de API REST para uso direto por sistemas terceiros: https://www.gov.br/mj/pt-br/assuntos/sua-seguranca/seguranca-publica/diretoria-de-gestao-e-integracao-de-informacoes-1/produtos/sinesp_cidadao
- A API FIPE do DeividFortuna serve para marcas, modelos, anos e valores FIPE, nao para consultar veiculo por placa: https://deividfortuna.github.io/fipe/

Na pratica: para placa real em producao, provavelmente voce vai precisar contratar/configurar um provedor de consulta de placas, ou obter acesso autorizado a uma fonte oficial. O Nexar ja esta preparado para receber essa URL e token.

## Placas de teste

Enquanto nao houver API real:

- `ABC1D23`: Volkswagen Voyage 1.6 MSI Comfortline
- `BRA2E19`: Chevrolet Onix 1.0 LT
- `NXR0A01`: Fiat Argo 1.3 Drive
