# Mapeamento das implementações de referência

Este documento registra a relação entre as duas implementações usadas como
base e o código deste repositório (`nfv-mano`), explicando o que foi
aproveitado, o que foi alterado e por quê.

## 1. Implementações de referência

### 1.1 `giovannivenancio/nham` — NFV High-Availability Module

- **Linguagem:** Python 2.
- **Comunicação:** APIs REST com Flask + Eve, persistência em *arquivos
  texto* (`nfv-mano/utils.py`, diretório `../db/`).
- **Blocos:** `nfvo.py` (9002), `vnfm.py` (9001), `vim.py` (9000, Docker),
  `sff.py` (9004, Service Function Forwarder), `sfc_enabler.py` (TCP 10000),
  `nham/sm.py` (State Manager, 9003) e `nham/fms.py` (Fault Management System).
- **Foco:** cadeias de serviços (SFC) com **alta disponibilidade por VNF**.
  O VNFD traz requisitos de resiliência (`num_backups`, `cooldown`,
  `vnf_level`) e métodos de recuperação **0R, 1R-AS, 1R-AA e MR-AA**.
- **Tolerância a falhas (nível VNF):** `fms.py` detecta falhas (status do
  container + `ping`) e recupera; `sm.py` faz *checkpoint* de memória do
  processo da VNF via `ptrace` (dump/restore) para sincronizar estado.

### 1.2 `aodoan/tcc` — projeto `nfv`

- **Linguagem:** Python 3.
- **Comunicação:** barramento de mensagens **RabbitMQ** (`pika`) com exchanges
  `fanout` (`vim-exchange`, `nfvo-exchange`, `vnfm-exchange`,
  `nfv-gateway-exchange`, `fwd-exchange`, `vnf-control`, `ids-exchange`).
- **Blocos:** `mano/nfvo.py`, `mano/vnfm.py`, `mano/vim.py`,
  `gateway/gateway.py`, `sfc/sfc.py`, `vnf/` (VNF em container TCP),
  `client/client.py` (CLI/status via heartbeat) e `ids/` (detecção de
  anomalias).
- **Foco:** SFC executável de ponta a ponta, com VIM que sobe containers
  Docker e o VNFM que calcula o *forward graph* da cadeia.
- **Tolerância a falhas:** não há; apenas *heartbeat* por módulo para status.

## 2. Tabela de correspondência

| Conceito ETSI | `nham` | `aodoan/tcc` | `nfv-mano` (este) |
| --- | --- | --- | --- |
| NFVO | `nfv-mano/nfvo.py` (REST) | `mano/nfvo.py` (RabbitMQ) | `nfvo.py` (REST `Os-Ma-nfvo`) |
| VNFM | `nfv-mano/vnfm.py` | `mano/vnfm.py` | `vnfm.py` (REST `Or-Vnfm`) |
| VIM | `nfv-mano/vim.py` | `mano/vim.py` | `vim.py` (REST `Vi-Vnfm` + driver `Nf-Vi`) |
| Catálogo VNF/NS | implícito em `nfv-mano/utils.py` | implícito no NFVO | `repositories.py` (`vnf_catalog`, `ns_catalog`) |
| Instâncias | arquivos `../db/vnf`, `../db/sfc` | dicionários em memória | `repositories.py` (`vnf_instances`, `ns_instances`) |
| Recursos NFVI | arquivo `../db/device` | lista `running_containers` | `vim.py` (`VimManager`) + `nfvi_resources` |
| Orquestração de NS | `nfvo.py::create_sfc` | `nfvo.py::create_sfc` | `nfvo.py::instantiate_ns` |
| LCM de VNF | `vnfm.py::create_vnf` | `vnfm.py::create_vnf` | `vnfm.py::instantiate_vnf` |
| Alocação NFVI | `vim.py::create_virtual_device` | `vim.py::start_container` | `vim.py::allocate_compute` |
| Driver NFVI | Docker direto no VIM | Docker direto no VIM | `vim.py` (`MockDriver`/`DockerDriver`) |
| Cliente/CLI | `bin/client` | `client/client.py` | `nfv-mano serve` / `nfv-mano demo` |
| Tolerância a falhas | `nham/fms.py` + `nham/sm.py` | ausente | **trabalho futuro** (ver doc dedicado) |
| SFC / forwarding | `sff.py`, `sfc_enabler.py` | `sfc/`, `gateway/` | **fora do escopo base** |
| IDS | — | `ids/` | **fora do escopo base** |

