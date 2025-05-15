# --- Versão da Aplicação ---
APP_VERSION = "0.1.0"

# Data final da temporada atual (ATUALIZE A CADA TEMPORADA
SEASON_START_DATE = "2025-05-01"
SEASON_END_DATE = "2025-07-31" # Exemplo: Final de Julho de 2025

# Data em que atividades (além do baú) começam a render tokens sazonais
DATE_ACTIVITIES_START_YIELDING_TOKENS = "2025-05-05"

#Datas de entrega dupla para calendario (out id farm)
DOUBLE_DELIVERY_DATE = "2025-05-16"
DOUBLE_DELIVERY_INTERVAL_DAYS = 8

# Nome do Token Sazonal (Atualize a cada temporada)
SEASONAL_TOKEN_NAME = "Geniseed"

# --- Itens da Loja Sazonal e Custos ---
# Estrutura: "Nome Exato do Item": {"cost": VALOR, "currency": "ticket" ou "sfl", "tier": 1/2/3/4}
SEASONAL_SHOP_ITEMS = {
    # Tier 1 (Normal) - 
    "Balloon Rug":           {"cost": 5, "currency": "sfl", "tier": 1}, # Ignorar nos cálculos de ticket
    "Amberfall Suit":        {"cost": 20,  "currency": "broken_pillar", "tier": 1}, # !! CUSTO BAIXO - BOM PARA DESBLOQUEIO?
    "Embersteel Suit":       {"cost": 50,  "currency": "ticket", "tier": 1}, # !!
    "Treasure Key":          {"cost": 200, "currency": "ticket", "tier": 1}, # !!
    "Bronze Flower Box":     {"cost": 250, "currency": "ticket", "tier": 1}, # !!
    "Flower Mask":           {"cost": 300, "currency": "ticket", "tier": 1}, # !!

    # Tier 2 (Rare) - Requer 4x T1 diferentes (tickets)
    "Glacierguard Suit":     {"cost": 60,  "currency": "sfl", "tier": 2}, # Ignorar
    "Blooomwarden Suit":     {"cost": 80,  "currency": "broken_pillar", "tier": 2}, # Ignorar
    "Rare Key":              {"cost": 500, "currency": "ticket", "tier": 2}, # !!
    "Love Charm Shirt":      {"cost": 650, "currency": "ticket", "tier": 2}, # !!
    "Silver Flower Box":     {"cost": 750, "currency": "ticket", "tier": 2}, # !!
    "Giant Yam":             {"cost": 2000,"currency": "ticket", "tier": 2}, # !!

    # Tier 3 (Epic) - Requer 4x T2 diferentes (tickets)
    "Frost Sword":           {"cost": 180, "currency": "broken_pillar", "tier": 3}, # Ignorar
    "Heart Air Balloon":     {"cost": 200, "currency": "sfl", "tier": 3}, # Ignorar
    "Luxury Key":            {"cost": 1000,"currency": "ticket", "tier": 3}, # !!
    "Flower-Scribed Statue": {"cost": 1500,"currency": "ticket", "tier": 3}, # !!
    "Gold Flower Box":       {"cost": 1500,"currency": "ticket", "tier": 3},
    "Giant Zucchini":        {"cost": 3000,"currency": "ticket", "tier": 3}, # !!

    # Tier 4 (Mega) - Requer 4x T3 diferentes (tickets)
    "Giant Kale":            {"cost": 6000, "currency": "ticket", "tier": 4},
    "Oracle Syringe":        {"cost": 8500, "currency": "ticket", "tier": 4}        
}

# Dicionário de Recompensas Base (existente)
BASE_DELIVERY_REWARDS = {
    "pumpkin' pete": 1,
    "bert": 2,
    "finley": 2,
    "miranda": 2,
    "finn": 3,
    "raven": 3,
    "cornwell": 4,
    "jester": 4,
    "timmy": 4,
    "pharaoh": 5,
    "tywin": 5,
}

# ---> DEFINIÇÃO DAS FONTES DE BÔNUS DO JOGADOR ---
# Este dicionário define os bônus potenciais, seus valores base e como verificar se estão ativos.
# Pode ser usado para diferentes tipos de atividades, não apenas entregas.
# Considerar renomear para DEFINED_PLAYER_BONUSES para maior clareza de seu propósito geral.
# Por enquanto, manteremos o nome original, mas entendendo seu uso mais amplo.
SEASONAL_DELIVERY_BUFFS = { # Poderia ser renomeado para DEFINED_PLAYER_BONUSES
    # Tipo 'vip': Verifica se o VIP está ativo
    "vip": {"type": "vip", "bonus_value": 2, "description": "VIP Status"}, # 'bonus' renomeado para 'bonus_value'

    # Tipo 'equipped': Verifica se o VALOR abaixo existe em farm.bumpkin.equipped.* OU farm.farmHands.bumpkins.*.equipped.*
    "Flower Mask": {"type": "equipped", "bonus_value": 1, "description": "Flower Mask equipped"},
    "Love Charm Shirt": {"type": "equipped", "bonus_value": 1, "description": "Love Charm Shirt equipped"},

    # Tipo 'collectible': Verifica se a CHAVE abaixo existe em farm.home.collectibles OU farm.collectibles
    "Heart Air Balloon": {"type": "collectible", "bonus_value": 1, "description": "Heart Air Balloon placed"},

    # Adicionar outros buffs futuros aqui
}


# ---> REGRAS DE APLICAÇÃO DE BÔNUS POR ATIVIDADE ---
# Define como os bônus de SEASONAL_DELIVERY_BUFFS
# se aplicam a diferentes atividades e tipos de recompensa.

ALL_PLAYER_BONUSES = list(SEASONAL_DELIVERY_BUFFS.keys()) 
# Resultado: ["vip", "Flower Mask", "Love Charm Shirt", "Heart Air Balloon"]

