from django import forms


class AvaliacaoForm(forms.Form):
    """Nota única de 1 a 5 para a outra parte da locação."""

    nota = forms.ChoiceField(
        label="Sua nota",
        choices=(
            (5, "5 — Excelente"),
            (4, "4 — Muito bom"),
            (3, "3 — Bom"),
            (2, "2 — Ruim"),
            (1, "1 — Muito ruim"),
        ),
        widget=forms.RadioSelect,
    )
