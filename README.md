# Nexar

Nexar e um sistema Django para consultar modelos de veiculos e exibir pecas compativeis cadastradas no catalogo. Ele tambem oferece um painel interno para cadastrar pecas, categorias, modelos, importar produtos de XML/CSV e criar vinculos de aplicacao por busca, PDF ou planilha.

## O que esta pronto

- Projeto Django 5.2 com SQLite.
- Pagina publica de busca por marca, modelo, versao, ano, motor, combustivel ou codigo FIPE.
- Cadastro de modelos/aplicacoes de veiculos, sem depender de placa.
- Cadastro, edicao, listagem, busca e exclusao de categorias, modelos e pecas.
- Cadastro de dados fiscais/comerciais da peca: codigo, EAN, NCM, unidade, ultima quantidade comprada, ultimo custo unitario e ultimo total comprado.
- Importacao de pecas por XML de NF-e ou CSV.
- Vinculo manual de compatibilidade entre pecas e veiculos.
- Vinculo em massa por linhas de busca.
- Vinculo de pecas por tabelas de aplicacao em PDF com texto extraivel, XLSX ou XLSM, com pre-visualizacao antes de aplicar.
- Tela interna para localizar codigos de produtos por nome, marca, categoria, EAN, NCM ou observacao.
- Painel protegido por senha especial em sessao.
- Importacao automatizada de modelos pela API FIPE DeividFortuna/Parallelum.
- Testes automatizados para busca, filtro de pecas, vinculo em massa e importacao de aplicacoes em PDF.

## Estrutura do projeto

```text
catalog/                         app principal
catalog/models.py                modelos Vehicle, Category e Part
catalog/views.py                 telas publicas, painel e fluxos de importacao
catalog/forms.py                 formularios do painel e upload
catalog/xml_importer.py          importacao de pecas por XML NF-e e CSV
catalog/application_importer.py  vinculo de pecas por PDF/XLSX/XLSM
catalog/management/commands/     comandos seed_demo e import_fipe
nexar/settings.py                configuracoes Django e variaveis NEXAR_*
templates/catalog/               templates HTML
static/catalog/styles.css        estilos da interface
```

## Configuracao

Instale as dependencias:

```bash
python -m pip install -r requirements.txt
```

Crie um `.env` a partir do exemplo, se quiser alterar senha ou FIPE:

```bash
copy .env.example .env
```

Variaveis disponiveis:

