import random
from typing import List, Dict

class FallbackResponses:
    """Respostas fallback organizadas por categoria"""
    
    # Saudações iniciais
    GREETINGS = [
        "Opa! E aí, tudo bem? 😊",
        "Oi oi! Como você tá?",
        "Fala! Tudo certo aí?",
        "Hey! Que bom te ver por aqui!",
        "Oi! Tava esperando você aparecer! Como tá?",
        "E aí! Beleza? Como posso ajudar?",
        "Salve! Tudo tranquilo?",
        "Olá! Como tá seu dia hoje?",
        "Opa, tudo bem? Que legal você por aqui!",
        "Oi! Tudo joia? Em que posso ajudar?"
    ]
    
    # Quando perguntam sobre serviços
    SERVICES_INFO = [
        "Ah, eu faço várias coisas legais! Consigo puxar relatórios e dados da empresa, ajudo quando algo dá problema no sistema, organizo reuniões e agenda... É tipo um canivete suíço digital! 😄 Tem algo específico que você precisa?",
        
        "Boa pergunta! Eu ajudo com um monte de coisa: dados e relatórios da empresa, problemas técnicos, agendamentos... Basicamente tô aqui pra facilitar seu trabalho! O que você tá precisando hoje?",
        
        "Então, eu sou tipo aquele amigo que resolve as paradas chatas do trabalho! Puxo relatórios, resolvo problemas do sistema, marco reuniões... Me conta, o que seria útil pra você agora?",
        
        "Legal que você quer saber! Eu faço um monte de coisa útil aqui. Consigo puxar relatórios e dados da empresa pra você, ajudo quando o sistema dá problema, organizo sua agenda... É tipo ter um amigo que resolve essas coisas chatas do trabalho, sabe? Tem algo específico que você tá precisando?",
        
        "Ah, eu ajudo com várias coisas! Posso puxar relatórios e dados pra você, ajudo se tiver algum problema técnico, marco reuniões... Basicamente tô aqui pra facilitar sua vida! O que você tá precisando agora?"
    ]
    
    # Pedidos de ajuda genéricos
    HELP_RESPONSES = [
        "Claro! Me conta o que você precisa que eu te ajudo! 😊",
        "Opa, tô aqui pra isso! O que tá precisando?",
        "Com certeza! Pode falar, como posso ajudar?",
        "Sim! Me diz aí o que você precisa!",
        "Lógico! Conta comigo! O que seria?",
        "Pode deixar! No que posso te ajudar?"
    ]
    
    # Quando não entende
    CONFUSION_RESPONSES = [
        "Hmm, não entendi bem... Pode me explicar melhor? 🤔",
        "Opa, acho que não captei. Pode falar de outro jeito?",
        "Desculpa, não peguei essa. Me conta mais?",
        "Putz, não entendi direito. Você quer dados, suporte ou marcar algo?",
        "Eita, me perdi aqui! 😅 Pode repetir?",
        "Não entendi muito bem, mas tô aqui pra ajudar! Me explica melhor?",
        "Xiii, não captei! Pode dar mais detalhes?",
        "Ops, acho que me confundi! Pode explicar de novo?"
    ]
    
    # Erros técnicos (quando o sistema falha)
    TECHNICAL_ERRORS = [
        "Opa, tive uma travadinha aqui! 😅 Pode repetir? Prometo prestar atenção dessa vez!",
        "Eita, bugou aqui! 🐛 Me dá um segundinho que já volto!",
        "Ops, travei! 😵 Tenta de novo? Prometo que vou funcionar!",
        "Xiii, deu ruim aqui! Mas calma, já tô voltando! 🔧",
        "Poxa, tive um probleminha técnico. Pode repetir? 🙏",
        "Desculpa, deu uma travada! Mas tô de volta! O que você precisa?",
        "Eita, pequeno problema técnico! Mas já resolvi! Como posso ajudar?",
        "Foi mal, deu um bug aqui! Mas já tô funcionando! Pode falar!",
        "Ops, sistema deu uma falhada! Mas já voltou! Me conta o que precisa?"
    ]
    
    # Timeouts (quando demora muito)
    TIMEOUT_RESPONSES = [
        "Opa, demorei demais pensando aqui! 😅 Pode repetir? Vou ser mais rápido!",
        "Desculpa a demora! Tava processando muita coisa! O que você disse mesmo?",
        "Eita, me enrolei aqui! Pode falar de novo? Prometo ser mais ágil!",
        "Foi mal pela demora! Tava resolvendo umas coisas aqui! Como posso ajudar?",
        "Putz, demorei né? 😅 Pode repetir? Agora tô ligado!"
    ]
    
    # Despedidas
    FAREWELLS = [
        "Tchau! Foi ótimo falar com você! 👋",
        "Até mais! Se cuida!",
        "Falou! Boa sorte aí! ✨",
        "Tchau tchau! Aparece mais!",
        "Até! Qualquer coisa me chama!",
        "Valeu pela conversa! Até a próxima!",
        "Até logo! Foi um prazer ajudar! 😊",
        "Tchau! Bom resto de dia pra você!"
    ]
    
    # Agradecimentos
    THANK_YOU_RESPONSES = [
        "Imagina! Sempre que precisar! 😊",
        "Por nada! Foi um prazer!",
        "Que isso! Tamo junto! 🤝",
        "De nada! Conta comigo!",
        "Valeu você! Fico feliz em ajudar!",
        "Nada! Precisando, só chamar!",
        "Magina! Sempre às ordens!",
        "Que nada! É um prazer ajudar!"
    ]
    
    # Quando pedem dados/relatórios
    DATA_REQUESTS = [
        "Ah, você quer ver dados! Legal! Me conta mais: vendas, clientes, performance... O que seria útil pra você?",
        "Show! Adoro mostrar números! 📊 Quer ver vendas? Clientes? Ou alguma métrica específica?",
        "Opa, vamos aos dados! O que você quer saber? Vendas do mês? Comparativo? Performance?",
        "Relatórios! Boa! Temos várias opções... Vendas, clientes, KPIs... Por onde quer começar?",
        "Beleza! Vou puxar os dados! Me diz o que especificamente você precisa ver?"
    ]
    
    # Quando relatam problemas
    PROBLEM_REPORTS = [
        "Eita, que chato! Me conta direitinho o que tá acontecendo que eu te ajudo!",
        "Poxa, problema técnico é fogo! O que tá dando erro aí?",
        "Xiii, vamos resolver isso! Me explica o que aconteceu?",
        "Problema? Calma que a gente resolve! O que tá pegando?",
        "Puts, que saco! Mas vamos lá, me conta tudo sobre o erro!",
        "Ih, complicou aí? Relaxa, vamos resolver! O que tá rolando?"
    ]
    
    @staticmethod
    def get_response(category: str) -> str:
        """Retorna uma resposta aleatória da categoria especificada"""
        responses_map = {
            "greeting": FallbackResponses.GREETINGS,
            "services": FallbackResponses.SERVICES_INFO,
            "help": FallbackResponses.HELP_RESPONSES,
            "confusion": FallbackResponses.CONFUSION_RESPONSES,
            "error": FallbackResponses.TECHNICAL_ERRORS,
            "timeout": FallbackResponses.TIMEOUT_RESPONSES,
            "farewell": FallbackResponses.FAREWELLS,
            "thanks": FallbackResponses.THANK_YOU_RESPONSES,
            "data": FallbackResponses.DATA_REQUESTS,
            "problem": FallbackResponses.PROBLEM_REPORTS
        }
        
        responses = responses_map.get(category, FallbackResponses.CONFUSION_RESPONSES)
        return random.choice(responses)
    
    @staticmethod
    def get_contextual_response(user_input: str, error_type: str = None) -> str:
        """Retorna uma resposta apropriada baseada no contexto"""
        input_lower = user_input.lower()
        
        # Analisa a entrada para determinar a melhor categoria
        if any(word in input_lower for word in ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "hey", "opa"]):
            return FallbackResponses.get_response("greeting")
        
        elif any(word in input_lower for word in ["serviço", "serviços", "o que você faz", "o que faz", "funcionalidades", "o que oferece"]):
            return FallbackResponses.get_response("services")
        
        elif any(word in input_lower for word in ["ajuda", "ajudar", "me ajuda", "socorro", "help"]):
            return FallbackResponses.get_response("help")
        
        elif any(word in input_lower for word in ["tchau", "até", "adeus", "bye", "flw", "falou"]):
            return FallbackResponses.get_response("farewell")
        
        elif any(word in input_lower for word in ["obrigado", "obrigada", "valeu", "thanks", "agradeço"]):
            return FallbackResponses.get_response("thanks")
        
        elif any(word in input_lower for word in ["relatório", "dados", "vendas", "dashboard", "kpi", "métrica"]):
            return FallbackResponses.get_response("data")
        
        elif any(word in input_lower for word in ["erro", "problema", "bug", "travou", "não funciona", "falha"]):
            return FallbackResponses.get_response("problem")
        
        else:
            # Se não identificar o contexto, usa o tipo de erro ou confusion
            if error_type == "timeout":
                return FallbackResponses.get_response("timeout")
            elif error_type in ["error", "exception"]:
                return FallbackResponses.get_response("error")
            else:
                return FallbackResponses.get_response("confusion")


# Função helper para uso fácil
def get_fallback_response(user_input: str, error_type: str = None) -> str:
    """
    Retorna uma resposta fallback apropriada.
    
    Args:
        user_input: Mensagem original do usuário
        error_type: Tipo de erro (timeout, error, exception, etc.)
    
    Returns:
        Resposta natural e contextual
    """
    return FallbackResponses.get_contextual_response(user_input, error_type)