# Fundação PostgreSQL multi-tenant da Kiara

Status: **baseline de desenvolvimento; ainda não é autorização de produção**  
Responsável: `database-reliability-engineer`  
Data: 2026-09-05

## Resultado

A migration `services/api/migrations/0001_initial_postgres.sql` cria o primeiro schema web para identidade, consumers, conversas, aprovação humana, pipeline, jobs, outbox e auditoria. Ela é atômica, não contém dados reais e usa chaves primárias e estrangeiras compostas para impedir referências cruzadas entre organizações.

`organizations` e `users` são raízes globais e, por definição, não possuem `organization_id`: uma organização é o próprio limite e um usuário pode participar de mais de uma. `memberships` e todas as tabelas de negócio têm `organization_id NOT NULL`. O acesso à organização e ao usuário globais também fica coberto por políticas específicas.

## Contrato de isolamento

Em cada transação autenticada, a aplicação deve executar com parâmetros, nunca com interpolação:

```sql
SET LOCAL app.organization_id = '<uuid verificado da membership>';
SET LOCAL app.user_id = '<uuid canônico verificado>';
```

Se o contexto estiver ausente, `kiara.current_organization_id()` retorna `NULL` e as políticas não autorizam linhas. Todas as tabelas tenant-owned têm `ENABLE ROW LEVEL SECURITY`, `FORCE ROW LEVEL SECURITY`, `USING` para leitura/alteração e `WITH CHECK` para impedir troca de tenant. A role da aplicação não pode ser superuser, ter `BYPASSRLS` ou ser dona das tabelas. A role de migrations deve ser separada e não utilizada pelo runtime.

O teste contratual é estático e deliberadamente não substitui integração com PostgreSQL. Antes de merge para staging, é obrigatório testar com duas organizações e roles reais: SELECT, INSERT, UPDATE de `organization_id`, DELETE, joins, jobs e outbox.

## Operação e mudanças seguras

- Esta é uma migration inicial, executada antes de existir tráfego. O `CREATE EXTENSION pgcrypto` precisa ser autorizado pelo provedor gerenciado.
- Não há migration `down`: remover este schema apagaria dados e não seria uma reversão segura. Rollback de implantação deve reverter o código e manter o schema expandido. Destruição de ambiente efêmero deve ocorrer pela automação do próprio ambiente, após validar o alvo.
- Próximas migrations seguem expand-contract: adicionar coluna nullable, publicar dual-write, backfill em lotes pequenos, validar constraint separadamente e somente remover caminhos antigos em release posterior.
- Índices novos em tabelas populadas usam `CREATE INDEX CONCURRENTLY` fora de bloco transacional, em migration operacional separada e com plano de retry. O arquivo inicial pode criar índices normalmente porque roda em banco vazio.
- Jobs devem ser reclamados com `FOR UPDATE SKIP LOCKED`, lease com expiração, limite de tentativas e transações curtas. Pool de conexão deve usar `SET LOCAL` dentro da mesma transação para não vazar contexto entre requests.

## RPO, RTO e gates antes do piloto

Meta inicial proposta, sujeita a aceite comercial: **RPO ≤ 5 minutos e RTO ≤ 30 minutos**. Não é uma promessa até ser medida.

O provedor PostgreSQL deve oferecer PITR contínuo, backup base diário, cópia fora da região e endpoint estável com failover gerenciado e fencing. A aplicação deve usar pooler em modo transaction, com orçamento de conexões por API e worker e alerta antes de 70% do limite.

Produção permanece bloqueada até existir evidência de:

1. restore da última base + WAL em uma instância descartável, com integridade e RTO medidos;
2. teste de recuperação para um timestamp conhecido dentro do RPO;
3. failover promovendo apenas réplica elegível, sem split-brain, e reconexão da API/worker;
4. teste cross-tenant no PostgreSQL real usando a role de runtime;
5. carga de pool, leases expirados e backlog de outbox;
6. runbooks de restore, failover, credencial comprometida e migration bloqueada.

Backups sem restore comprovado não contam como recuperação. A primeira restauração nunca deve ocorrer durante um incidente real.

## Limitações verificadas

Esta entrega não provisiona PostgreSQL, réplica, pooler, backup, monitoramento nem segredo. Também não executa SQL contra servidor local. Os testes garantem presença estrutural dos controles, não a semântica do parser, locks, permissões ou políticas no engine. Essas validações exigem PostgreSQL efêmero em CI e um restore drill no ambiente gerenciado escolhido.