```bash
NEXAR_STAFF_PASSWORD=34260120
NEXAR_FIPE_API_BASE_URL=https://fipe.parallelum.com.br/api/v2
NEXAR_FIPE_API_VERSION=v2
NEXAR_FIPE_API_TOKEN=
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

Essa senha pode ser alterada no `.env`:

```bash
NEXAR_STAFF_PASSWORD=outra-senha
```

Principais telas do painel:

- `/painel/`: resumo de categorias, modelos e pecas.
- `/painel/categorias/`: listagem e busca de categorias.
- `/painel/modelos/`: listagem e busca de modelos.
- `/painel/pecas/`: listagem, busca e filtro por categoria.
- `/painel/codigos/`: busca rapida de codigos de produtos.
- `/painel/compatibilidades/lote/`: vinculo em massa por buscas de modelos.
- `/painel/pecas/importar-xml/`: importacao de pecas por XML ou CSV.
- `/painel/compatibilidades/pdf/`: vinculo de pecas por PDF, XLSX ou XLSM.
- `/painel/pecas/importar-pdf/`: tela preparada para importacao futura de catalogos de pecas em PDF.

## Como cadastrar pecas e compatibilidades

1. Acesse `/painel/`.
2. Entre com a senha especial.
3. Cadastre um modelo em "Novo modelo", por exemplo Volkswagen Voyage 1.6 MSI Comfortline.
4. Cadastre categorias em "Nova categoria", como Oleo, Filtro de ar ou Bieleta.
5. Cadastre uma peca em "Nova peca".
6. No cadastro da peca, marque os modelos compativeis.

Na pagina publica, pesquise pelo modelo do carro, por exemplo `Voyage 2020`, escolha o resultado exato e o Nexar exibira as pecas vinculadas ao modelo selecionado.

## Vinculo em massa

Use `/painel/compatibilidades/lote/` quando uma mesma peca precisa ser vinculada a varios modelos.

1. Escolha a peca.
2. Digite uma busca por linha, como `Voyage 1.6`, `Gol 2012` ou `Onix LT`.
3. Clique em "Pre-visualizar" para conferir os modelos encontrados.
4. Clique em "Aplicar vinculos" para gravar.

Se marcar "Substituir vinculos existentes desta peca", os vinculos antigos da peca sao removidos antes de adicionar os novos.

## Importando pecas por XML ou CSV

No painel, use "Importar pecas" para enviar um ou mais arquivos XML de NF-e ou CSV de uma vez.

O Nexar importa somente os itens da nota em `det > prod`, ignorando dados de emitente, destinatario, CNPJ, impostos e cobranca.

Campos aproveitados do XML:

- `cProd`: codigo principal do produto, usado no cadastro da peca.
- `xProd`: usado para separar codigo de referencia e nome da peca. Exemplo: `PD60-PASTILHA FREIO`.
- `cEAN`: codigo de barras.
- `NCM`: classificacao fiscal.
- `uCom`: unidade.
- `qCom`: ultima quantidade comprada.
- `vUnCom`: ultimo custo unitario.
- `vProd`: ultimo total comprado.

O codigo que aparece antes do hifen em `xProd`, como `PD60` ou `LX4894`, fica guardado nas observacoes como referencia/modelo do produto. O codigo principal usado pelo Nexar passa a ser o `cProd`, como `124285`.

Se uma peca com o mesmo codigo ja existir, ela sera atualizada. Se nao existir, sera criada. O importador tambem tenta reconhecer pecas existentes por EAN ou pelo codigo de referencia salvo anteriormente.

Para CSV, o Nexar tenta reconhecer colunas comuns, como:

- `codigo`, `cod`, `referencia`, `sku`
- `nome`, `descricao`, `produto`
- `marca`, `fabricante`
- `categoria`, `grupo`, `linha`
- `ean`, `codigo de barras`, `gtin`
- `ncm`
- `unidade`
- `preco`, `valor`, `custo`
- `quantidade`
- `total`

## Vinculando pecas por PDF ou XLSX

No painel, use "Vincular pecas por PDF" para enviar tabelas de aplicacao em `.pdf`, `.xlsx` ou `.xlsm`.

O fluxo recomendado e:

1. Envie o arquivo e clique em "Pre-visualizar".
2. Confira quais pecas e modelos foram encontrados.
3. Se estiver certo, envie o mesmo arquivo e clique em "Aplicar vinculos".

O importador tenta reconhecer colunas comuns de peca e veiculo, como `codigo`, `peca`, `marca`, `modelo`, `versao`, `motor`, `ano`, `ano inicial` e `ano final`. Ele tambem aceita tabelas largas, onde cada linha representa um carro e as colunas seguintes trazem codigos de pecas.

Para PDF, o arquivo precisa ter texto extraivel. Se o PDF for uma imagem escaneada, gere uma versao com OCR ou envie a planilha original.

Observacao: a tela "Importar PDF" em `/painel/pecas/importar-pdf/` ainda e apenas um placeholder para importacao futura de catalogos de pecas. O fluxo funcional hoje para aplicacoes/compatibilidades e "Vincular pecas por PDF".

## Importando modelos pela FIPE

O comando principal e:

```bash
python manage.py import_fipe
```

Por padrao, ele usa a API FIPE v2:

```text
https://fipe.parallelum.com.br/api/v2
```

Tambem e possivel configurar no `.env`:

```bash
NEXAR_FIPE_API_BASE_URL=https://parallelum.com.br/fipe/api/v1
NEXAR_FIPE_API_VERSION=v1
NEXAR_FIPE_API_TOKEN=
```

Configuracao recomendada:

```bash
NEXAR_FIPE_API_BASE_URL=https://fipe.parallelum.com.br/api/v2
NEXAR_FIPE_API_VERSION=v2
NEXAR_FIPE_API_TOKEN=
```

Criando um token gratuito em https://fipe.online, a FIPE informa que o limite sobe de 500 para 1000 requisicoes por 24h. Coloque esse token em `NEXAR_FIPE_API_TOKEN`.

Para testar a importacao FIPE com uma amostra pequena:

```bash
python manage.py import_fipe --brand-limit 1 --model-limit 1
```

Para popular rapidamente marcas e modelos sem consultar anos, use:

```bash
python manage.py import_fipe --catalog-only
```

Esse modo evita a maioria dos erros `429`, porque usa poucas requisicoes. Os modelos entram com ano nao especificado, e depois podem ser enriquecidos aos poucos.

Depois de importar o catalogo rapido, voce pode criar os anos somente para modelos ja existentes:

```bash
python manage.py import_fipe --expand-existing-years --brand-code 59 --sleep 0.5
```

Esse comando cria registros especificos por ano, por exemplo uma entrada generica `VW Voyage` pode virar entradas como `VW Voyage 2018`, `VW Voyage 2019` e `VW Voyage 2020`. Se a entrada generica ja tiver pecas vinculadas, os vinculos sao copiados para os anos criados.

Importante: modelos importados antes desta versao talvez ainda nao tenham os codigos internos da FIPE salvos. Nesse caso, rode novamente o catalogo rapido da marca antes de expandir anos:

```bash
python manage.py import_fipe --brand-code 59 --catalog-only --sleep 0.2
python manage.py import_fipe --expand-existing-years --brand-code 59 --sleep 0.5
```

Se voce ja importou muitos modelos antes dos codigos internos existirem, preencha esses codigos primeiro:

```bash
python manage.py import_fipe --brand-code 59 --backfill-codes --sleep 0.2
python manage.py import_fipe --brand-code 59 --expand-existing-years --sleep 0.5
```

Para importar carros sem limitar marca/modelo:

```bash
python manage.py import_fipe
```

Use com cuidado: a API gratuita tem limite diario e a importacao completa pode fazer muitas requisicoes. O ideal e importar por marcas prioritarias, em vez de puxar o Brasil inteiro de uma vez:

```bash
python manage.py import_fipe --brand-code 59 --catalog-only --sleep 0.2
```

Tambem da para importar varias marcas:

```bash
python manage.py import_fipe --brand-code 59,21,23 --catalog-only --sleep 0.2
```

Na API v1, alguns codigos comuns sao:

- `59`: VW - VolksWagen
- `21`: Fiat
- `23`: GM - Chevrolet
- `25`: Honda
- `56`: Toyota

Se aparecer erro `429 Too Many Requests`, voce atingiu o limite temporario da FIPE. Espere alguns minutos ou rode com uma pausa maior:

```bash
python manage.py import_fipe --sleep 1 --retry-wait 180
```

O comando imprime `Modelo CODIGO - nome` durante a execucao. Se parar no meio, voce pode retomar a partir de uma marca/modelo:

```bash
python manage.py import_fipe --start-brand-code 7 --start-model-code 9785 --sleep 1 --retry-wait 180
```

Outras opcoes uteis:

```bash
python manage.py import_fipe --vehicle-type carros
python manage.py import_fipe --vehicle-type motos
python manage.py import_fipe --vehicle-type caminhoes
python manage.py import_fipe --brand-limit 5 --model-limit 20
python manage.py import_fipe --strategy by_year
python manage.py import_fipe --strategy by_model
python manage.py import_fipe --with-values
```

`--with-values` faz uma consulta extra por ano/modelo para preencher detalhes como `CodigoFipe` e combustivel oficial, entao consome muito mais requisicoes.

Fonte da API FIPE: https://deividfortuna.github.io/fipe/

## Acessando por outros dispositivos na mesma rede

Para acessar o Nexar em celulares, notebooks ou outros computadores da mesma rede, deixe o computador principal ligado e rode o servidor aceitando conexoes externas.

1. Descubra o IP do computador que vai hospedar o Nexar:

```powershell
ipconfig
```

Procure por `Endereco IPv4`, por exemplo:

```text
192.168.100.42
```

2. No arquivo `nexar/settings.py`, adicione esse IP em `ALLOWED_HOSTS`:

```python
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "192.168.100.42"]
```

Se outro computador for virar o host depois, troque esse IP pelo IP dele, ou mantenha os dois:

```python
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "192.168.100.42", "192.168.100.55"]
```

3. Rode o Django assim:

```bash
python manage.py runserver 0.0.0.0:8000
```

4. Nos outros dispositivos da mesma rede, acesse:

```text
http://192.168.100.42:8000/
```

Use `http`, nao `https`.

5. Se nao abrir, libere a porta 8000 no firewall do computador host. No PowerShell como administrador:

```powershell
New-NetFirewallRule -DisplayName "Nexar Django 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Private
```

Para testar a conexao em outro computador:

```powershell
Test-NetConnection 192.168.100.42 -Port 8000
```

Se `TcpTestSucceeded` for `True`, a rede esta chegando no servidor.

## Testes

Rode a suite automatizada com:

```bash
python manage.py test
```

Os testes cobrem busca publica de modelos, filtro de pecas por categoria, vinculo em massa e leitura de aplicacoes em PDF.
