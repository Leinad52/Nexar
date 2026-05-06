# Nexar

Nexar e um sistema Django para consultar um veiculo pela placa e exibir pecas compativeis cadastradas no catalogo.

## O que esta pronto

- Projeto Django com SQLite.
- Pagina publica de busca por placa.
- Cadastro de modelos/aplicacoes de veiculos, sem depender de placa.
- Cadastro de categorias de pecas pelo painel.
- Cadastro de pecas.
- Importacao de pecas por XML de NF-e.
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

## Importando pecas por XML

No painel, use o botao "Importar XML" para enviar um arquivo XML de NF-e.

O Nexar importa somente os itens da nota em `det > prod`, ignorando dados de emitente, destinatario, CNPJ, impostos e cobranca.

Campos aproveitados:

- `xProd`: usado para separar codigo e nome da peca. Exemplo: `PD60-PASTILHA FREIO`.
- `cEAN`: codigo de barras.
- `NCM`: classificacao fiscal.
- `uCom`: unidade.
- `qCom`: ultima quantidade comprada.
- `vUnCom`: ultimo custo unitario.
- `vProd`: ultimo total comprado.
- `cProd`: guardado nas observacoes como codigo do fornecedor.

Se uma peca com o mesmo codigo ja existir, ela sera atualizada. Se nao existir, sera criada.

## Consulta de placa

O arquivo principal da integracao e:

```text
catalog/services.py
```

Por padrao, o Nexar usa dados de teste. Para usar uma API real, configure:

```bash
NEXAR_PLATE_API_PROVIDER=fipeapi
NEXAR_PLATE_API_URL=https://placas.fipeapi.com.br/placas/{placa}
NEXAR_PLATE_API_TOKEN=sua-api-key
```

Para o provedor `fipeapi`, o Nexar envia:

```http
GET /placas/ABC1D23?key=sua-api-key
```

O Nexar entende a resposta da FipeAPI em `data.veiculo` e usa a primeira opcao de `data.fipes` para codigo FIPE, marca e versao.

Tambem existe suporte aos provedores `placafipe`, `placafipeonline` e `generic_get`.

Se voce quiser usar uma API GET generica, defina:

```bash
NEXAR_PLATE_API_PROVIDER=generic_get
NEXAR_PLATE_API_URL=https://sua-api.com/consulta
```

Nesse modo, o Nexar envia `?placa=ABC1D23`.

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