## 3. O que foi aproveitado de cada uma

Do **`nham`**:

- A separação clara nos três blocos do MANO e a nomenclatura dos métodos de
  recuperação (0R/1R-AS/1R-AA/MR-AA), documentada como referência do trabalho
  futuro de tolerância a falhas.
- A ideia de persistir o estado do MANO fora da memória (lá, arquivos; aqui,
  uma abstração de repositório com backends) — pré-requisito para replicação.
- O conceito de reconciliação de saúde usado no FMS, que inspira o
  comportamento específico do VIM descrito no doc de tolerância a falhas.

Da implementação do **ex-aluno (`aodoan/tcc`)**:

- A organização modular por bloco (`mano/`, `sfc/`, `vnf/`, `gateway/`), que
  foi mantida como `nfvo.py`, `vnfm.py`, `vim.py`, `repositories.py` e
  `models.py`.
- O uso de **containers Docker** como NFVI (agora isolado atrás de um driver).
- O VNFM como ponto que resolve o *forward graph* da cadeia — aqui
  simplificado para a composição de instâncias de VNF do NSD.
- O comando de **status via heartbeat**, generalizado para `/health` em cada
  reference point.

## 4. Mudanças deliberadas e justificativa

| Decisão | Antes (refs) | Agora | Motivo |
| --- | --- | --- | --- |
| Transporte | RabbitMQ (`pika`) ou Eve/REST ad hoc | **REST/FastAPI** padronizado por reference point | Alinha aos reference points ETSI, facilita documentação, testes e evolui para os schemas SOL. |
| Versão do Python | 2 (`nham`) / 3 (`aodoan`) | **3.12 gerenciado por `uv`** | Reproducibilidade e dependências modernas (pydantic v2). |
| Persistência | arquivos texto / dicts em memória | **interface `Repository[T]`** com backends `memory` e `file` | Ponto único de troca para um backend replicado (etcd/Raft) no futuro. |
| NFVI | Docker acoplado ao VIM | **driver `Nf-Vi`** (`mock`/`docker`) | Permite rodar e testar sem Docker e trocar de tecnologia sem tocar no VIM. |
| Modelos de dados | dicionários soltos | **modelos pydantic** alinhados ao IFA/SOL | Validação, tipagem e documentação automática (OpenAPI). |
| Erros | exceções/`print` genéricos | **hierarquia de exceções** mapeada para HTTP | Respostas consistentes nos reference points. |
| Escopo | SFC + gateway + IDS | **somente NFV-MANO** | Isolar o objeto da Proposta 0.1 (MANO tolerante a falhas) antes de reintroduzir a cadeia de serviço. |

## 5. Fora do escopo do protótipo base

Os itens abaixo existem nas referências e ficam para etapas posteriores:

- **SFC / Service Function Forwarding** (`sff.py`, `sfc/`, `gateway/`):
  exige uma etapa de encadeamento e um plano de dados que não faz parte da
  Proposta 0.1 inicial.
- **IDS / detecção de anomalias** (`ids/`): ortogonal ao MANO.
- **`Ve-Vnfm-vnf`** e **`Or-Vi`** completos: interação direta com a VNF e
  orquestração de recursos entre múltiplos VIMs.
- **Tolerância a falhas**: tratada em
  [`requisitos-tolerancia-falhas.md`](./requisitos-tolerancia-falhas.md).

## 6. Como o `nfv-mano` reaproveita a estrutura das referências

```
nham/nfv-mano/{nfvo,vnfm,vim}.py      aodoan/{mano,sfc,vnf}/
            |                                   |
            +----------------+------------------+
                             v
                     src/nfv_mano/
                       nfvo.py   vnfm.py   vim.py   repositories.py   models.py
```

O protótipo base mantém o mesmo recorte de blocos, mas com fronteiras
explícitas (reference points REST), estado isolado em repositórios e a NFVI
escondida atrás de drivers — as três condições necessárias para, na próxima
fase, replicar os blocos e o estado com Raft/etcd.
