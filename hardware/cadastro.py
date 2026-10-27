colaboradores = {
    "702970395839": {
        "nome": "Alice",
        "autorizado": True
    },
    "909601600916": {
        "nome": "Thaise",
        "autorizado": False
    }
}


def buscar_colaborador(id_cracha):
    return colaboradores.get(str(id_cracha))


if __name__ == "__main__":
    id_teste = input("Digite o ID do crachá para consultar: ")

    colaborador = buscar_colaborador(id_teste)

    if colaborador:
        print("Nome:", colaborador["nome"])
        print("Autorizado:", colaborador["autorizado"])
    else:
        print("Identificação não encontrada!")