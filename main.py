import sys
import cv2
import numpy as np
from Graphcalculate import GraphCalculate
from Graphconfig import ChartConfig
from GraphComments import CommentGenerator


def build_sensor_data(labels, rects_by_color, cfg, step_px, y_base):
    """
    Constrói um dict unificado:
        {sensor_label: {color_key: value_pct, ...}, ...}
    """
    data = {}
    for color, rects in rects_by_color.items():
        if not rects:
            continue
        for i, (x, y, w, h) in enumerate(rects):
            label = labels[i] if i < len(labels) else f"label_{i}"
            val = cfg.vmin + (h / step_px) * cfg.major_tick_step
            data.setdefault(label, {})[color] = round(val, 2)
    return data


def ask_mode():
    print("\nSelect analysis mode:")
    print("  1 → Comparison (2 models / releases)")
    print("  2 → Study      (N references, same turbine)")
    choice = input("Enter 1 or 2: ").strip()
    return "comparison" if choice == "1" else "study"


def ask_ref_colors(available_colors):
    print(f"\nAvailable color series: {available_colors}")
    ref1 = input("Enter the color key for the CURRENT model (ref1): ").strip()
    ref2 = input("Enter the color key for the BASELINE model (ref2): ").strip()
    return ref1, ref2


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "samples/comparison.png"
    img = cv2.imread(path)
    if img is None:
        raise FileNotFoundError("Não consegui ler a imagem.")

    cfg = ChartConfig()
    gc = GraphCalculate(img)

    # 1. Processamento de Imagem (Silencioso)
    crop, bbox = gc.crop()
    step_px, y_base, ys = gc.get_scale()
    labels, label_x_centers = gc.get_x_labels()

    # Identificação das barras e cores
    rects_by_color = {}
    for color, ranges in cfg.hsv_db.items():
        rects_all = []
        for (lower, upper) in ranges:
            mask = gc.color_mask_hsv(lower, upper)
            rects_all.extend(gc.find_bar_rects(mask))
        rects_all.sort(key=lambda r: r[0])
        rects_by_color[color] = rects_all

    available = [c for c, r in rects_by_color.items() if r]

    # 2. Definição do Modo (Antes de apresentar resultados)
    if len(available) <= 1:
        mode = "study"
        if len(available) == 1:
            print(f"\n[Auto] Only 1 color series detected ({available[0]}) → Study mode active.")
        else:
            print("\n[Auto] No color series detected → Study mode active.")
    else:
        # Exatamente 2 cores
        mode = ask_mode()

    # Configuração de referências (apenas se for comparison)
    ref1_color, ref2_color = None, None
    if mode == "comparison":
        ref1_color, ref2_color = ask_ref_colors(available)

    # 3. Apresentação dos Valores (Aparece sempre, após a seleção)
    
    print(f"\nLabels found ({len(labels)}): {labels}")
    print(f"\nLabels found ({len(labels)}): {labels}")
    print("\n" + "=" * 50)
    print(f"VALORES DETETADOS - MODO: {mode.upper()}")
    
    if mode == "comparison":
        print(f"Filtrando apenas: {ref1_color} vs {ref2_color}")
    print("=" * 50)
    
    for color, rects in rects_by_color.items():
        if not rects:
            continue
        
        # --- NOVO: Filtragem para o modo Comparison ---
        if mode == "comparison" and color not in [ref1_color, ref2_color]:
            continue # Salta as cores que não interessam à comparação
            
        print(f"\n[{color}]")
        for i, (x, y, w, h) in enumerate(rects):
            label = labels[i] if i < len(labels) else f"label_{i}"
            val = cfg.vmin + ((y_base - y) / step_px) * cfg.major_tick_step
            print(f"  {label:20s} → {round(val, 2):.2f}%")

    # 4. Comentários (Apenas se for Comparison)
    if mode == "comparison":
        sensor_data = build_sensor_data(labels, rects_by_color, cfg, step_px, y_base)
        gen = CommentGenerator(
            data=sensor_data,
            mode="comparison",
            ref1_color=ref1_color,
            ref2_color=ref2_color,
            ref1_label="current model",
            ref2_label="baseline model",
        )
        print("\n" + "=" * 50)
        print("AUTO-GENERATED COMMENTS")
        print("=" * 50)
        print(gen.generate())
    else:
        print("\n" + "=" * 50)
        print("Study mode: Tabular output only. No comparisons generated.")
        print("=" * 50)


if __name__ == "__main__":
    main()





