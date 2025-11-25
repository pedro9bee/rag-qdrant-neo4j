A implementação de um Agente de IA com o **Model Context Protocol (MCP)** no AWS Bedrock permite que o Agente se conecte a sistemas de negócios externos (bases de dados, APIs de CRM, ERPs, etc.) de forma segura e padronizada.

Este processo utiliza a arquitetura do **Bedrock AgentCore Runtime** e o *framework* `strands-agents` (mencionado na base de código analisada) para orquestração.

-----

## 1\. Referências e Componentes Principais

Para implementar este agente, irá precisar dos seguintes componentes e ferramentas:

| Componente | Função | Referência no Código |
| :--- | :--- | :--- |
| **AWS Bedrock** | Serviço gerenciado para *hostear* e orquestrar o Agente. | Implantação *serverless*. |
| **Bedrock AgentCore Runtime** | O ambiente de execução (runtime) do Agente. | `@app.entrypoint` e `bedrock-agentcore-starter-toolkit`. |
| **Strands Agents** | O *framework* de código aberto da AWS que lida com a orquestração do LLM. | Usado para definir o Agente, o LLM e as ferramentas. |
| **Model Context Protocol (MCP)** | Um protocolo padronizado que define como as ferramentas (funções Python) se ligam a serviços de *backend* (Gateway). | O pacote `mcp` na lista de dependências. |
| **MCP Gateway** | O serviço de *backend* que recebe as solicitações do Agente, executa a lógica de negócios (e.g., faz uma chamada a uma API de CRM) e retorna o resultado. | Módulo 03/04 do projeto. |

-----

## 2\. Visão Geral da Arquitetura (MCP)

O MCP insere uma camada de tradução e segurança entre o Agente (que é otimizado para raciocínio com o LLM) e os seus sistemas de negócios (que são otimizados para dados e transações).

O fluxo de trabalho é o seguinte:

1.  O **Agente LLM** determina que precisa de uma ferramenta externa para responder à pergunta do usuário.
2.  O Agente invoca a **Função Python** (a *Tool Interface*) definida com o MCP.
3.  O `strands-agents` interceta esta chamada e a envia como uma **solicitação HTTP** para o **MCP Gateway**.
4.  O **MCP Gateway** processa a solicitação (e.g., consulta uma base de dados) e retorna o resultado.
5.  O **Agente LLM** recebe o resultado e o usa para construir a resposta final ao usuário.

-----

## 3\. Passo a Passo para Implementação com MCP

A implementação divide-se em duas partes: o **Agente (Frontend)** e o **Gateway (Backend)**.

### Passo 1: Configurar a Tool Interface no Agente (Frontend)

Crie um arquivo Python para definir a função que o LLM verá e usará. Esta é a *interface* da ferramenta.

1.  **Instalar Dependências:** Certifique-se de que o seu ambiente tem o `strands-agents` e o `mcp`.
2.  **Definir a Função (Tool):** Crie uma função Python normal, mas adicione uma *docstring* clara, pois o LLM usará essa descrição para decidir quando usá-la.

<!-- end list -->

```python
# Em agent/tools/customer_service.py

# A função recebe o identificador do cliente e o que procurar.
def get_customer_orders(customer_id: str, search_query: str) -> str:
    """
    Use esta função para procurar pedidos de um cliente específico.
    O `customer_id` é obrigatório.
    Args:
        customer_id: O ID único do cliente.
        search_query: A descrição do pedido que o cliente está a procurar.
    Returns:
        Um resumo do estado do pedido do cliente.
    """
    # Esta função não implementa a lógica, ela é apenas a interface.
    # O MCP tratará de enviar esta invocação para o Gateway.
    return "Tool invocation will be routed to MCP Gateway."
```

### Passo 2: Configurar o Agente para Usar a Tool

No seu arquivo principal de configuração do Agente (onde usa o `@app.entrypoint`):

1.  **Importar a Tool:** Importe a função que acabou de criar.
2.  **Configurar o Agente:** Adicione a ferramenta à lista de ferramentas do seu Agente.

<!-- end list -->

```python
# Em agent/app.py (configuração principal)
from strands_agents.app import App
from strands_agents.models import Claude
from .tools.customer_service import get_customer_orders

app = App()

@app.entrypoint
def agent_entrypoint(runtime_context: dict) -> Claude:
    # 1. Escolher o modelo LLM
    llm = Claude(
        model_id='eu.anthropic.claude-haiku-4-5-20251001-v1:0' 
    )
    
    # 2. Injetar a ferramenta no Agente
    llm.tools.add(get_customer_orders)
    
    return llm
```

*Neste ponto, quando o LLM decidir chamar `get_customer_orders(...)`, a invocação será automaticamente roteada para o seu MCP Gateway.*

### Passo 3: Implementar o MCP Gateway (Backend)

O Gateway é onde a **lógica de negócios real** reside e é implantado separadamente (e.g., como um AWS Lambda ou Container).

1.  **Receber a Solicitação:** O Gateway recebe um payload JSON que descreve a Tool, o nome da função e os argumentos (e.g., `customer_id="123"`).
2.  **Executar a Lógica:** Dentro do Gateway, implementa-se a função que corresponde à interface:
      * Fazer a chamada à API de terceiros (e.g., `requests.get('crm.com/api/orders', params={'id': '123'})`).
      * Formatar o resultado em texto simples.
3.  **Retornar o Resultado:** O Gateway retorna o resultado da operação (em formato JSON, que é convertido de volta para a string do Agente).

### Passo 4: Implantação e Conexão (Bedrock)

1.  **Implantação do Agente:** Use o `bedrock-agentcore-starter-toolkit` ou o AWS CDK/CloudFormation para empacotar e implantar o código do Agente no **AWS Bedrock AgentCore Runtime**.
2.  **Implantação do Gateway:** Implante o seu **MCP Gateway** (a lógica do Passo 3) como um **endpoint HTTP** seguro (e.g., API Gateway + Lambda).
3.  **Configurar o Bedrock:** No console do AWS Bedrock, ao criar ou configurar o seu Agente:
      * Vá à secção de **Action Groups** (Grupos de Ação).
      * Defina um novo **Action Group** (que representa o seu Gateway).
      * Forneça a **URL do endpoint HTTP** do seu Gateway (obtida no Passo 4.2).
      * O Bedrock usará esta URL para rotear as chamadas das funções definidas no Agente.

Ao seguir estes passos, o Bedrock AgentCore fará a **integração automática** entre a chamada da função Python no seu Agente e a execução da lógica de negócios no seu Gateway via MCP.