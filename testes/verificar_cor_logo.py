"""
Script para verificar a cor de fundo da logo
"""
from PIL import Image
import os
import sys

# Configurar encoding para Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

def analisar_logo(caminho_logo):
    """Analisa a cor de fundo da logo"""
    print(f"\n{'='*80}")
    print(f"ANALISE DA LOGO: {os.path.basename(caminho_logo)}")
    print(f"{'='*80}\n")
    
    if not os.path.exists(caminho_logo):
        print(f"[ERRO] Arquivo nao encontrado: {caminho_logo}")
        return None
    
    try:
        img = Image.open(caminho_logo)
        
        # Informações básicas
        print(f"[INFO] Dimensoes: {img.size[0]}x{img.size[1]} pixels")
        print(f"[INFO] Modo: {img.mode}")
        print(f"[INFO] Formato: {img.format}\n")
        
        # Converter para RGB se necessário
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Analisar cantos da imagem para determinar cor de fundo
        width, height = img.size
        
        # Cantos: (x, y)
        cantos = [
            (0, 0),  # Canto superior esquerdo
            (width-1, 0),  # Canto superior direito
            (0, height-1),  # Canto inferior esquerdo
            (width-1, height-1)  # Canto inferior direito
        ]
        
        print("[INFO] Analisando cantos da imagem:")
        cores_cantos = []
        for i, (x, y) in enumerate(cantos):
            r, g, b = img.getpixel((x, y))
            cores_cantos.append((r, g, b))
            nome_canto = ["Superior Esquerdo", "Superior Direito", "Inferior Esquerdo", "Inferior Direito"][i]
            print(f"   {nome_canto}: RGB({r}, {g}, {b}) = #{r:02x}{g:02x}{b:02x}")
        
        # Calcular média das cores dos cantos
        r_medio = sum(c[0] for c in cores_cantos) // len(cores_cantos)
        g_medio = sum(c[1] for c in cores_cantos) // len(cores_cantos)
        b_medio = sum(c[2] for c in cores_cantos) // len(cores_cantos)
        
        print(f"\n[INFO] Cor de fundo estimada (media dos cantos):")
        print(f"   RGB({r_medio}, {g_medio}, {b_medio}) = #{r_medio:02x}{g_medio:02x}{b_medio:02x}")
        
        # Verificar se é preto ou muito escuro
        if r_medio < 10 and g_medio < 10 and b_medio < 10:
            print(f"   [OK] Cor de fundo: PRETO (ou muito escuro)")
            print(f"   [RECOMENDACAO] Usar bg-black no CSS")
        elif r_medio < 30 and g_medio < 30 and b_medio < 30:
            print(f"   [INFO] Cor de fundo: MUITO ESCURO")
            print(f"   [RECOMENDACAO] Usar bg-black ou bg-gray-950 no CSS")
        else:
            print(f"   [ATENCAO] Cor de fundo nao e preta")
            print(f"   [RECOMENDACAO] Usar bg-[#{r_medio:02x}{g_medio:02x}{b_medio:02x}] no CSS")
        
        # Analisar algumas linhas do centro para verificar se há gradiente
        print(f"\n[INFO] Analisando centro da imagem:")
        centro_x = width // 2
        centro_y = height // 2
        r, g, b = img.getpixel((centro_x, centro_y))
        print(f"   Centro: RGB({r}, {g}, {b}) = #{r:02x}{g:02x}{b:02x}")
        
        # Verificar variação de cor
        variacao = max(cores_cantos, key=lambda c: sum(c))[0] - min(cores_cantos, key=lambda c: sum(c))[0]
        if variacao < 5:
            print(f"   [OK] Cor uniforme (variacao: {variacao})")
        else:
            print(f"   [INFO] Ha variacao de cor (variacao: {variacao})")
        
        return {
            'rgb': (r_medio, g_medio, b_medio),
            'hex': f"#{r_medio:02x}{g_medio:02x}{b_medio:02x}",
            'width': width,
            'height': height
        }
        
    except Exception as e:
        print(f"[ERRO] Erro ao analisar logo: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """Função principal"""
    # Caminho da logo
    caminho_logo = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                'static', 'logo', 'aero-cartola-logo.png')
    
    resultado = analisar_logo(caminho_logo)
    
    if resultado:
        print(f"\n{'='*80}")
        print("RESUMO")
        print(f"{'='*80}")
        print(f"Cor de fundo: {resultado['hex']}")
        print(f"Dimensoes: {resultado['width']}x{resultado['height']}")
        print(f"\n[RECOMENDACAO CSS]")
        if resultado['rgb'][0] < 10 and resultado['rgb'][1] < 10 and resultado['rgb'][2] < 10:
            print("   background-color: #000000; /* bg-black */")
        else:
            print(f"   background-color: {resultado['hex']};")
        print()

if __name__ == "__main__":
    main()