ALL_PLAYER_BONUSES_EXCEPT_VIP = [
    bonus_name for bonus_name in ALL_PLAYER_BONUSES if bonus_name != "vip"]
# Resultado: ["Flower Mask", "Love Charm Shirt", "Heart Air Balloon"]


ACTIVITY_BONUS_RULES = {
    "deliveries": {
        "description": "Bônus para tokens sazonais de entregas de NPC.",
        "applicable_bonuses": ALL_PLAYER_BONUSES, # Todos os bônus
        "reward_type": "numeric_token"
        # A lógica de aplicação para deliveries já é bem tratada pelo total_delivery_bonus
    },
    "animal_bounties": {
        "description": "Bônus para tokens sazonais em recompensas de bounties de animais (Mega Board).",
        "applicable_bonuses": ALL_PLAYER_BONUSES_EXCEPT_VIP, # Todos, exceto VIP
        "reward_type": "item_dict",
        "item_container_field": "items",
        "target_item_keys": [SEASONAL_TOKEN_NAME]
    },
    "generic_mega_board_bounties": {
        "description": "Bônus para tokens sazonais de bounties gerais do Mega Board (que usam 'items' para Geniseed).",
        "applicable_bonuses": ALL_PLAYER_BONUSES_EXCEPT_VIP, # Todos, exceto VIP
        "reward_type": "item_dict", # Mudança: A API mostra Geniseed em 'items'
        "item_container_field": "items",
        "target_item_keys": [SEASONAL_TOKEN_NAME]
    },
    "chores": { # Nova entrada para Chores
        "description": "Bônus para tokens sazonais de Chores (tarefas).",
        "applicable_bonuses": ALL_PLAYER_BONUSES, # Todos os bônus
        "reward_type": "item_dict", 
        "item_container_field": "items", # As chores no JSON têm farm.choreBoard.chores[npc_name].reward.items
        "target_item_keys": [SEASONAL_TOKEN_NAME]
        # Nota: Para chores, o 'item_container_field' será acessado dentro de chore_data['reward']['items']
        # A função apply_bonus_to_reward precisará de um pequeno ajuste ou de um objeto de recompensa pré-processado.
        # Por ora, vamos manter assim e ajustar em route_helpers.py como passamos o objeto.

    }
}

# --- CATEGORIAS PARA BOUNTIES (Mega Board - v2) ---

# Lista de nomes de requisitos ('bounty.name') para Flores
FLOWER_BOUNTY_NAMES = [
    "Prism Petal", "Celestial Frostbloom", "Primula Enigma", "Red Daffodil",
    "Yellow Daffodil", "Purple Daffodil", "White Daffodil", "Blue Daffodil",
    "Red Lotus", "Yellow Lotus", "Purple Lotus", "White Lotus", "Blue Lotus",
    "Red Edelweiss", "Yellow Edelweiss", "Purple Edelweiss", "White Edelweiss",
    "Blue Edelweiss", "Red Gladiolus", "Yellow Gladiolus", "Purple Gladiolus",
    "White Gladiolus", "Blue Gladiolus", "Red Lavender", "Yellow Lavender",
    "Purple Lavender", "White Lavender", "Blue Lavender", "Red Clover",
    "Yellow Clover", "Purple Clover", "White Clover", "Blue Clover",
    "Red Pansy", "Yellow Pansy", "Purple Pansy", "White Pansy", "Blue Pansy", 
    "Red Cosmos", "Yellow Cosmos", "Purple Cosmos", "White Cosmos", "Blue Cosmos",
    "Red Balloon Flower", "Yellow Balloon Flower", "Purple Balloon Flower",
    "White Balloon Flower", "Blue Balloon Flower",
    "Red Carnation", "Yellow Carnation", "Purple Carnation", "White Carnation",
    # Revise e adicione/remova conforme necessário...
]

# Lista de nomes de requisitos ('bounty.name') para Peixes
FISH_BOUNTY_NAMES = [
    "Anchovy", "Butterflyfish", "Blowfish", "Clownfish", "Sea Bass",
    "Sea Horse", "Horse Mackerel", "Squid", "Red Snapper", "Moray Eel",
    "Olive Flounder", "Napoleanfish", "Surgeonfish", "Zebra Turkeyfish",
    "Ray", "Hammerhead Shark", "Tuna", "Mahi Mahi", "Blue Marlin",
    "Oarfish", "Football fish", "Sunfish", "Coelacanth", "Whale Shark",
    "Barred Knifejaw", "Sawshark", "White Shark", "Twilight Anglerfish",
    "Starlight Tuna", "Radiant Ray", "Phantom Barracuda", "Gilded Swordfish",
    "Crimson Carp", "Battle Fish", "Lemon Shark", "Longhorn Cowfish", "Jellyfish",
    # Revise e adicione/remova conforme necessário...
]

# Lista de nomes de requisitos ('bounty.name') para Obsidianas
OBSIDIAN_BOUNTY_NAMES = [
    "Obsidian",
    # Revise e adicione/remova conforme necessário...
]

# Lista de nomes de requisitos ('bounty.name') para Marks
MARK_BOUNTY_NAMES = [
    "Mark",
    # Revise e adicione/remova conforme necessário...
]

# Ordem de exibição das categorias + a categoria "Exotic" para o resto
# A categoria "Exotic" será tratada automaticamente no template
BOUNTY_CATEGORY_ORDER = [
    "Flores",
    "Peixes",
    "Exotic",# Catch-all para itens não listados acima
    "Mark",
    "Obsidiana"  
]

# Heurística para coluna Animais (mantida)
ANIMAL_NAMES_HEURISTIC = ["Chicken", "Cow", "Sheep"]