# Arquitetura ETSI NFV-MANO

Este repositório é uma versão enxuta de um NFV-MANO em Python, seguindo a
arquitetura da ETSI (GS NFV 002). Por enquanto ele faz o básico e faz sem
tolerância a falhas: consenso (Raft/etcd) e replicação ficam para depois.

## Componentes

São três blocos, cada um em seu próprio processo:

| Bloco | O que faz |
| --- | --- |
| **NFVO** | Guarda os catálogos de VNFD/NSD e conduz o ciclo de vida dos Network Services. |
| **VNFM** | Cuida do ciclo de vida das instâncias de VNF. |
| **VIM** | Aloca os recursos de compute da NFVI, falando com a infraestrutura por um driver. |

O estado não fica solto por aí: tudo passa pelos repositórios ETSI (catálogo de
VNF, catálogo de NS, instâncias e recursos de NFVI), que vivem em
`repositories.py`.

## Reference points

Cada ponto de contato entre os blocos é uma API REST feita com FastAPI:

| Reference point | Liga | Onde está |
| --- | --- | --- |
| `Os-Ma-nfvo` | OSS/BSS ↔ NFVO | `nfvo.py` (`/os/...`) |
| `Or-Vnfm` | NFVO ↔ VNFM | `vnfm.py` (`/or/...`) + `VnfmClient` |
| `Vi-Vnfm` | VNFM ↔ VIM | `vim.py` (`/vi/...`) + `VimClient` |
| `Nf-Vi` | VIM ↔ NFVI | `vim.py` (`MockDriver`/`DockerDriver`) |
| `Ve-Vnfm-em` | EM ↔ VNFM | visão somente leitura em `vnfm.py` (`/ve/...`) |

`Or-Vi` e `Ve-Vnfm-vnf` ainda não entraram no escopo.

## Organização do código

```
src/nfv_mano/
  config.py         # settings (pydantic-settings) e portas
  common.py         # ids, logging, exceções -> HTTP
  models.py         # modelos ETSI e estados de LCM
  repositories.py   # Repository[T] com backends memory/file
  nfvo.py           # NFVO
  vnfm.py           # VNFM
  vim.py            # VIM + drivers Nf-Vi
  cli.py            # comandos serve e demo
```

## Como um NS sobe

1. O cliente bate no NFVO com `POST /os/ns_instances`.
2. Para cada VNFD do NSD, o NFVO pede uma VNF ao VNFM (`POST /or/vnf_instances`).
3. O VNFM pede o recurso ao VIM (`POST /vi/resources`).
4. O VIM aloca no driver `Nf-Vi` e devolve o `NfviResource`.
5. O NFVO responde com a `NsInstance` já como `INSTANTIATED`.

Se algo der errado no meio do caminho, o NFVO desfaz as VNFs que já tinha
criado (rollback), para não deixar lixo para trás.

## Configuração

Dá para ajustar tudo por variáveis de ambiente com o prefixo `NFV_MANO_` ou por
um arquivo `.env`:

| Variável | Padrão | Descrição |
| --- | --- | --- |
| `NFV_MANO_NFVO_HOST` / `_PORT` | `127.0.0.1` / `9002` | Bind do NFVO. |
| `NFV_MANO_VNFM_HOST` / `_PORT` | `127.0.0.1` / `9001` | Bind do VNFM. |
| `NFV_MANO_VIM_HOST` / `_PORT` | `127.0.0.1` / `9000` | Bind do VIM. |
| `NFV_MANO_REPOSITORY_BACKEND` | `memory` | `memory` ou `file`. |
| `NFV_MANO_DATA_DIR` | `data` | Diretório do backend de arquivos. |
| `NFV_MANO_VIM_DRIVER` | `mock` | `mock` ou `docker`. |

## Referências

- ETSI GS NFV 002: Architectural Framework.
- ETSI GS NFV-SOL 001/002/003/005: VNFD, NSD, VNF LCM e NS LCM.
- Raft (<https://raft.github.io/>) e etcd (<https://etcd.io/>), para o trabalho futuro.
