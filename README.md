# dev-pipeline

**Claude Code esquece o que fez. dev-pipeline lembra.**

Plugin para Claude Code que pega um issue do GitHub e entrega um PR revisado — sem babysitting, sem trigger manual, sem você ficar colando contexto toda hora.

[![version](https://img.shields.io/badge/version-1.0.0-blue)](https://github.com/lucianfialho/claude-dev-pipeline/releases/tag/v1.0.0)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-plugin-blueviolet)](https://claude.ai/code)

---

## O problema

Você dá um issue pro Claude, ele implementa, cria o PR. Na próxima sessão, ele não sabe o que fez, por que fez, ou quais padrões o projeto usa. Você repete o contexto. Ele erra de novo. Você corrige. Ciclo.

**Context rot**: quanto mais Claude trabalha sem memória estruturada, pior fica a qualidade.

dev-pipeline resolve isso em três camadas:

1. **Memória por diretório** — escreve `.metadata/` junto com o código. Cada sessão futura carrega contexto sem ler todos os arquivos.
2. **Docs cache** — busca documentação atualizada das libs antes de implementar. Commita no repo. Todos se beneficiam.
3. **Especialistas por domínio** — não manda frontend pro backend-dev nem vice-versa. Cada issue vai pro especialista certo.

---

## Instala em 2 comandos

Dentro do Claude Code:
```
claude plugin marketplace add lucianfialho/claude-dev-pipeline
claude plugin install dev-pipeline
```

Resolve o primeiro issue:
```
/solve-issue 42
```

É isso.

---

## O que acontece quando você roda `/solve-issue 42`

```
Lê o issue
    ↓
Classifica o domínio → escolhe o especialista certo
    ↓
Especialista lê .metadata/ dos diretórios afetados (contexto instantâneo)
    ↓
Busca docs atualizadas das libs via cache ou context7
    ↓
Implementa com expertise do domínio
    ↓
Escreve testes → roda quality gates (test / lint / build)
    ↓
Escreve .metadata/ para os arquivos modificados
    ↓
Self-review de segurança → valida cobertura do issue
    ↓
Cria PR → GitHub Actions roda review automático com todos os especialistas
```

Sem você fazer nada depois do primeiro comando.

---

## Por que especialistas importam

Claude genérico implementa um componente React com `any` em todo lugar e esquece de loading state. O `frontend-dev` sabe que Server Components são padrão, que `'use client'` vai o mais fundo possível, que toda operação assíncrona tem loading/error/empty state.

Cada issue é classificado e delegado automaticamente:

| Tipo de issue | Especialista |
|--------------|-------------|
| UI, componentes, páginas, estilo, a11y | `frontend-dev` |
| API, banco de dados, auth, servidor | `backend-dev` |
| Testes, cobertura, flaky tests | `qa-engineer` |
| UX, fluxo, interação, acessibilidade | `ux-designer` + `frontend-dev` |
| Feature full-stack | `backend-dev` → `frontend-dev` |
| Docs, config, CI/CD | Direto (sem especialista) |

---

## `.metadata/` — a memória que persiste

Depois de cada implementação, o pipeline escreve isso junto com o código:

```
src/components/NavBar/
  index.tsx
  .metadata/
    context.md   → o que faz, dependências, padrões, caveats
    prompt.md    → qual issue originou, qual especialista, decisões tomadas
    summary.md   → uma linha — carregamento instantâneo nas próximas sessões
```

Vai commitado no PR. Na próxima vez que alguém (ou outra sessão) tocar nesse diretório, carrega o contexto em vez de reler o código inteiro.

O `CLAUDE.md` mantém um **Component Registry** atualizado automaticamente — uma tabela de todos os módulos com seus resumos. Qualquer sessão lê isso no início e já sabe onde está.

---

## Quality gates automáticos

Três hooks rodam sem você pedir:

| Hook | Quando | O que faz |
|------|--------|----------|
| **Stop** | Antes do Claude parar | Roda testes — bloqueia se falharem |
| **PostToolUse** | Após Write/Edit | Lint assíncrono — reporta problemas |
| **TaskCompleted** | Antes de fechar | Roda build — bloqueia se quebrar |

Detalhe: se `npm test` for `next build`, o hook de test pula (senão trava o `.next/lock` com o hook de build rodando ao mesmo tempo).

---

## Review automático no PR

O `solve-issue` inclui `@claude review-pr all` no body do PR. O GitHub Actions detecta e roda todos os especialistas em paralelo — sem você comentar, sem trigger manual.

---

## Skills disponíveis

### Resolver issues

```bash
/solve-issue 42       # resolve o issue #42
/solve-issue          # pega o próximo issue com label "claude"
/batch-issues         # processa todos os issues labelados em paralelo
/context-sync         # atualiza .metadata/ dos arquivos mudados + Component Registry
/context-sync full    # reconstrói .metadata/ de todo o projeto
```

### Revisar PRs

```bash
/review-pr all        # todos os especialistas em paralelo, veredicto unificado
/review-pr frontend   # componentes, a11y, performance, Server Components
/review-pr backend    # API, banco, auth, error handling
/review-pr security   # OWASP Top 10, secrets, injection, auth gaps
/review-pr ux         # Nielsen's heuristics, WCAG 2.1 AA
/check-security       # audit de segurança completo com scan de dependências
/suggest-tests        # testes faltando com skeleton code
/ux-review            # audit UX completo com recomendações priorizadas
/pr-summary           # resumo estruturado: mudanças, impacto, foco da review
/validate-issue       # verifica se o PR cobre todos os requisitos do issue
/batch-review         # mesmo que review-pr all, funciona em qualquer PR
```

Todos os skills de review funcionam como `@claude <comando>` em comentários de PR.

---

## GitHub Actions

Copia os workflows de `.github/workflows/` pro seu repo. Adiciona um secret:

| Secret | Valor |
|--------|-------|
| `CLAUDE_CODE_OAUTH_TOKEN` | Seu OAuth token do Claude Code |

Dois workflows:
- **`claude.yml`** — responde `@claude` em issues, comentários de PR, e body de PR
- **`claude-code-review.yml`** — review automático em todo PR aberto ou atualizado

---

## Configuração

Tudo opcional. Os defaults funcionam para a maioria dos projetos.

Cria `pipeline.config.json` na raiz do repo para customizar:

```json
{
  "$schema": "https://raw.githubusercontent.com/lucianfialho/claude-dev-pipeline/main/schemas/pipeline-config.schema.json",
  "specialists": {
    "defaults": ["code-reviewer"],
    "filePatterns": {
      "src/components/**": "frontend-dev",
      "src/api/**": "backend-dev",
      "**/*.test.*": "qa-engineer"
    }
  },
  "issues": {
    "label": "claude",
    "branchPrefix": "fix",
    "autoAssign": true
  },
  "batch": {
    "maxParallel": 3
  },
  "quality": {
    "requireTests": true,
    "requireBuild": true,
    "requireLint": true
  },
  "review": {
    "securityCheck": true,
    "performanceCheck": true,
    "maxFileReviewSize": 500
  }
}
```

| Seção | Chave | Default | O que faz |
|-------|-------|---------|-----------|
| `specialists` | `defaults` | `["code-reviewer"]` | Especialistas que sempre rodam em reviews |
| `specialists` | `filePatterns` | `{}` | Mapeia globs de arquivo para especialistas |
| `issues` | `label` | `"claude"` | Label do GitHub para auto-descoberta |
| `issues` | `branchPrefix` | `"fix"` | Prefixo de branch (`fix/42-descrição`) |
| `issues` | `autoAssign` | `true` | Auto-assign do issue ao resolver |
| `batch` | `maxParallel` | `3` | Máximo de agentes paralelos (1–10) |
| `quality` | `requireTests` | `true` | Bloqueia Stop se testes falharem |
| `quality` | `requireBuild` | `true` | Bloqueia TaskCompleted se build quebrar |
| `quality` | `requireLint` | `true` | Reporta lint após editar arquivos |
| `review` | `securityCheck` | `true` | Inclui checklist de segurança |
| `review` | `performanceCheck` | `true` | Inclui checklist de performance |
| `review` | `maxFileReviewSize` | `500` | Máx. linhas por arquivo na review |

---

## Review rules

Regras por domínio carregadas automaticamente pelo tipo de arquivo modificado:

| Arquivo de regra | Dispara em | Foco |
|-----------------|-----------|------|
| `base.md` | Sempre | Secrets, error handling, responsabilidade única |
| `frontend.md` | `.tsx`, `.jsx`, `.css` | Server Components, a11y, performance, design system |
| `backend.md` | `route.ts`, `actions.ts`, `api/` | Status codes, validação, queries, auth |
| `security.md` | Reviews de segurança | Injection, secrets, CSRF, CORS |
| `database.md` | `migration*`, `schema*`, `.prisma` | Migrations, N+1, transações, indexes |
| `performance.md` | Reviews de performance | Rendering, fetching, caching, assets |

Adiciona um `REVIEW.md` na raiz do repo para regras específicas do seu projeto — todos os skills de review carregam automaticamente.
