# ProgressTracker/bumpkin_utils.py
import json
import os

# Ordem dos Slots (baseado no tokenUriBuilder.ts)
# Esta ordem é crucial para construir a string de IDs corretamente.
SLOTS_ORDER = {
    "Background": 0,    "Body": 1,          "Hair": 2,            "Shirt": 3,
    "Pants": 4,         "Shoes": 5,         "Tool": 6,            "Hat": 7,
    "Necklace": 8,      "SecondaryTool": 9, "Coat": 10,           "Onesie": 11,
    "Suit": 12,         "Wings": 13,        "Dress": 14,          "Beard": 15,
    "Aura": 16,
}
# O número máximo de slots que consideramos para a URL da imagem.
# A URL de exemplo (32_3_5_317_234_22_240_396_0_0_86) tem 11 segmentos,
# correspondendo aos slots 0 a 10 (Background até Coat).
NUM_RELEVANT_SLOTS_FOR_URL = SLOTS_ORDER["Coat"] + 1 # 11 slots

ITEM_IDS_MAPPING = {}

def load_item_ids(base_dir, filename="bumpkin_data.json"):
    """
    Carrega o mapeamento de ITEM_IDS de um arquivo JSON.
    Este arquivo deve estar na raiz do projeto.
    """
    global ITEM_IDS_MAPPING
    filepath = os.path.join(base_dir, filename)
    try:
        with open(filepath, 'r') as f:
            ITEM_IDS_MAPPING = json.load(f)
        print(f"Mapeamento de ITEM_IDS carregado de {filepath}")
    except FileNotFoundError:
        print(f"ERRO: Arquivo {filepath} não encontrado. Crie este arquivo com os ITEM_IDS.")
        ITEM_IDS_MAPPING = {} # Garante que é um dict mesmo se falhar
    except json.JSONDecodeError:
        print(f"ERRO: Falha ao decodificar JSON de {filepath}.")
        ITEM_IDS_MAPPING = {}


def gerar_url_imagem_bumpkin(equipped_items):
    """
    Gera a URL da imagem do Bumpkin com base nos itens equipados.

    :param equipped_items: Dicionário com os itens equipados (ex: {'hair': 'Basic Hair', ...})
    :return: String da URL da imagem do Bumpkin, ou None se não puder ser gerada.
    """
    if not equipped_items or not ITEM_IDS_MAPPING:
        print("DEBUG: Itens equipados ou mapeamento de IDs ausente.")
        return None

    # Inicializa uma lista de IDs com zeros para o número de slots relevantes para a URL.
    # A URL de exemplo tem 11 partes, então consideramos até o slot "Coat".
    ids_numericos = [0] * NUM_RELEVANT_SLOTS_FOR_URL

    for nome_da_parte_equipada, nome_do_item in equipped_items.items():
        # Converte o nome da parte para o formato do SLOTS_ORDER (ex: "hair" -> "Hair")
        nome_da_categoria_no_slot = nome_da_parte_equipada.capitalize()

        item_id = ITEM_IDS_MAPPING.get(nome_do_item)
        slot_index = SLOTS_ORDER.get(nome_da_categoria_no_slot)

        if item_id is not None and slot_index is not None:
            if slot_index < NUM_RELEVANT_SLOTS_FOR_URL: # Só preenche se o slot for relevante para a URL
                ids_numericos[slot_index] = item_id
        # else:
            # Descomente para depurar itens ou categorias não encontradas
            # if item_id is None:
            # print(f"DEBUG: ID não encontrado para o item: {nome_do_item}")
            # if slot_index is None:
            # print(f"DEBUG: Categoria de slot não encontrada para: {nome_da_categoria_no_slot}")


    # Junta os IDs para formar a string
    # A URL de exemplo (e a imagem correta) usa 11 segmentos.
    string_de_ids = "_".join(map(str, ids_numericos)) # Garante que os 11 slots são representados

    # Monta a URL final
    url_base = "https://animations.sunflower-land.com/bumpkin_image/0_v1_"
    sufixo_url = "/100"
    url_imagem_final = f"{url_base}{string_de_ids}{sufixo_url}"

    print(f"DEBUG: Itens Equipados: {equipped_items}")
    print(f"DEBUG: IDs Numéricos Ordenados (para URL): {ids_numericos}")
    print(f"DEBUG: String de IDs Gerada: {string_de_ids}")
    print(f"DEBUG: URL da Imagem Gerada: {url_imagem_final}")

    return url_imagem_final