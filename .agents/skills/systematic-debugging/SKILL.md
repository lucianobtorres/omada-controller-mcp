---
name: systematic-debugging
description: Utiliza o método científico para o diagnóstico de bugs de forma sistemática.
---

# Systematic Debugging

Para diagnosticar bugs, siga este método científico sistemático:

1. **Observação (Gather Data)**: 
   - Reproduza o bug.
   - Analise os logs de erro, stack traces e o comportamento do sistema.

2. **Hipótese (Formulate Hypothesis)**: 
   - Baseado nos dados, formule uma ou mais hipóteses sobre o que está causando o erro.
   - Liste as possíveis causas raízes, da mais provável para a menos provável.

3. **Previsão (Make Predictions)**: 
   - O que deveria acontecer no código se a hipótese for verdadeira?
   - Onde podemos inspecionar variáveis ou estados para confirmar?

4. **Teste (Experiment & Test)**: 
   - Adicione logs estratégicos ou isole o trecho de código afetado.
   - Modifique o estado ou a entrada e verifique se o comportamento muda conforme previsto.

5. **Conclusão (Analyze Results & Conclude)**: 
   - Se o teste confirmar a hipótese, você encontrou a causa raiz. Proponha a correção.
   - Se o teste falhar, descarte a hipótese e retorne ao passo 2.

6. **Ação Corretiva**: 
   - Implemente a correção apenas após confirmar a causa raiz, evitando soluções de "tentativa e erro" (shotgun debugging).
