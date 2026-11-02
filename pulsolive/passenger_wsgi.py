"""Punto de entrada para hostings con cPanel (Namecheap, etc.) que usan Passenger.

cPanel → "Setup Python App" busca este archivo en la raíz de la aplicación.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from config.wsgi import application  # noqa: E402,F401
