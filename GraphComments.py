import re
from collections import defaultdict


class CommentGenerator:
    EXCEEDANCE_THRESHOLD = 101.0   # %
    UNCERTAINTY_THRESHOLD = 1.0    # % — variações abaixo disto são incerteza
    TOP_N = 5                      # top N subidas e descidas a reportar

    def __init__(self, data: dict, mode: str,
                 ref1_color: str = None, ref2_color: str = None,
                 ref1_label: str = "current model",
                 ref2_label: str = "baseline model"):
        """
        Parameters
        ----------
        data : dict  {sensor_label: {color_key: value_pct, ...}, ...}
        mode : str   "comparison" | "study"
        ref1_color   : color key que representa o modelo atual (referência 1)
        ref2_color   : color key que representa o modelo de baseline (referência 2)
        ref1_label   : nome legível da ref1 (para as frases)
        ref2_label   : nome legível da ref2 (para as frases)
        """
        self.data = data
        self.mode = mode
        self.ref1_color = ref1_color
        self.ref2_color = ref2_color
        self.ref1_label = ref1_label
        self.ref2_label = ref2_label

    # ------------------------------------------------------------------
    # Ponto de entrada público
    # ------------------------------------------------------------------
    def generate(self) -> str:
        if self.mode == "comparison":
            return self._generate_comparison()
        else:
            return self._generate_study()

    # ------------------------------------------------------------------
    # Modo comparison
    # ------------------------------------------------------------------
    def _generate_comparison(self) -> str:
        ref1_vals, ref2_vals = self._split_values()
        paragraphs = []

        # --- §1 Excedências na ref1 ---
        paragraphs.append(self._para_exceedances(ref1_vals,ref2_vals))

        # --- §2 Maiores subidas e descidas ---
        paragraphs.append(self._para_variations(ref1_vals, ref2_vals))

        # --- §3 Frase estática ---
        paragraphs.append(
            "Load differences up to 1% are considered calculation "
            "uncertainties and are not discussed further."
        )

        # --- §4 Sensores ausentes numa das referências ---
        missing_para = self._para_missing(ref1_vals, ref2_vals)
        if missing_para:
            paragraphs.append(missing_para)

        # --- §5 Sumário por grupo ---
        diffs = self._compute_diffs(ref1_vals, ref2_vals)
        significant = {l: d for l, d in diffs.items()
                       if abs(d) > self.UNCERTAINTY_THRESHOLD}
        group_para = self._para_groups(significant)
        if group_para:
            paragraphs.append(group_para)

        return "\n\n".join(paragraphs)

    # ------------------------------------------------------------------
    # Modo study (sem comentários automáticos)
    # ------------------------------------------------------------------
    def _generate_study(self) -> str:
        return (
            "[Study mode: tabular output only — "
            "no automatic comments are generated for multi-reference studies.]"
        )

    # ------------------------------------------------------------------
    # Helpers de construção de parágrafos
    # ------------------------------------------------------------------
    def _para_exceedances(self, ref1_vals: dict, ref2_vals:dict =None) -> str:
        """Reports exceedances found in ref1 and/or ref2."""
        exc1 = {l: v for l, v in ref1_vals.items() if v > self.EXCEEDANCE_THRESHOLD}
        exc2 = {}
        if ref2_vals:
            exc2 = {l: v for l, v in ref2_vals.items() if v > self.EXCEEDANCE_THRESHOLD}

        if not exc1 and not exc2:
            return (
                f"The {self.ref1_label} and {self.ref2_label} show no exceedances "
                f"(all load ratios are at or below {self.EXCEEDANCE_THRESHOLD:.0f}%)."
            )

        sentences = []

        if exc1:
            parts = [f"{l} ({v:.1f}%)" for l, v in sorted(exc1.items(), key=lambda x: -x[1])]
            noun = "an exceedance" if len(parts) == 1 else "exceedances"
            sentences.append(f"The {self.ref1_label} ({self.ref1_color}) shows {noun} in {self._join_list(parts)}.")
        else:
            sentences.append(f"The {self.ref1_label} ({self.ref1_color}) shows no exceedances.")

        # Bloco do Modelo de Baseline (ref2)
        if exc2:
            parts = [f"{l} ({v:.1f}%)" for l, v in sorted(exc2.items(), key=lambda x: -x[1])]
            noun = "an exceedance" if len(parts) == 1 else "exceedances"
            sentences.append(f"The {self.ref2_label} ({self.ref2_color}) shows {noun} in {self._join_list(parts)}.")
        else:
            sentences.append(f"The {self.ref2_label} ({self.ref2_color}) shows no exceedances.")
            
        return "\n\n".join(sentences)

    def _para_variations(self, ref1_vals: dict, ref2_vals: dict) -> str:
        diffs = self._compute_diffs(ref1_vals, ref2_vals)
        significant = {l: d for l, d in diffs.items()
                       if abs(d) > self.UNCERTAINTY_THRESHOLD}

        if not significant:
            return (
                "Comparing the load ratios between the two releases, "
                "no significant variations (above 1%) were observed."
            )

        decreases = sorted(
            [(l, d) for l, d in significant.items() if d < 0],
            key=lambda x: x[1]                 # mais negativo primeiro
        )[:self.TOP_N]

        increases = sorted(
            [(l, d) for l, d in significant.items() if d > 0],
            key=lambda x: -x[1]                # mais positivo primeiro
        )[:self.TOP_N]

        clauses = []
        if decreases:
            dec_parts = [f"{l} ({d:+.1f}%)" for l, d in decreases]
            clauses.append(
                f"the most noteworthy decreases occur in {self._join_list(dec_parts)}"
            )
        if increases:
            inc_parts = [f"{l} ({d:+.1f}%)" for l, d in increases]
            clauses.append(
                f"the most noteworthy increases happen in {self._join_list(inc_parts)}"
            )

        body = " while ".join(clauses)
        return (
            "Comparing the load ratios between the two releases, "
            f"{body}."
        )

    def _para_missing(self, ref1_vals: dict, ref2_vals: dict) -> str:
        only_ref1 = sorted(set(ref1_vals) - set(ref2_vals))   # na ref1, não na ref2
        only_ref2 = sorted(set(ref2_vals) - set(ref1_vals))   # na ref2, não na ref1

        sentences = []
        for label in only_ref2:
            sentences.append(
                f"It is relevant to mention that {label} "
                f"is suppressed for the {self.ref1_label}."
            )
        for label in only_ref1:
            sentences.append(
                f"It is relevant to mention that {label} "
                f"is suppressed for the {self.ref2_label}."
            )
        return " ".join(sentences)

    def _para_groups(self, significant_diffs: dict) -> str:
        """
        Agrupa sensores pelo prefixo de letras maiúsculas (ex: BX, MY, FA)
        e gera frases de sumário quando TODOS os sensores do grupo variam
        na mesma direcção.
        """
        groups = defaultdict(list)
        for label, diff in significant_diffs.items():
            match = re.match(r'^([A-Z]+)', label)
            if match:
                groups[match.group(1)].append(diff)

        summaries = []
        for group, group_diffs in sorted(groups.items()):
            if len(group_diffs) < 2:          # grupo com 1 sensor → não resume
                continue
            if all(d > 0 for d in group_diffs):
                summaries.append(
                    f"Overall, all {group} sensors show load increases."
                )
            elif all(d < 0 for d in group_diffs):
                summaries.append(
                    f"Overall, all {group} sensors show load decreases."
                )

        return " ".join(summaries)

    # ------------------------------------------------------------------
    # Utilitários internos
    # ------------------------------------------------------------------
    def _split_values(self):
        ref1, ref2 = {}, {}
        for label, color_vals in self.data.items():
            if self.ref1_color in color_vals:
                ref1[label] = color_vals[self.ref1_color]
            if self.ref2_color in color_vals:
                ref2[label] = color_vals[self.ref2_color]
        return ref1, ref2

    @staticmethod
    def _compute_diffs(ref1_vals: dict, ref2_vals: dict) -> dict:
        """diff = ref1 − ref2  (positivo → ref1 subiu face à ref2)"""
        common = set(ref1_vals) & set(ref2_vals)
        return {l: ref1_vals[l] - ref2_vals[l] for l in common}

    @staticmethod
    def _join_list(parts: list) -> str:
        """['A', 'B', 'C']  →  'A, B and C'"""
        if len(parts) == 1:
            return parts[0]
        return ", ".join(parts[:-1]) + f" and {parts[-1]}"