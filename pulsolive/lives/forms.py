from django import forms

from .models import Brand, Host, LiveEvent, LiveSession, Tag


class BrandForm(forms.ModelForm):
    class Meta:
        model = Brand
        fields = ("name", "tiktok_handle", "category", "monthly_gmv_goal")


class HostForm(forms.ModelForm):
    class Meta:
        model = Host
        fields = ("name", "handle", "gender", "style", "experience", "active")
        help_texts = {"gender": "Opcional. Solo se usa para analizar la respuesta de tu audiencia."}


class TagsField(forms.CharField):
    """Etiquetas separadas por coma: 'música en vivo, set nuevo'."""

    def prepare_value(self, value):
        if isinstance(value, (list, tuple)):
            return ", ".join(t.name if hasattr(t, "name") else str(t) for t in value)
        return value


class LiveSessionForm(forms.ModelForm):
    started_at = forms.DateTimeField(label="Inicio", widget=forms.DateTimeInput(attrs={"type": "datetime-local"},
                                                                                format="%Y-%m-%dT%H:%M"))
    tag_names = TagsField(label="Etiquetas", required=False,
                          help_text="Separadas por coma. Ej: set nuevo, invitada, música")

    class Meta:
        model = LiveSession
        fields = ("brand", "host", "title", "started_at", "duration_minutes",
                  "gmv", "orders", "units_sold", "viewers", "peak_viewers", "avg_watch_seconds",
                  "new_followers", "likes", "comments", "shares", "product_clicks",
                  "promo_type", "script_type", "format", "setting", "main_product", "product_category",
                  "avg_price", "experiment", "experiment_variant", "notes")
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, org=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.org = org
        self.fields["brand"].queryset = Brand.objects.filter(organization=org, archived=False)
        self.fields["host"].queryset = Host.objects.filter(organization=org)
        from insights.models import Experiment

        self.fields["experiment"].queryset = Experiment.objects.filter(organization=org, status="running")
        self.fields["experiment"].required = False
        if self.instance.pk:
            self.initial["tag_names"] = ", ".join(t.name for t in self.instance.tags.all())

    def save(self, commit=True):
        live = super().save(commit=False)
        live.organization = self.org
        if commit:
            live.save()
            names = [n.strip()[:60] for n in (self.cleaned_data.get("tag_names") or "").split(",") if n.strip()]
            tags = [Tag.objects.get_or_create(organization=self.org, name=n.lower())[0] for n in names]
            live.tags.set(tags)
        return live


class QuickTagForm(forms.ModelForm):
    """Etiquetado rápido (30 segundos por live)."""

    class Meta:
        model = LiveSession
        fields = ("host", "promo_type", "script_type", "format", "setting", "main_product")

    def __init__(self, *args, org=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["host"].queryset = Host.objects.filter(organization=org, active=True)


class LiveEventForm(forms.ModelForm):
    class Meta:
        model = LiveEvent
        fields = ("minute", "kind", "description")


class ImportForm(forms.Form):
    brand = forms.ModelChoiceField(label="Marca", queryset=Brand.objects.none())
    default_host = forms.ModelChoiceField(label="Host (si el archivo no lo trae)", queryset=Host.objects.none(),
                                          required=False)
    file = forms.FileField(label="Archivo CSV o Excel")

    def __init__(self, *args, org=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["brand"].queryset = Brand.objects.filter(organization=org, archived=False)
        self.fields["default_host"].queryset = Host.objects.filter(organization=org)

    def clean_file(self):
        f = self.cleaned_data["file"]
        if not f.name.lower().endswith((".csv", ".xlsx", ".xls", ".txt")):
            raise forms.ValidationError("Sube un archivo .csv o .xlsx")
        return f


class MinuteImportForm(forms.Form):
    file = forms.FileField(label="Archivo minuto a minuto (CSV o Excel)")


class TranscriptForm(forms.Form):
    file = forms.FileField(label="Archivo de subtítulos (.srt, .vtt o .txt)", required=False)
    text = forms.CharField(label="…o pega la transcripción", required=False,
                           widget=forms.Textarea(attrs={"rows": 8, "placeholder": "[00:01:10] Hola a todos, bienvenidos…"}))

    def clean(self):
        data = super().clean()
        if not data.get("file") and not (data.get("text") or "").strip():
            raise forms.ValidationError("Sube un archivo o pega el texto.")
        return data
