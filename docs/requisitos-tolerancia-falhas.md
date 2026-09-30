# Requisitos de tolerância a falhas do NFV-MANO

Este documento discute os requisitos de tolerância a falhas para uma
**Proposta 0.1 de arquitetura NFV-MANO tolerante a falhas** e como o protótipo
base foi preparado para recebê-la. A tolerância a falhas em si é **trabalho
futuro**; o objetivo agora é deixar o *seam* (ponto de extensão) correto.

> Referência de trabalho futuro:
> *Fault-Tolerant NFV MANO* (<https://ieeexplore.ieee.org/abstract/document/9459426>).

## 1. Contexto

No protótipo base, NFVO, VNFM e VIM são processos únicos e *stateful*. Se
qualquer um deles cair, o plano de controle do MANO fica indisponível e o
estado em memória é perdido. Uma arquitetura tolerante a falhas precisa:

1. **Detectar** a falha de um bloco (liveness).
2. **Eleger** uma réplica ativa entre as saudáveis (evitar cérebro dividido).
3. **Replicar** as decisões de estado de forma consistente (consenso).
4. **Reconciliar** o estado derivável com a infraestrutura (recuperação).

## 2. Modelo de falhas

Consideramos inicialmente falhas do tipo *crash-stop* (o processo para e não
volta sozinho), não falhas bizantinas. Esse é o modelo atendido por algoritmos
de consenso como o **Raft** e por armazenamentos distribuídos como o **etcd**.

O plano de dados (as VNFs em execução) **não** deve depender da disponibilidade
do MANO: a queda do plano de controle não pode derrubar tráfego existente.

## 3. Inventário de estado (o que precisa ser replicado)

| Bloco | Estado | Natureza | Consistência necessária |
| --- | --- | --- | --- |
| NFVO | Catálogos VNFD/NSD | Configuração autoritativa | Forte (consenso) |
| NFVO | Instâncias de NS e decisões de LCM | Autoritativo | Forte (consenso) |
| NFVO | Mapa NS → instâncias de VNF | Autoritativo | Forte (consenso) |
| VNFM | Instâncias de VNF e operações de LCM | Autoritativo | Forte (consenso) |
| VNFM | Mapa VNF → recursos de NFVI | Autoritativo (decisão) | Forte (consenso) |
| VIM | Inventário de recursos de NFVI | **Derivável da NFVI** | Eventual (reconciliação) |
| VIM | Registro de VIMs e políticas | Configuração | Forte (consenso) |

A distinção entre **estado autoritativo** (não reconstruível) e **estado
derivável** (reconstruível a partir da infraestrutura) é o ponto central para
tratar NFVO/VNFM e VIM de forma diferente.

## 4. Raft e etcd

O **Raft** (<https://raft.github.io/>) é um algoritmo de consenso para
máquinas de estado replicadas: um líder recebe as operações, replica o log
para a maioria (*quorum*) e as réplicas aplicam os comandos na mesma ordem.
Com 3 réplicas, tolera 1 falha; com 5, tolera 2.

O **etcd** (<https://etcd.io/>) é um armazenamento chave-valor distribuído que
usa Raft internamente. Ele oferece os primitivos necessários para o MANO:
eleição de líder, *lease* (liveness), transações, *watch* e leitura
linearizável.

Proposta de encaixe: transformar as operações de LCM do MANO em **comandos
replicados** aplicados a uma máquina de estado, persistida no etcd. As
decisões (criar instância, alocar recurso) são registradas via consenso antes
de serem consideradas efetivas.

## 5. Requisitos por bloco

### NFVO e VNFM

- **Autoritativo:** não é possível reconstruir de outra fonte. Exige consenso
  (Raft/etcd) para evitar divergência entre réplicas.
- **Réplicas ativas-passivas ou ativas-ativas** com eleição de líder por
  bloco; apenas o líder aceita operações de escrita.
- **Idempotência de operações de LCM:** cada operação tem um `id` e um estado
  (`LcmOperationOccurrence`), permitindo *retry* após falha sem duplicar
  efeitos.
- **Detecção:** liveness via `/health` ou *lease* no etcd.

### VIM — comportamento diferente

O VIM **não deve ser tratado como o NFVO/VNFM**. Requisitos específicos:

1. **Estado derivável.** O inventário de recursos pode ser reconstruído
   perguntando diretamente à NFVI (Docker/OpenStack). Portanto, o VIM pode usar
   **reconciliação** (eventual consistency) em vez de consenso para o
   inventário: ao reiniciar, ele re-sincroniza o estado com a infraestrutura.
2. **Fronteira com o plano de dados.** A falha do VIM bloqueia **novas**
   alocações, mas as VNFs em execução continuam funcionando. O VIM não precisa
   estar sempre disponível para manter o serviço.
3. **Domínios administrativos distintos.** A NFVI pode estar distribuída em
   vários *hosts*/*PoPs*. Um grupo de consenso global não escala bem; o
   natural é um **agente por domínio** com reconciliação local e um líder por
   domínio para evitar alocação duplicada (*split-brain*).
4. **Tolerar falhas da própria NFVI.** O VIM precisa lidar com *hosts* que
   caem — falhas externas e não apenas *crash-stop* do próprio VIM.
5. **Operações idempotentes.** Como a reconciliação pode repetir operações,
   `allocate`/`terminate` precisam ser idempotentes (o driver já trata
   `terminate` de recurso inexistente de forma tolerante em
   `vim/drivers/docker_driver.py`).

Resumo: **NFVO/VNFM exigem consenso forte; o VIM exige reconciliação
idempotente e particionamento por domínio.** Ambos, porém, precisam de
detecção de falha e recuperação do líder.

## 6. Recuperação de VNF vs. recuperação do MANO

O `nham` implementa alta disponibilidade **no nível da VNF** (por exemplo,
réplicas ativas/standby), com *checkpoint* de memória do processo. Isso é
ortogonal à tolerância a falhas **do MANO** tratada aqui:

| Nível | Objetivo | Método (referência `nham`) |
| --- | --- | --- |
| VNF | Serviço continua mesmo com falha de uma VNF | `0R`, `1R-AS`, `1R-AA`, `MR-AA`, checkpoint via `ptrace` |
| MANO | Plano de controle continua com falha de uma réplica | Consenso (Raft/etcd) + eleição de líder + reconciliação |

Ambos podem coexistir: o MANO tolerante a falhas garante que a orquestração
sobreviva, enquanto a resiliência por VNF garante o serviço.

## 7. Ponto de extensão no código

A decisão de projeto central é que **todo** acesso a estado passa por
`repositories/base.py::Repository`. Trocar o backend não afeta NFVO, VNFM ou
VIM:

```python
class Repository[T: BaseModel](ABC):
    def add(self, entity: T) -> T: ...
    def get(self, entity_id: str) -> T: ...
    def update(self, entity: T) -> T: ...
    def delete(self, entity_id: str) -> None: ...
    def list(self) -> list[T]: ...
```

Plano:

1. Implementar `EtcdRepository` com a mesma interface
   (`repositories/backends/etcd.py`).
2. Aplicar LCM como comandos replicados (log Raft) em vez de escritas diretas.
3. Adicionar eleição de líder por bloco (lease no etcd) e *failover*.
4. Para o VIM, adicionar um laço de **reconciliação** que reconstrói
   `nfvi_resources` a partir do driver.

## 8. Métricas de avaliação (fase de validação)

- Tempo de detecção e de *failover* do líder.
- Disponibilidade do plano de controle sob injeção de falhas (`kill` da
  réplica líder, partição de rede).
- Consistência: ausência de operações duplicadas após *retry*.
- Comparação com a linha de base sem tolerância a falhas (este protótipo).

## 9. Fases de evolução

| Fase | Entrega |
| --- | --- |
| **0 (atual)** | MANO sem tolerância a falhas, com estado atrás de `Repository`. |
| 1 | Backend `etcd` (Raft) + LCM como comandos replicados no NFVO/VNFM. |
| 2 | Eleição de líder e *failover* por bloco; liveness via lease. |
| 3 | VIM com reconciliação idempotente e particionamento por domínio. |
| 4 | Avaliação com injeção de falhas e comparação com a linha de base. |

## 10. Referências do tema

- Raft: <https://raft.github.io/> e paper *In Search of an Understandable
  Consensus Algorithm* (<https://raft.github.io/raft.pdf>).
- etcd: <https://etcd.io/>.
- Trabalho futuro: *Fault-Tolerant NFV MANO*,
  <https://ieeexplore.ieee.org/abstract/document/9459426>.
