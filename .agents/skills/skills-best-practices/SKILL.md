---
name: skills-best-practices
description: Boas práticas de engenharia de software, SOLID, Clean Code e padrões arquiteturais.
---

# Best Practices & Code Standards

## 1. Clean Code
- **Nomes Intencionais**: Variáveis, funções e classes devem expressar com clareza o seu propósito.
- **Funções Pequenas e Focadas**: Cada função deve realizar apenas uma operação com perfeição.
- **Transparência**: O código deve ser legível por si só, evitando comentários redundantes sobre o "como", focando apenas no "porquê" quando estritamente necessário.

## 2. Princípios SOLID
- **S (Single Responsibility)**: Módulos e classes possuem um único motivo para mudar.
- **O (Open/Closed)**: Entidades abertas para extensão e fechadas para modificação.
- **L (Liskov Substitution)**: Subtipos devem ser substituíveis pelos seus tipos base.
- **I (Interface Segregation)**: Interfaces específicas são melhores que uma única interface genérica.
- **D (Dependency Inversion)**: Dependa de abstrações, nunca de implementações concretas.

## 3. Qualidade & Defesa
- **Cláusulas de Guarda**: Retorne antecipadamente para evitar aninhamento excessivo (`if/else`).
- **Imutabilidade**: Priorize estruturas de dados imutáveis sempre que possível.
- **Zero Warnings**: O código gerado deve passar limpo em analisadores estáticos e linters.
