from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import Invitation, Membership, Organization

User = get_user_model()


class SignupForm(UserCreationForm):
    first_name = forms.CharField(label="Tu nombre", max_length=60)
    email = forms.EmailField(label="Correo")
    org_name = forms.CharField(label="Nombre de tu agencia, marca o canal", max_length=120)
    org_kind = forms.ChoiceField(label="¿Qué eres?", choices=Organization.KIND_CHOICES)

    class Meta:
        model = User
        fields = ("first_name", "email", "org_name", "org_kind")

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(username=email).exists():
            raise forms.ValidationError("Ya existe una cuenta con ese correo.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["email"]
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        if commit:
            user.save()
        return user


class AcceptInvitationForm(UserCreationForm):
    first_name = forms.CharField(label="Tu nombre", max_length=60)

    class Meta:
        model = User
        fields = ("first_name",)


class OnboardingForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = ("name", "kind")


class OrganizationSettingsForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = ("name", "kind", "logo", "brand_color", "report_footer")
        widgets = {"brand_color": forms.TextInput(attrs={"type": "color"})}


class InvitationForm(forms.ModelForm):
    class Meta:
        model = Invitation
        fields = ("email", "role")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].choices = [c for c in Membership.ROLE_CHOICES if c[0] != Membership.ROLE_OWNER]
