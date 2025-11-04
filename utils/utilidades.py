DEBUG_MODE = True

def printdbg(*args):
    if DEBUG_MODE:
        print(" ".join(map(str, args)))

def is_debug() -> bool:
    return DEBUG_MODE

def get_progress(total: int, desc: str = ""):
    """
    Retorna um objeto de progresso com API semelhante ao tqdm:
    - update(n)
    - set_description(text)
    - close()
    Sempre visível (mesmo com DEBUG_MODE False). Se tqdm não estiver disponível,
    faz fallback para uma implementação simples baseada em prints.
    """
    try:
        from tqdm import tqdm  # type: ignore

        bar = tqdm(total=total, desc=desc, ncols=80)

        class TqdmWrapper:
            def update(self, n=1):
                bar.update(n)

            def set_description(self, text: str):
                bar.set_description(text)

            def close(self):
                bar.close()

        return TqdmWrapper()
    except Exception:
        # Fallback simples
        class SimpleProgress:
            def __init__(self, total: int, desc: str):
                self.total = total
                self.count = 0
                self.desc = desc
                if desc:
                    print(f"[1/{total}] {desc}")

            def update(self, n=1):
                self.count += n
                pass  # Sem barra, apenas mensagens por set_description

            def set_description(self, text: str):
                # Exibe passo atual
                cur = min(self.count + 1, self.total)
                print(f"[{cur}/{self.total}] {text}")

            def close(self):
                print("Concluído.")

        return SimpleProgress(total, desc)

def print_table(title: str, headers: list[str], rows: list[list], max_rows: int | None = None):
    """
    Imprime uma tabela simples somente quando DEBUG_MODE=True.
    headers: lista de cabeçalhos
    rows: lista de linhas (listas)
    max_rows: limita número de linhas exibidas
    """
    if not DEBUG_MODE:
        return
    if max_rows is not None:
        rows = rows[:max_rows]

    # calcular larguras
    widths = [len(str(h)) for h in headers]
    for r in rows:
        for i, cell in enumerate(r):
            widths[i] = max(widths[i], len(str(cell)))

    def fmt_row(cols):
        return " ".join(str(c).ljust(widths[i]) for i, c in enumerate(cols))

    print("\n=== " + title + " ===")
    print(fmt_row(headers))
    print("-" * (sum(widths) + len(widths) - 1))
    for r in rows:
        print(fmt_row(r))
