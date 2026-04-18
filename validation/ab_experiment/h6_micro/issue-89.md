## Contexto

O Claude Code usa PreToolUse hooks para interceptar e validar ações antes da execução. Podemos usar esse padrão para garantir que o Claude não gere queries inválidas, charts com dados incompatíveis, ou configurações de connector malformadas.

## Hooks propostos

### 1. Validação de chart config
- **Matcher**: `Write|Edit` em `src/components/charts/`
- **Tipo**: command (determinístico)
- **Lógica**: Valida que props passadas ao chart são compatíveis com o tipo (ex: BarChart precisa de `data[]` com `name` e `value`)

### 2. Validação de connector schema
- **Matcher**: `Write|Edit` em `src/lib/connectors/`
- **Tipo**: command
- **Lógica**: Valida que config do connector segue schema esperado (API keys, required fields)

### 3. Query validation
- **Matcher**: `Bash` com padrões de query
- **Tipo**: prompt (LLM avalia)
- **Lógica**: Verifica que métricas/dimensões solicitadas existem no connector ativo

## Formato de hook

```json
{
  "PreToolUse": [
    {
      "matcher": "Write|Edit",
      "hooks": [
        {
          "type": "command",
          "command": "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/validate-chart.py",
          "timeout": 10
        }
      ]
    }
  ]
}
```

## Critérios de aceite

- [ ] Hook de chart validation bloqueia configs inválidas
- [ ] Hook de connector validation bloqueia schemas malformados
- [ ] Hooks não adicionam >500ms de latência por tool use
- [ ] Exit code 2 retorna mensagem útil pro Claude corrigir
