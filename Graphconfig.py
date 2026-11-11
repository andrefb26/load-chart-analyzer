from dataclasses import dataclass
# HSV (OpenCV): H 0..179, S 0..255, V 0..255

HSV_DB_DEFAULT = {
    # 1) Azul claro (HSV ~ (107,186,240))
    # Hue centrado ~107, V alto para não apanhar o azul escuro
    "blue_light": [
        ((98,  80, 170), (118, 255, 255)),
    ],

    # 2) Laranja / amarelado (HSV ~ (18,189,252))
    "orange_yellow": [
        ((12,  80, 120), (26,  255, 255)),
    ],

    # 3) Vermelho (HSV ~ (8,244,224))  -> precisa de wrap (0 e 179)
    "red": [
        ((0,   120, 80), (12,  255, 255)),
        ((170, 120, 80), (179, 255, 255)),
    ],

    # 4) Azul escuro (HSV ~ (100,246,146))
    # Hue perto do azul mas V mais baixo que o azul claro
    "blue_dark": [
        ((92,  120, 40), (110, 255, 169)),
    ],

    # 5) Cinzento (HSV ~ (0,0,191))  -> saturação muito baixa
    "gray": [
        ((0,   0,   80), (179, 35,  230)),
    ],
}
class ChartConfig:
    def __init__(self,
                 vmin=60,
                 major_tick_step=5,
                 series_order=None,
                 hsv_db=None,
                 ):
        self.vmin = vmin
        self.major_tick_step = major_tick_step

        # listas/dicts: nunca uses [] / {} como default direto no parâmetro
        self.series_order = series_order if series_order is not None else ["blue_light", "orange_yellow", "red", "blue_dark", "gray"]
        self.hsv_db=HSV_DB_DEFAULT
       