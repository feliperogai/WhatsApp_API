from typing import Dict, List, Any

class DataValidationConfig:
    """Configurações centralizadas para validação de dados"""
    
    # Ordem obrigatória de coleta
    COLLECTION_ORDER = [
        "cnpj",          # 1º - Sempre primeiro
        "empresa",       # 2º - Nome da empresa
        "nome",          # 3º - Nome do usuário
        "email",         # 4º - Email corporativo
        "cargo"          # 5º - Cargo na empresa
    ]
    
    # Campos obrigatórios para liberar acesso
    REQUIRED_FIELDS = {
        "empresa": ["cnpj", "empresa"],  # Para identificar empresa
        "usuario": ["nome", "email", "cargo"]  # Para identificar usuário
    }
    
    # Regras de validação
    VALIDATION_RULES = {
        "cnpj": {
            "min_length": 14,
            "max_length": 18,  # Com formatação
            "pattern": r'^\d{2}\.?\d{3}\.?\d{3}\/?\d{4}-?\d{2}$',
            "custom_validator": "validate_cnpj",
            "error_messages": {
                "invalid": "❌ CNPJ inválido. Por favor, verifique os dígitos e tente novamente.",
                "format": "❌ Formato inválido. Use: XX.XXX.XXX/XXXX-XX",
                "repeated": "❌ CNPJ não pode ter todos os números iguais."
            }
        },
        "empresa": {
            "min_length": 3,
            "max_length": 100,
            "error_messages": {
                "too_short": "❌ Nome da empresa muito curto. Digite o nome completo.",
                "too_long": "❌ Nome da empresa muito longo. Use até 100 caracteres."
            }
        },
        "nome": {
            "min_length": 3,
            "max_length": 100,
            "min_words": 2,  # Nome e sobrenome
            "error_messages": {
                "too_short": "❌ Nome muito curto.",
                "incomplete": "⚠️ Por favor, informe seu nome completo (nome e sobrenome).",
                "invalid_chars": "❌ Nome não pode conter números ou caracteres especiais."
            }
        },
        "email": {
            "pattern": r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$',
            "error_messages": {
                "invalid": "❌ Email inválido. Use o formato: nome@empresa.com",
                "domain": "❌ Domínio de email inválido."
            }
        },
        "cargo": {
            "min_length": 3,
            "max_length": 50,
            "error_messages": {
                "too_short": "❌ Cargo muito curto. Digite o cargo completo.",
                "too_long": "❌ Cargo muito longo. Use até 50 caracteres."
            }
        }
    }
    
    # Mensagens de solicitação
    REQUEST_MESSAGES = {
        "cnpj": [
            "📋 Antes de mostrar os dados, preciso do CNPJ da empresa. Pode informar?",
            "Para liberar o acesso aos dados, qual o CNPJ da empresa?",
            "Primeiro, me passa o CNPJ da empresa, por favor.",
            "Preciso validar o CNPJ da empresa. Qual é?",
            "📊 Para acessar os relatórios, informe o CNPJ da empresa:"
        ],
        "empresa": [
            "Agora, qual o nome da empresa?",
            "Ótimo! Agora me diz o nome da empresa.",
            "Perfeito! Qual é o nome da empresa?",
            "Legal! E o nome da empresa é...?",
            "Show! Me informa o nome completo da empresa:"
        ],
        "nome": [
            "Excelente! Agora preciso do seu nome completo.",
            "Ótimo! Como você se chama? (nome completo)",
            "Perfeito! Qual o seu nome completo?",
            "Show! Me diz seu nome completo, por favor.",
            "Legal! Agora seu nome completo:"
        ],
        "email": [
            "Qual seu email corporativo?",
            "Me passa seu email de trabalho, por favor.",
            "Preciso do seu email para enviar os relatórios. Qual é?",
            "E seu email profissional?",
            "Agora, qual seu melhor email para contato?"
        ],
        "cargo": [
            "Para finalizar, qual o seu cargo na empresa?",
            "Último dado: qual sua função/cargo?",
            "E qual cargo você ocupa na empresa?",
            "Por fim, me diz seu cargo, por favor.",
            "Para completar o cadastro, qual sua posição na empresa?"
        ]
    }
    
    # Mensagens de sucesso
    SUCCESS_MESSAGES = {
        "cnpj": "✅ CNPJ validado com sucesso!",
        "empresa": "✅ Empresa registrada!",
        "nome": "✅ Nome cadastrado!",
        "email": "✅ Email confirmado!",
        "cargo": "✅ Cargo registrado!",
        "complete": "🎉 Parabéns {nome}! Acesso liberado para {empresa}!"
    }
    
    # Configurações de segurança
    SECURITY_SETTINGS = {
        "block_personal_before_company": True,  # Bloqueia dados pessoais antes da empresa
        "require_valid_cnpj": True,  # Exige CNPJ válido
        "require_corporate_email": False,  # Exige email corporativo (não gmail, hotmail, etc)
        "session_timeout_minutes": 30,  # Timeout da sessão de coleta
        "max_validation_attempts": 5  # Máximo de tentativas para cada campo
    }
    
    # Domínios de email não corporativos (se require_corporate_email = True)
    PUBLIC_EMAIL_DOMAINS = [
        "gmail.com", "hotmail.com", "outlook.com", "yahoo.com",
        "yahoo.com.br", "bol.com.br", "uol.com.br", "terra.com.br",
        "ig.com.br", "globo.com", "protonmail.com", "icloud.com"
    ]
    
    @classmethod
    def get_validation_rule(cls, field: str) -> Dict[str, Any]:
        """Retorna regra de validação para um campo"""
        return cls.VALIDATION_RULES.get(field, {})
    
    @classmethod
    def get_request_message(cls, field: str, index: int = 0) -> str:
        """Retorna mensagem de solicitação para um campo"""
        messages = cls.REQUEST_MESSAGES.get(field, [f"Por favor, informe: {field}"])
        return messages[index % len(messages)]
    
    @classmethod
    def is_corporate_email(cls, email: str) -> bool:
        """Verifica se é email corporativo"""
        if not cls.SECURITY_SETTINGS["require_corporate_email"]:
            return True
        
        domain = email.split('@')[-1].lower()
        return domain not in cls.PUBLIC_EMAIL_DOMAINS
    
    @classmethod
    def get_field_description(cls, field: str) -> str:
        """Retorna descrição amigável do campo"""
        descriptions = {
            "cnpj": "CNPJ da empresa",
            "empresa": "nome da empresa",
            "nome": "seu nome completo",
            "email": "seu email corporativo",
            "cargo": "seu cargo na empresa"
        }
        return descriptions.get(field, field)

# Exemplo de uso personalizado
class CustomDataValidationConfig(DataValidationConfig):
    """Configuração personalizada para cliente específico"""
    
    # Adiciona campo extra
    COLLECTION_ORDER = DataValidationConfig.COLLECTION_ORDER + ["departamento"]
    
    # Adiciona validação para o novo campo
    VALIDATION_RULES = {
        **DataValidationConfig.VALIDATION_RULES,
        "departamento": {
            "min_length": 2,
            "max_length": 50,
            "allowed_values": [
                "Vendas", "Marketing", "TI", "RH", "Financeiro",
                "Operações", "Logística", "Compras", "Jurídico"
            ],
            "error_messages": {
                "invalid": "❌ Departamento inválido. Escolha um dos departamentos disponíveis."
            }
        }
    }
    
    # Adiciona mensagens para o novo campo
    REQUEST_MESSAGES = {
        **DataValidationConfig.REQUEST_MESSAGES,
        "departamento": [
            "Em qual departamento você trabalha?",
            "Qual o seu departamento na empresa?",
            "Me informa seu departamento:"
        ]
    }